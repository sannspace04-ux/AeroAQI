"""
src/models/aqi_forecaster.py
=============================
72-hour AQI forecaster using XGBoost gradient-boosted trees.

Strategy
--------
Direct multi-step forecasting: one XGBRegressor is trained per
(target_variable × forecast_horizon_hour), e.g. a separate model for
pm25_t+1, pm25_t+2, …, pm25_t+72.

This avoids recursive error compounding (where errors in step 1
feed into step 2 and grow over time).  With 5 targets × 72 hours
= 360 models, each model is lightweight (shallow trees, small dataset).

Models are saved to ``data/models/<target>_t+<h>.joblib`` so they
persist across server restarts and do not need retraining on every run.

Usage
-----
    from src.models.aqi_forecaster import AQIForecaster
    from src.models.feature_builder import FeatureBuilder

    fb  = FeatureBuilder()
    afc = AQIForecaster()

    X, y_dict, feat_names = fb.build(obs_df)
    afc.fit(X, y_dict)
    afc.save("data/models")

    # Later, for inference:
    afc.load("data/models")
    forecast_df = afc.predict(X_latest, feature_names=feat_names)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

log = get_logger(__name__)

# XGBoost is an optional dependency — guard import so the rest of the
# application still works if it is not installed.
try:
    from xgboost import XGBRegressor
    _XGBOOST_AVAILABLE = True
except ImportError:  # pragma: no cover
    _XGBOOST_AVAILABLE = False
    log.warning(
        "[forecaster] xgboost not installed — forecasting will not work. "
        "Install with: pip install xgboost==2.1.1"
    )

try:
    import joblib
    _JOBLIB_AVAILABLE = True
except ImportError:  # pragma: no cover
    _JOBLIB_AVAILABLE = False

from src.models.feature_builder import FORECAST_TARGETS

# Default XGBoost hyper-parameters — conservative, fast-training values
# suitable for the small to medium datasets in this prototype.
_DEFAULT_XGBOOST_PARAMS = {
    "n_estimators": 200,
    "max_depth": 5,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "objective": "reg:squarederror",
    "random_state": 42,
    "n_jobs": -1,
    "verbosity": 0,
}

# CPCB AQI category breakpoints
_AQI_CATEGORIES = [
    (0,    50,   "Good"),
    (51,   100,  "Satisfactory"),
    (101,  200,  "Moderate"),
    (201,  300,  "Poor"),
    (301,  400,  "Very Poor"),
    (401,  float("inf"), "Severe"),
]


def aqi_to_category(aqi: float | None) -> str:
    """Map a numeric AQI value to its CPCB category string."""
    if aqi is None or (isinstance(aqi, float) and np.isnan(aqi)):
        return "Unknown"
    for lo, hi, label in _AQI_CATEGORIES:
        if lo <= aqi <= hi:
            return label
    return "Severe" if aqi > 400 else "Unknown"


class AQIForecaster:
    """
    Multi-step XGBoost AQI forecaster.

    Parameters
    ----------
    target_hours : int
        Number of future hours to forecast (default 72).
    model_params : dict | None
        XGBoost parameters.  Defaults to ``_DEFAULT_XGBOOST_PARAMS``.
    """

    def __init__(
        self,
        target_hours: int = 72,
        model_params: Optional[dict] = None,
    ) -> None:
        self._target_hours = target_hours
        self._params = model_params or _DEFAULT_XGBOOST_PARAMS.copy()
        # _models: dict keyed by "pm25_t+1", "pm10_t+1" etc.
        self._models: dict[str, Any] = {}
        self._feature_names: list[str] = []
        self._is_trained = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(
        self,
        X: pd.DataFrame,
        y_dict: dict[str, pd.Series],
        feature_names: Optional[list[str]] = None,
    ) -> "AQIForecaster":
        """
        Train one XGBRegressor per (target × horizon) pair.

        Parameters
        ----------
        X            : Feature matrix (NaN-free, from FeatureBuilder).
        y_dict       : Target columns keyed as ``"pm25_t+1"`` etc.
        feature_names: Ordered list of feature names (stored for SHAP).

        Returns self for chaining.
        """
        if not _XGBOOST_AVAILABLE:
            raise ImportError(
                "xgboost is required for training. "
                "Install with: pip install xgboost==2.1.1"
            )
        if X.empty or not y_dict:
            log.warning("[forecaster] fit() called with empty X or y_dict — skipping.")
            return self

        self._feature_names = feature_names or list(X.columns)
        n_trained = 0

        for key, y_series in y_dict.items():
            # Drop rows where target is NaN
            mask = y_series.notna()
            if mask.sum() < 5:
                log.debug(f"[forecaster] Skipping {key} — fewer than 5 training rows.")
                continue

            X_train = X[mask].values
            y_train = y_series[mask].values

            model = XGBRegressor(**self._params)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model.fit(X_train, y_train)

            self._models[key] = model
            n_trained += 1

        self._is_trained = len(self._models) > 0
        log.info(
            f"[forecaster] Training complete — {n_trained} models trained "
            f"across {len(FORECAST_TARGETS)} targets × {self._target_hours} horizons."
        )
        return self

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(
        self,
        X_latest: pd.DataFrame,
        feature_names: Optional[list[str]] = None,
        station_id: Optional[str] = None,
        base_timestamp: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """
        Generate a 72-hour forecast from the most recent feature row.

        Parameters
        ----------
        X_latest      : Feature matrix for the latest time step(s).
                        Only the last row is used.
        feature_names : Feature names (used to align columns).
        station_id    : Stamped on every output row.
        base_timestamp: UTC timestamp of the last observation row.
                        Forecast target times are base + 1h, +2h, …

        Returns
        -------
        pd.DataFrame with columns:
            station_id, forecast_hour, target_utc,
            pm25, pm10, o3, no2, aqi_computed, aqi_category
        """
        if not self._is_trained:
            log.warning("[forecaster] predict() called before fit() or load().")
            return pd.DataFrame()

        if X_latest.empty:
            return pd.DataFrame()

        # Use the last row for inference
        x_row = X_latest.iloc[[-1]].values

        rows = []
        for h in range(1, self._target_hours + 1):
            row: dict[str, Any] = {
                "station_id": station_id,
                "forecast_hour": h,
                "target_utc": (
                    (base_timestamp + pd.Timedelta(hours=h)).isoformat()
                    if base_timestamp is not None else None
                ),
            }
            for target in FORECAST_TARGETS:
                key = f"{target}_t+{h}"
                model = self._models.get(key)
                if model is not None:
                    val = float(model.predict(x_row)[0])
                    # Clip to physical bounds (pollutants can't be negative)
                    val = max(0.0, val)
                    row[target] = round(val, 2)
                else:
                    row[target] = None

            # Compute AQI category
            aqi_val = row.get("aqi_computed")
            row["aqi_category"] = aqi_to_category(aqi_val)
            rows.append(row)

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, model_dir: str | Path) -> None:
        """
        Save all trained models to ``<model_dir>/<key>.joblib``.

        Parameters
        ----------
        model_dir : Directory path (created if it does not exist).
        """
        if not _JOBLIB_AVAILABLE:
            raise ImportError("joblib is required to save models.")
        if not self._is_trained:
            log.warning("[forecaster] save() called with no trained models.")
            return

        model_dir = Path(model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)

        for key, model in self._models.items():
            filepath = model_dir / f"{key}.joblib"
            joblib.dump(model, filepath)

        # Save metadata (feature names, params)
        meta = {
            "feature_names": self._feature_names,
            "target_hours": self._target_hours,
            "n_models": len(self._models),
            "model_keys": list(self._models.keys()),
        }
        joblib.dump(meta, model_dir / "_meta.joblib")
        log.info(f"[forecaster] Saved {len(self._models)} models to {model_dir}")

    def load(self, model_dir: str | Path) -> bool:
        """
        Load pre-trained models from ``<model_dir>``.

        Returns True if models were loaded successfully, False if the
        directory is empty or does not exist.
        """
        if not _JOBLIB_AVAILABLE:
            raise ImportError("joblib is required to load models.")

        model_dir = Path(model_dir)
        meta_path = model_dir / "_meta.joblib"

        if not meta_path.exists():
            log.info(
                f"[forecaster] No saved models found at {model_dir}. "
                "Run scripts/train_model.py to train the model first."
            )
            return False

        meta = joblib.load(meta_path)
        self._feature_names = meta.get("feature_names", [])
        self._target_hours = meta.get("target_hours", 72)

        self._models = {}
        for key in meta.get("model_keys", []):
            filepath = model_dir / f"{key}.joblib"
            if filepath.exists():
                self._models[key] = joblib.load(filepath)

        self._is_trained = len(self._models) > 0
        log.info(
            f"[forecaster] Loaded {len(self._models)} models from {model_dir}"
        )
        return self._is_trained

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        X_test: pd.DataFrame,
        y_dict_test: dict[str, pd.Series],
    ) -> dict[str, dict[str, float]]:
        """
        Compute RMSE and MAE for each target on held-out data.

        Returns
        -------
        dict: ``{"pm25_t+1": {"rmse": 12.3, "mae": 9.1}, …}``
        """
        if not self._is_trained:
            return {}

        metrics: dict[str, dict[str, float]] = {}
        for key, y_true in y_dict_test.items():
            model = self._models.get(key)
            if model is None:
                continue
            mask = y_true.notna()
            if mask.sum() == 0:
                continue
            y_pred = model.predict(X_test[mask].values)
            y_actual = y_true[mask].values
            rmse = float(np.sqrt(np.mean((y_pred - y_actual) ** 2)))
            mae = float(np.mean(np.abs(y_pred - y_actual)))
            metrics[key] = {"rmse": round(rmse, 3), "mae": round(mae, 3)}

        return metrics

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    @property
    def n_models(self) -> int:
        return len(self._models)
