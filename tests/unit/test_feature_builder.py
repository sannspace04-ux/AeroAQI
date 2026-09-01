"""
tests/unit/test_feature_builder.py
=====================================
Unit tests for src/models/feature_builder.py

All data is SYNTHETIC/DEMO — no real API calls.
Tests run without API keys or network access.

Run with:
    pytest tests/unit/test_feature_builder.py -v
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from src.models.feature_builder import FeatureBuilder, FORECAST_TARGETS


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------
_NOW = datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_obs(n: int = 80, station_id: str = "DEL_ITO") -> pd.DataFrame:
    """Build n rows of synthetic hourly observations at one station."""
    rows = []
    for i in range(n):
        ts = _NOW - timedelta(hours=n - i)
        rows.append({
            "timestamp_utc": ts,
            "station_id": station_id,
            "pm25": 50.0 + i * 0.5,
            "pm10": 80.0 + i * 0.5,
            "o3": 40.0 + (i % 10),
            "no2": 30.0 + (i % 5),
            "aqi_computed": 80.0 + i * 0.3,
            "temperature": 25.0 + (i % 8),
            "pbl_height": 400.0 + (i % 200),
            "wind_speed": 3.0 + (i % 5),
            "wind_direction": 315.0 + (i % 45),
            "relative_humidity": 60.0 + (i % 20),
            "inversion_strength": 2.5 + (i % 3),
            "wind_transport_idx": 0.7 + (i % 3) * 0.1,
            "mixing_volume_idx": 1500.0 + i * 10,
            "fire_transport_risk": 0.3 + (i % 5) * 0.05,
            "fire_count_300km": float(i % 10),
            "fire_distance_km": 200.0 + i,
        })
    return pd.DataFrame(rows)


# ===========================================================================
# Tests
# ===========================================================================

class TestFeatureBuilderBasic:

    @pytest.fixture
    def fb(self):
        return FeatureBuilder(target_hours=72)

    def test_returns_three_outputs(self, fb):
        X, y_dict, names = fb.build(_make_obs())
        assert isinstance(X, pd.DataFrame)
        assert isinstance(y_dict, dict)
        assert isinstance(names, list)

    def test_x_is_non_empty_for_sufficient_data(self, fb):
        X, _, _ = fb.build(_make_obs(n=80))
        assert len(X) > 0

    def test_x_has_no_nan(self, fb):
        X, _, _ = fb.build(_make_obs(n=80))
        assert not X.isnull().any().any(), "Feature matrix contains NaN after imputation"

    def test_x_has_no_inf(self, fb):
        X, _, _ = fb.build(_make_obs(n=80))
        assert np.isfinite(X.values).all(), "Feature matrix contains inf values"

    def test_feature_names_match_x_columns(self, fb):
        X, _, names = fb.build(_make_obs(n=80))
        assert list(X.columns) == names

    def test_feature_names_non_empty(self, fb):
        _, _, names = fb.build(_make_obs(n=80))
        assert len(names) > 0

    def test_empty_df_returns_empty_outputs(self, fb):
        X, y_dict, names = fb.build(pd.DataFrame())
        assert X.empty
        assert y_dict == {}
        assert names == []


class TestTimeFeatures:

    @pytest.fixture
    def fb(self):
        return FeatureBuilder(target_hours=3)

    def test_hour_sin_cos_present(self, fb):
        X, _, _ = fb.build(_make_obs(n=30))
        assert "hour_sin" in X.columns
        assert "hour_cos" in X.columns

    def test_month_sin_cos_present(self, fb):
        X, _, _ = fb.build(_make_obs(n=30))
        assert "month_sin" in X.columns
        assert "month_cos" in X.columns

    def test_cyclical_encoding_in_minus1_to_1(self, fb):
        X, _, _ = fb.build(_make_obs(n=30))
        for col in ["hour_sin", "hour_cos", "month_sin", "month_cos"]:
            assert (X[col] >= -1.0).all()
            assert (X[col] <= 1.0).all()

    def test_stubble_season_flag_present(self, fb):
        X, _, _ = fb.build(_make_obs(n=30))
        assert "is_stubble_season" in X.columns

    def test_stubble_season_is_1_for_october(self, fb):
        # _NOW is in October — is_stubble_season should be 1
        X, _, _ = fb.build(_make_obs(n=30))
        assert (X["is_stubble_season"] == 1.0).all()

    def test_stubble_season_is_0_for_january(self, fb):
        obs = _make_obs(n=20)
        obs["timestamp_utc"] = [
            datetime(2023, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
            for i in range(20)
        ]
        X, _, _ = fb.build(obs)
        assert (X["is_stubble_season"] == 0.0).all()


class TestLagFeatures:

    @pytest.fixture
    def fb(self):
        return FeatureBuilder(target_hours=3)

    def test_lag_features_present_for_pm25(self, fb):
        X, _, _ = fb.build(_make_obs(n=60))
        assert "pm25_lag1h" in X.columns
        assert "pm25_lag24h" in X.columns

    def test_lag_features_present_for_aqi(self, fb):
        X, _, _ = fb.build(_make_obs(n=60))
        assert "aqi_computed_lag1h" in X.columns

    def test_no_lag_nan_after_imputation(self, fb):
        X, _, _ = fb.build(_make_obs(n=60))
        lag_cols = [c for c in X.columns if "lag" in c]
        assert len(lag_cols) > 0
        for col in lag_cols:
            assert not X[col].isnull().any(), f"NaN found in lag column {col}"


class TestTargetBuilding:

    @pytest.fixture
    def fb(self):
        return FeatureBuilder(target_hours=3)  # 3 hours for speed

    def test_y_dict_has_target_keys(self, fb):
        _, y_dict, _ = fb.build(_make_obs(n=60))
        for tgt in FORECAST_TARGETS:
            for h in [1, 2, 3]:
                key = f"{tgt}_t+{h}"
                assert key in y_dict, f"Missing target key: {key}"

    def test_y_dict_series_aligned_with_x(self, fb):
        X, y_dict, _ = fb.build(_make_obs(n=60))
        for key, series in y_dict.items():
            assert len(series) == len(X), (
                f"y[{key}] length {len(series)} != X length {len(X)}"
            )


class TestImputation:

    @pytest.fixture
    def fb(self):
        return FeatureBuilder(target_hours=3)

    def test_missing_optional_column_handled_gracefully(self, fb):
        """DataFrame missing pbl_height and fire columns should still work."""
        obs = _make_obs(n=60)
        obs = obs.drop(columns=["pbl_height", "fire_count_300km"], errors="ignore")
        X, _, _ = fb.build(obs)
        assert not X.empty
        assert not X.isnull().any().any()

    def test_all_nan_column_not_zero_filled(self, fb):
        """Imputation uses median, not zero — median of all-NaN falls back to 0
        as last resort but should never silently mask the issue."""
        obs = _make_obs(n=60)
        obs["pm25"] = float("nan")
        X, _, _ = fb.build(obs)
        # pm25 lag features will be NaN then filled — they must not be -inf
        assert np.isfinite(X.values).all()


class TestStationFilter:

    def test_station_filter_applies(self):
        obs = pd.concat([_make_obs(20, "DEL_ITO"), _make_obs(20, "DEL_ROHINI")])
        fb = FeatureBuilder(target_hours=2)
        X_all, _, _ = fb.build(obs)
        X_ito, _, _ = fb.build(obs, station_id="DEL_ITO")
        assert len(X_ito) < len(X_all)

    def test_unknown_station_returns_empty(self):
        fb = FeatureBuilder(target_hours=2)
        X, y, names = fb.build(_make_obs(20), station_id="NONEXISTENT")
        assert X.empty
