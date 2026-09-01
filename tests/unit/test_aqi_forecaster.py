"""
tests/unit/test_aqi_forecaster.py
====================================
Unit tests for src/models/aqi_forecaster.py

All data is SYNTHETIC/DEMO. Tests run without API keys.
Uses a tiny dataset (30 rows) so training completes in milliseconds.

Run with:
    pytest tests/unit/test_aqi_forecaster.py -v
"""

from __future__ import annotations

import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.feature_builder import FeatureBuilder, FORECAST_TARGETS
from src.models.aqi_forecaster import AQIForecaster, aqi_to_category


# ---------------------------------------------------------------------------
# Synthetic data
# ---------------------------------------------------------------------------
_NOW = datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_obs(n: int = 50) -> pd.DataFrame:
    rows = []
    for i in range(n):
        ts = _NOW - timedelta(hours=n - i)
        rows.append({
            "timestamp_utc": ts,
            "station_id": "DEL_ITO",
            "pm25": 50.0 + (i % 30) * 2,
            "pm10": 80.0 + (i % 20) * 3,
            "o3": 40.0 + (i % 10),
            "no2": 30.0 + (i % 5),
            "aqi_computed": 80.0 + (i % 30) * 2,
            "temperature": 25.0,
            "pbl_height": 400.0,
            "wind_speed": 3.0,
            "wind_direction": 315.0,
            "inversion_strength": 2.5,
            "wind_transport_idx": 0.7,
            "mixing_volume_idx": 1200.0,
            "fire_transport_risk": 0.3,
        })
    return pd.DataFrame(rows)


def _train_quick_forecaster(n: int = 50, target_hours: int = 3) -> tuple:
    """Return (forecaster, X_test, y_test_dict, feature_names) trained on tiny data."""
    obs = _make_obs(n)
    fb = FeatureBuilder(target_hours=target_hours)
    X, y_dict, feat_names = fb.build(obs)
    params = {
        "n_estimators": 5,
        "max_depth": 2,
        "learning_rate": 0.1,
        "objective": "reg:squarederror",
        "random_state": 42,
        "n_jobs": 1,
        "verbosity": 0,
    }
    fc = AQIForecaster(target_hours=target_hours, model_params=params)
    n_test = max(1, int(len(X) * 0.2))
    X_train, X_test = X.iloc[:-n_test], X.iloc[-n_test:]
    y_train = {k: v.iloc[:-n_test] for k, v in y_dict.items()}
    y_test = {k: v.iloc[-n_test:] for k, v in y_dict.items()}
    fc.fit(X_train, y_train, feature_names=feat_names)
    return fc, X_test, y_test, feat_names


# ===========================================================================
# AQI category helper
# ===========================================================================

class TestAqiToCategory:

    def test_good(self):
        assert aqi_to_category(25) == "Good"

    def test_satisfactory(self):
        assert aqi_to_category(75) == "Satisfactory"

    def test_moderate(self):
        assert aqi_to_category(150) == "Moderate"

    def test_poor(self):
        assert aqi_to_category(250) == "Poor"

    def test_very_poor(self):
        assert aqi_to_category(350) == "Very Poor"

    def test_severe(self):
        assert aqi_to_category(450) == "Severe"

    def test_none_returns_unknown(self):
        assert aqi_to_category(None) == "Unknown"

    def test_nan_returns_unknown(self):
        assert aqi_to_category(float("nan")) == "Unknown"


# ===========================================================================
# AQIForecaster
# ===========================================================================

class TestAQIForecasterTrain:

    def test_fit_succeeds_on_small_dataset(self):
        fc, _, _, _ = _train_quick_forecaster()
        assert fc.is_trained

    def test_n_models_positive_after_fit(self):
        fc, _, _, _ = _train_quick_forecaster()
        assert fc.n_models > 0

    def test_feature_names_stored(self):
        fc, _, _, names = _train_quick_forecaster()
        assert fc.feature_names == names

    def test_fit_empty_x_does_not_crash(self):
        fc = AQIForecaster(target_hours=3)
        fc.fit(pd.DataFrame(), {})
        assert not fc.is_trained

    def test_fit_called_twice_overwrites(self):
        obs = _make_obs(50)
        fb = FeatureBuilder(target_hours=3)
        X, y, names = fb.build(obs)
        params = {"n_estimators": 5, "max_depth": 2, "learning_rate": 0.1,
                  "objective": "reg:squarederror", "random_state": 42,
                  "n_jobs": 1, "verbosity": 0}
        fc = AQIForecaster(target_hours=3, model_params=params)
        fc.fit(X, y, feature_names=names)
        n1 = fc.n_models
        fc.fit(X, y, feature_names=names)   # second call — should replace
        assert fc.n_models == n1


class TestAQIForecasterPredict:

    @pytest.fixture(scope="module")
    def trained_fc_and_data(self):
        return _train_quick_forecaster(n=50, target_hours=3)

    def test_predict_returns_dataframe(self, trained_fc_and_data):
        fc, X_test, _, _ = trained_fc_and_data
        result = fc.predict(X_test)
        assert isinstance(result, pd.DataFrame)

    def test_predict_has_correct_row_count(self, trained_fc_and_data):
        fc, X_test, _, _ = trained_fc_and_data
        result = fc.predict(X_test)
        assert len(result) == 3   # target_hours=3

    def test_predict_has_expected_columns(self, trained_fc_and_data):
        fc, X_test, _, _ = trained_fc_and_data
        result = fc.predict(X_test)
        for col in ["forecast_hour", "pm25", "pm10", "aqi_computed", "aqi_category"]:
            assert col in result.columns, f"Missing column: {col}"

    def test_forecast_hours_are_1_to_n(self, trained_fc_and_data):
        fc, X_test, _, _ = trained_fc_and_data
        result = fc.predict(X_test)
        assert list(result["forecast_hour"]) == [1, 2, 3]

    def test_pm25_values_are_non_negative(self, trained_fc_and_data):
        fc, X_test, _, _ = trained_fc_and_data
        result = fc.predict(X_test)
        for val in result["pm25"].dropna():
            assert val >= 0.0, f"Negative PM2.5 prediction: {val}"

    def test_aqi_category_is_valid_string(self, trained_fc_and_data):
        fc, X_test, _, _ = trained_fc_and_data
        valid = {"Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"}
        result = fc.predict(X_test)
        for cat in result["aqi_category"].dropna():
            assert cat in valid, f"Unexpected AQI category: {cat}"

    def test_no_nan_in_numeric_columns(self, trained_fc_and_data):
        fc, X_test, _, _ = trained_fc_and_data
        result = fc.predict(X_test)
        for col in ["pm25", "pm10", "aqi_computed"]:
            if col in result.columns:
                vals = result[col].dropna()
                for v in vals:
                    assert math.isfinite(v), f"Non-finite value in {col}: {v}"

    def test_predict_empty_x_returns_empty(self, trained_fc_and_data):
        fc, _, _, _ = trained_fc_and_data
        result = fc.predict(pd.DataFrame())
        assert result.empty

    def test_predict_before_fit_returns_empty(self):
        fc = AQIForecaster(target_hours=3)
        result = fc.predict(pd.DataFrame({"x": [1, 2, 3]}))
        assert result.empty

    def test_station_id_stamped(self, trained_fc_and_data):
        fc, X_test, _, _ = trained_fc_and_data
        result = fc.predict(X_test, station_id="DEL_ITO")
        assert (result["station_id"] == "DEL_ITO").all()

    def test_target_utc_present_when_base_ts_given(self, trained_fc_and_data):
        fc, X_test, _, _ = trained_fc_and_data
        base = pd.Timestamp("2023-10-15T12:00:00", tz="UTC")
        result = fc.predict(X_test, base_timestamp=base)
        assert result["target_utc"].notna().all()


class TestAQIForecasterSaveLoad:

    def test_save_and_load_roundtrip(self):
        fc_orig, X_test, _, _ = _train_quick_forecaster()
        with tempfile.TemporaryDirectory() as tmpdir:
            fc_orig.save(tmpdir)
            # Verify meta file exists
            assert (Path(tmpdir) / "_meta.joblib").exists()

            # Load into a new forecaster
            fc_loaded = AQIForecaster(target_hours=3)
            ok = fc_loaded.load(tmpdir)
            assert ok
            assert fc_loaded.is_trained
            assert fc_loaded.n_models == fc_orig.n_models

            # Predictions should be consistent
            r1 = fc_orig.predict(X_test)
            r2 = fc_loaded.predict(X_test)
            assert len(r1) == len(r2)
            if "pm25" in r1.columns and "pm25" in r2.columns:
                for v1, v2 in zip(r1["pm25"].dropna(), r2["pm25"].dropna()):
                    assert abs(v1 - v2) < 1e-6

    def test_load_from_empty_dir_returns_false(self):
        fc = AQIForecaster(target_hours=3)
        with tempfile.TemporaryDirectory() as tmpdir:
            ok = fc.load(tmpdir)
        assert ok is False
        assert not fc.is_trained

    def test_load_nonexistent_dir_returns_false(self):
        fc = AQIForecaster(target_hours=3)
        ok = fc.load("/nonexistent/path/xyz")
        assert ok is False


class TestAQIForecasterEvaluate:

    def test_evaluate_returns_dict(self):
        fc, X_test, y_test, _ = _train_quick_forecaster()
        metrics = fc.evaluate(X_test, y_test)
        assert isinstance(metrics, dict)

    def test_metrics_have_rmse_and_mae(self):
        fc, X_test, y_test, _ = _train_quick_forecaster()
        metrics = fc.evaluate(X_test, y_test)
        for key, m in metrics.items():
            assert "rmse" in m
            assert "mae" in m

    def test_rmse_is_finite(self):
        fc, X_test, y_test, _ = _train_quick_forecaster()
        metrics = fc.evaluate(X_test, y_test)
        for key, m in metrics.items():
            assert math.isfinite(m["rmse"]), f"Non-finite RMSE for {key}"
            assert math.isfinite(m["mae"]), f"Non-finite MAE for {key}"

    def test_evaluate_before_fit_returns_empty(self):
        fc = AQIForecaster(target_hours=3)
        metrics = fc.evaluate(pd.DataFrame(), {})
        assert metrics == {}
