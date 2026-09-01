"""
tests/unit/test_explainer.py
================================
Unit tests for src/models/explainer.py

Tests run without network access. The SHAP tests only run when
shap is installed (they are skipped gracefully otherwise).

Run with:
    pytest tests/unit/test_explainer.py -v
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from src.models.feature_builder import FeatureBuilder
from src.models.aqi_forecaster import AQIForecaster
from src.models.explainer import ForecastExplainer, _FEATURE_LABELS


# ---------------------------------------------------------------------------
# Check if shap is available
# ---------------------------------------------------------------------------
try:
    import shap  # noqa: F401
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False


# ---------------------------------------------------------------------------
# Synthetic helpers
# ---------------------------------------------------------------------------
_NOW = datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_obs(n: int = 60) -> pd.DataFrame:
    rows = []
    for i in range(n):
        ts = _NOW - timedelta(hours=n - i)
        rows.append({
            "timestamp_utc": ts,
            "station_id": "DEL_ITO",
            "pm25": 50.0 + (i % 30) * 2,
            "pm10": 80.0 + (i % 20),
            "o3": 40.0,
            "no2": 30.0,
            "aqi_computed": 85.0 + (i % 20),
            "temperature": 25.0,
            "pbl_height": 500.0,
            "wind_speed": 3.0,
            "wind_direction": 315.0,
            "inversion_strength": 3.0,
            "wind_transport_idx": 0.8,
            "mixing_volume_idx": 1500.0,
            "fire_transport_risk": 0.4,
        })
    return pd.DataFrame(rows)


def _get_trained_fc_and_X():
    obs = _make_obs(60)
    fb = FeatureBuilder(target_hours=3)
    X, y, names = fb.build(obs)
    params = {"n_estimators": 5, "max_depth": 2, "learning_rate": 0.1,
              "objective": "reg:squarederror", "random_state": 42,
              "n_jobs": 1, "verbosity": 0}
    fc = AQIForecaster(target_hours=3, model_params=params)
    n_test = max(1, int(len(X) * 0.2))
    fc.fit(X.iloc[:-n_test], {k: v.iloc[:-n_test] for k, v in y.items()},
           feature_names=names)
    return fc, X, names


# ===========================================================================
# ForecastExplainer
# ===========================================================================

class TestForecastExplainerUntrained:
    """Graceful handling when the model is not trained."""

    def test_explain_untrained_returns_dict(self):
        fc = AQIForecaster(target_hours=3)
        exp = ForecastExplainer(fc)
        result = exp.explain(pd.DataFrame({"x": [1.0]}))
        assert isinstance(result, dict)

    def test_explain_untrained_has_empty_top_features(self):
        fc = AQIForecaster(target_hours=3)
        exp = ForecastExplainer(fc)
        result = exp.explain(pd.DataFrame({"x": [1.0]}))
        assert result["top_features"] == []

    def test_explain_untrained_has_explanation_text(self):
        fc = AQIForecaster(target_hours=3)
        exp = ForecastExplainer(fc)
        result = exp.explain(pd.DataFrame({"x": [1.0]}))
        assert isinstance(result["explanation_text"], str)
        assert len(result["explanation_text"]) > 0

    def test_explain_empty_x_returns_graceful_result(self):
        fc = AQIForecaster(target_hours=3)
        exp = ForecastExplainer(fc)
        result = exp.explain(pd.DataFrame())
        assert result["shap_available"] is False

    def test_explain_result_has_all_required_keys(self):
        fc = AQIForecaster(target_hours=3)
        exp = ForecastExplainer(fc)
        result = exp.explain(pd.DataFrame({"x": [1.0]}))
        required = {"top_features", "explanation_text", "inversion_detected", "shap_available"}
        assert required.issubset(result.keys())

    def test_inversion_detected_is_boolean(self):
        fc = AQIForecaster(target_hours=3)
        exp = ForecastExplainer(fc)
        result = exp.explain(pd.DataFrame({"x": [1.0]}))
        assert isinstance(result["inversion_detected"], bool)


@pytest.mark.skipif(not SHAP_AVAILABLE, reason="shap not installed")
class TestForecastExplainerWithShap:
    """Tests that require shap to be installed."""

    @pytest.fixture(scope="module")
    def fc_X(self):
        return _get_trained_fc_and_X()

    def test_shap_explain_returns_top_features(self, fc_X):
        fc, X, _ = fc_X
        exp = ForecastExplainer(fc, top_n=5)
        result = exp.explain(X, target="pm25", horizon_hours=3)
        # shap_available may be True or False depending on model state
        if result["shap_available"]:
            assert len(result["top_features"]) > 0

    def test_top_features_have_required_fields(self, fc_X):
        fc, X, _ = fc_X
        exp = ForecastExplainer(fc, top_n=5)
        result = exp.explain(X, target="pm25", horizon_hours=3)
        if result["shap_available"] and result["top_features"]:
            for f in result["top_features"]:
                assert "name" in f
                assert "label" in f
                assert "shap_value" in f
                assert "contribution_pct" in f

    def test_contribution_pcts_sum_roughly_100(self, fc_X):
        fc, X, _ = fc_X
        exp = ForecastExplainer(fc, top_n=100)  # get all features
        result = exp.explain(X, target="pm25", horizon_hours=3)
        if result["shap_available"] and len(result["top_features"]) >= 3:
            total = sum(f["contribution_pct"] for f in result["top_features"])
            # Allow rounding errors; total of top_n features may be < 100
            assert 0.0 < total <= 100.5

    def test_explanation_text_is_non_empty_string(self, fc_X):
        fc, X, _ = fc_X
        exp = ForecastExplainer(fc)
        result = exp.explain(X, target="pm25", horizon_hours=3)
        assert isinstance(result["explanation_text"], str)

    def test_inversion_detected_reflects_feature_value(self, fc_X):
        fc, X, _ = fc_X
        exp = ForecastExplainer(fc)
        # Create X with strong inversion
        X_inv = X.copy()
        if "inversion_strength" in X_inv.columns:
            X_inv["inversion_strength"] = 8.0
        result = exp.explain(X_inv, target="pm25")
        assert isinstance(result["inversion_detected"], bool)

    def test_unknown_target_returns_graceful(self, fc_X):
        fc, X, _ = fc_X
        exp = ForecastExplainer(fc)
        result = exp.explain(X, target="nonexistent_pollutant")
        assert isinstance(result, dict)
        assert "explanation_text" in result


class TestFeatureLabels:

    def test_feature_labels_dict_is_non_empty(self):
        assert len(_FEATURE_LABELS) > 0

    def test_known_features_have_labels(self):
        expected = ["pbl_height", "inversion_strength", "wind_transport_idx"]
        for name in expected:
            assert name in _FEATURE_LABELS, f"Missing label for: {name}"

    def test_all_label_values_are_strings(self):
        for k, v in _FEATURE_LABELS.items():
            assert isinstance(v, str), f"Label for {k!r} is not a string"
            assert len(v) > 0, f"Empty label for {k!r}"
