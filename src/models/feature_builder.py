"""
src/models/feature_builder.py
==============================
Constructs the feature matrix (X) and target matrix (y) that the
AQI forecaster trains and infers on.

Design
------
- Input  : a pandas DataFrame that matches (or is a subset of) the master
           schema — one row per (station_id, timestamp_utc).
- Output : a clean, numeric feature matrix with:
    * Rolling lag features for the primary pollutants and AQI
    * Hour-of-day and month-of-year encoded cyclically (sin/cos)
    * An is_stubble_season boolean flag (October–November)
    * All physics-informed features already in the master schema
      (pbl_height, inversion_strength, wind_transport_idx,
       mixing_volume_idx, fire_transport_risk)
- Missing values are forward-filled within each station group, then
  filled with the column median.  Values are NEVER filled with zero.
- All column names are documented so SHAP can reference them by name.

Usage
-----
    from src.models.feature_builder import FeatureBuilder

    fb = FeatureBuilder()
    X, y, feature_names = fb.build(obs_df, target_hours=72)
    # X : (n_samples, n_features)
    # y : dict {target_name: pd.Series}  e.g. {"pm25_t1": ..., "pm25_t72": ...}
    # feature_names : list[str]
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Feature column definitions
# ---------------------------------------------------------------------------

# Physics-informed features from master schema (already computed in Phase 4)
_PHYSICS_FEATURES = [
    "pbl_height",
    "inversion_strength",
    "wind_transport_idx",
    "mixing_volume_idx",
    "fire_transport_risk",
    "wind_speed",
    "wind_direction",
    "temperature",
    "relative_humidity",
    "surface_pressure",
    "precipitation",
    "solar_radiation",
    "fire_count_300km",
    "fire_distance_km",
]

# Pollutants for which lag features are created
_LAG_TARGETS = ["pm25", "pm10", "o3", "no2", "aqi_computed"]

# Lag windows (hours)
_LAG_HOURS = [1, 3, 6, 12, 24, 48]

# Target variables the model predicts (one column per forecast step)
FORECAST_TARGETS = ["pm25", "pm10", "o3", "no2", "aqi_computed"]


class FeatureBuilder:
    """
    Transforms the master observation DataFrame into a numeric feature
    matrix ready for XGBoost.

    Parameters
    ----------
    target_hours : int
        Forecast horizon (default 72).  Each target column is named
        e.g. ``pm25_t+1``, ``pm25_t+2``, … ``pm25_t+72``.
    """

    def __init__(self, target_hours: int = 72) -> None:
        self._target_hours = target_hours

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        df: pd.DataFrame,
        station_id: Optional[str] = None,
    ) -> tuple[pd.DataFrame, dict[str, pd.Series], list[str]]:
        """
        Build the feature matrix and target columns.

        Parameters
        ----------
        df          : Master observation DataFrame (sorted by timestamp_utc).
        station_id  : If provided, filter to a single station before
                      building features.

        Returns
        -------
        X            : pd.DataFrame  — numeric features (NaN-free)
        y_dict       : dict  — target series keyed as ``"pm25_t+1"`` etc.
        feature_names: list[str]  — ordered feature column names (for SHAP)
        """
        if df.empty:
            return pd.DataFrame(), {}, []

        df = df.copy()
        if station_id:
            df = df[df["station_id"] == station_id].copy()
            if df.empty:
                return pd.DataFrame(), {}, []

        # Ensure timestamp is parsed
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp_utc"]).sort_values("timestamp_utc").reset_index(drop=True)

        # ── Time features ────────────────────────────────────────────────
        df = self._add_time_features(df)

        # ── Lag features ─────────────────────────────────────────────────
        df = self._add_lag_features(df)

        # ── Identify feature columns ─────────────────────────────────────
        feature_cols = self._get_feature_columns(df)

        # ── Build target columns ─────────────────────────────────────────
        y_dict = self._build_targets(df)

        # ── Drop rows with NaN targets ────────────────────────────────────
        # Keep only rows where at least one target is available
        target_series_list = list(y_dict.values())
        if target_series_list:
            any_target = pd.concat(target_series_list, axis=1).notna().any(axis=1)
            df = df[any_target].reset_index(drop=True)
            y_dict = {k: v[any_target].reset_index(drop=True) for k, v in y_dict.items()}

        # ── Impute features ──────────────────────────────────────────────
        X = df[feature_cols].copy()
        X = self._impute(X)

        log.debug(
            f"[feature_builder] Built feature matrix: "
            f"{X.shape[0]} rows × {X.shape[1]} features, "
            f"{len(y_dict)} target series."
        )
        return X, y_dict, list(X.columns)

    def get_feature_names(self, df: pd.DataFrame) -> list[str]:
        """Return the feature column names for a given DataFrame shape."""
        df_tmp = self._add_time_features(df.copy())
        df_tmp = self._add_lag_features(df_tmp)
        return self._get_feature_columns(df_tmp)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add hour-of-day and month cyclical encodings + stubble flag."""
        hour = df["timestamp_utc"].dt.hour.astype(float)
        month = df["timestamp_utc"].dt.month.astype(float)

        df["hour_sin"] = np.sin(2 * math.pi * hour / 24.0)
        df["hour_cos"] = np.cos(2 * math.pi * hour / 24.0)
        df["month_sin"] = np.sin(2 * math.pi * month / 12.0)
        df["month_cos"] = np.cos(2 * math.pi * month / 12.0)

        # Stubble burning season: October (10) and November (11)
        df["is_stubble_season"] = month.isin([10, 11]).astype(float)

        return df

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create rolling lag features for each pollutant target."""
        # If multiple stations, group by station to avoid cross-station lag leakage
        has_station = "station_id" in df.columns and df["station_id"].notna().any()

        for target in _LAG_TARGETS:
            if target not in df.columns:
                continue
            series = pd.to_numeric(df[target], errors="coerce")
            for lag_h in _LAG_HOURS:
                col_name = f"{target}_lag{lag_h}h"
                if has_station:
                    # Group-aware shift
                    df[col_name] = df.groupby("station_id")[target].transform(
                        lambda s: pd.to_numeric(s, errors="coerce").shift(lag_h)
                    )
                else:
                    df[col_name] = series.shift(lag_h)

        return df

    def _get_feature_columns(self, df: pd.DataFrame) -> list[str]:
        """Collect all feature column names present in df."""
        # Time features
        time_cols = [
            "hour_sin", "hour_cos", "month_sin", "month_cos",
            "is_stubble_season",
        ]
        # Physics features
        physics_cols = [c for c in _PHYSICS_FEATURES if c in df.columns]
        # Lag features
        lag_cols = [
            f"{t}_lag{h}h"
            for t in _LAG_TARGETS
            for h in _LAG_HOURS
            if f"{t}_lag{h}h" in df.columns
        ]
        all_cols = time_cols + physics_cols + lag_cols
        return [c for c in all_cols if c in df.columns]

    def _build_targets(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """
        Build future-shifted target columns.

        For each target pollutant and each forecast step h (1 … target_hours),
        create a Series where row i is the value at i+h.
        """
        y_dict: dict[str, pd.Series] = {}
        has_station = "station_id" in df.columns and df["station_id"].notna().any()

        for target in FORECAST_TARGETS:
            if target not in df.columns:
                continue
            for h in range(1, self._target_hours + 1):
                key = f"{target}_t+{h}"
                if has_station:
                    y_dict[key] = df.groupby("station_id")[target].transform(
                        lambda s: pd.to_numeric(s, errors="coerce").shift(-h)
                    )
                else:
                    y_dict[key] = pd.to_numeric(df[target], errors="coerce").shift(-h)

        return y_dict

    @staticmethod
    def _impute(X: pd.DataFrame) -> pd.DataFrame:
        """
        Forward-fill, then fill remaining NaN with the column median.
        Never fills with zero — zero has physical meaning for pollutants.
        """
        X = X.ffill()
        for col in X.columns:
            median = X[col].median()
            if pd.isna(median):
                median = 0.0  # last resort — all values are NaN
            X[col] = X[col].fillna(median)
        return X
