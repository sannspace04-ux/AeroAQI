"""
src/models/explainer.py
========================
SHAP-based explainability for the AQI forecasts.

For every 72-hour forecast window, the explainer answers:
  "What drove today's high PM2.5 prediction?"

It uses ``shap.TreeExplainer`` (which is fast for XGBoost without
requiring sampling) to compute exact SHAP values.

Output per station per forecast run:
- Top-5 features by mean |SHAP value| across hours 1–24
- Percentage contribution of each top feature
- Plain-language summary string, e.g.:
    "High PM2.5 driven by NW wind transport (38%), shallow PBL 180 m (27%),
     stubble season (18%), high fire density 300 km (12%), low mixing volume (5%)"

Usage
-----
    from src.models.explainer import ForecastExplainer

    explainer = ForecastExplainer(forecaster)
    result = explainer.explain(X_latest, target="pm25", horizon_hours=24)
    print(result["explanation_text"])
"""

from __future__ import annotations

import json
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

log = get_logger(__name__)

# SHAP import guard
try:
    import shap
    _SHAP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SHAP_AVAILABLE = False
    log.warning(
        "[explainer] shap not installed — explanations will not be generated. "
        "Install with: pip install shap==0.46.0"
    )

# Human-readable labels for feature names used in explanation text
_FEATURE_LABELS: dict[str, str] = {
    "pbl_height":           "Boundary layer height",
    "inversion_strength":   "Temperature inversion",
    "wind_transport_idx":   "NW wind transport",
    "mixing_volume_idx":    "Atmospheric mixing",
    "fire_transport_risk":  "Fire transport risk",
    "fire_count_300km":     "Fire density (300 km)",
    "fire_distance_km":     "Distance to nearest fire",
    "wind_speed":           "Wind speed",
    "wind_direction":       "Wind direction",
    "temperature":          "Temperature",
    "relative_humidity":    "Relative humidity",
    "is_stubble_season":    "Stubble season",
    "hour_sin":             "Time of day",
    "hour_cos":             "Time of day",
    "pm25_lag1h":           "PM2.5 (1 h ago)",
    "pm25_lag6h":           "PM2.5 (6 h ago)",
    "pm25_lag24h":          "PM2.5 (24 h ago)",
    "pm10_lag1h":           "PM10 (1 h ago)",
    "pm10_lag24h":          "PM10 (24 h ago)",
    "aqi_computed_lag1h":   "AQI (1 h ago)",
    "aqi_computed_lag24h":  "AQI (24 h ago)",
}


class ForecastExplainer:
    """
    SHAP-based explanation generator for the AQIForecaster.

    Parameters
    ----------
    forecaster : AQIForecaster
        A trained model instance.  Explanations are generated for the
        models inside it.
    top_n : int
        Number of top features to include in the explanation (default 5).
    """

    def __init__(self, forecaster: Any, top_n: int = 5) -> None:
        self._forecaster = forecaster
        self._top_n = top_n
        # Cache TreeExplainer instances per model key to avoid rebuilding
        self._explainers: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain(
        self,
        X: pd.DataFrame,
        target: str = "pm25",
        horizon_hours: int = 24,
    ) -> dict[str, Any]:
        """
        Generate a SHAP explanation for the given feature matrix.

        Computes SHAP values across all forecast steps for ``target``
        within ``horizon_hours``, then ranks features by mean |SHAP|.

        Parameters
        ----------
        X             : Feature matrix (NaN-free).  Only the last row is used.
        target        : Pollutant name, e.g. ``"pm25"``.
        horizon_hours : How many forecast steps to average SHAP over.

        Returns
        -------
        dict with keys:
            top_features     : list of {name, label, shap_value, contribution_pct}
            explanation_text : human-readable summary string
            inversion_detected: bool (True if inversion_strength > 2.0 in features)
            shap_available   : bool (False if shap not installed)
        """
        if not _SHAP_AVAILABLE or not self._forecaster.is_trained:
            return self._empty_explanation(target, "shap not available or model not trained")

        if X.empty:
            return self._empty_explanation(target, "empty feature matrix")

        x_row = X.iloc[[-1]]  # last row only
        feature_names = self._forecaster.feature_names or list(X.columns)

        # Accumulate |SHAP values| across horizons 1..horizon_hours
        shap_accum = np.zeros(len(feature_names))
        n_computed = 0

        for h in range(1, min(horizon_hours, self._forecaster._target_hours) + 1):
            key = f"{target}_t+{h}"
            model = self._forecaster._models.get(key)
            if model is None:
                continue

            explainer = self._get_explainer(key, model)
            if explainer is None:
                continue

            try:
                shap_vals = explainer.shap_values(x_row.values)
                if shap_vals is not None and len(shap_vals.shape) == 2:
                    shap_accum += np.abs(shap_vals[0])
                    n_computed += 1
            except Exception as exc:
                log.debug(f"[explainer] SHAP failed for {key}: {exc}")

        if n_computed == 0:
            return self._empty_explanation(target, "no SHAP values computed")

        mean_shap = shap_accum / n_computed

        # Rank features
        ranked_idx = np.argsort(mean_shap)[::-1]
        total_shap = float(mean_shap.sum()) or 1.0

        top_features = []
        for rank, idx in enumerate(ranked_idx[: self._top_n]):
            if idx >= len(feature_names):
                break
            name = feature_names[idx]
            sv = float(mean_shap[idx])
            pct = round(sv / total_shap * 100, 1)
            top_features.append({
                "rank": rank + 1,
                "name": name,
                "label": _FEATURE_LABELS.get(name, name.replace("_", " ").title()),
                "shap_value": round(sv, 4),
                "contribution_pct": pct,
            })

        explanation_text = self._build_text(target, top_features, horizon_hours)

        # Detect inversion from feature values
        inversion_col = "inversion_strength"
        inversion_detected = False
        if inversion_col in X.columns:
            val = float(x_row[inversion_col].iloc[0])
            inversion_detected = val > 2.0 if not np.isnan(val) else False

        return {
            "top_features": top_features,
            "explanation_text": explanation_text,
            "inversion_detected": inversion_detected,
            "shap_available": True,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_explainer(self, key: str, model: Any) -> Any:
        """Get or build a cached TreeExplainer for a model."""
        if key not in self._explainers:
            try:
                self._explainers[key] = shap.TreeExplainer(model)
            except Exception as exc:
                log.debug(f"[explainer] Could not build TreeExplainer for {key}: {exc}")
                return None
        return self._explainers[key]

    @staticmethod
    def _build_text(
        target: str,
        top_features: list[dict],
        horizon_hours: int,
    ) -> str:
        """Build a concise plain-language explanation string."""
        target_label = {
            "pm25": "PM2.5",
            "pm10": "PM10",
            "o3": "ozone",
            "no2": "NO₂",
            "aqi_computed": "AQI",
        }.get(target, target.upper())

        parts = [
            f"{f['label']} ({f['contribution_pct']:.0f}%)"
            for f in top_features
            if f["contribution_pct"] >= 1.0
        ]
        if not parts:
            return (
                f"{target_label} forecast for the next {horizon_hours} h "
                f"is driven by multiple factors."
            )
        drivers = ", ".join(parts)
        return (
            f"{target_label} forecast for the next {horizon_hours} h "
            f"is primarily driven by: {drivers}."
        )

    @staticmethod
    def _empty_explanation(target: str, reason: str) -> dict[str, Any]:
        return {
            "top_features": [],
            "explanation_text": (
                f"Explanation not available for {target}: {reason}."
            ),
            "inversion_detected": False,
            "shap_available": False,
        }
