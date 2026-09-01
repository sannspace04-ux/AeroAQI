"""
tests/unit/test_feature_engineer.py
======================================
Unit tests for src/processing/feature_engineer.py

All input data is SYNTHETIC/DEMO — not real observations.
No network calls or file I/O.

Run with:
    pytest tests/unit/test_feature_engineer.py -v
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from src.processing.feature_engineer import FeatureEngineer


# ---------------------------------------------------------------------------
# Synthetic test helpers
# NOTE: All values below are SYNTHETIC/DEMO data for testing only.
# ---------------------------------------------------------------------------

def _row(**kwargs) -> dict:
    """Build one synthetic observation row with sensible defaults."""
    defaults = {
        "timestamp_utc": pd.Timestamp("2023-10-15 06:00:00", tz="UTC"),
        "station_id": "DEL_ITO",
        "latitude": 28.6289,
        "longitude": 77.2412,
        "data_source": "test",
        "temperature": 25.0,
        "temp_850hpa": 22.0,
        "temp_925hpa": 24.0,
        "temp_700hpa": 15.0,
        "pbl_height": 500.0,
        "wind_speed": 3.0,
        "wind_direction": 315.0,    # NW — maximum transport risk
        "fire_distance_km": 250.0,
        "total_frp_300km": 500.0,
        "pm25": 75.0,
        "pm10": 150.0,
    }
    defaults.update(kwargs)
    return defaults


def _df(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows) if rows else [_row()])


# ===========================================================================
# Inversion detection
# ===========================================================================

class TestComputeInversion:

    @pytest.fixture
    def fe(self):
        return FeatureEngineer(inversion_threshold_c=2.0)

    def test_no_inversion_when_temp850_lower(self, fe):
        # temp_850hpa (22) < temperature (25) → no inversion
        df = _df(_row(temperature=25.0, temp_850hpa=22.0))
        result = fe.compute_inversion(df)
        assert result["inversion_flag"].iloc[0] == False
        assert result["inversion_strength"].iloc[0] < 0

    def test_inversion_when_temp850_higher_than_threshold(self, fe):
        # temp_850hpa (30) > temperature (25) + 2 → inversion
        df = _df(_row(temperature=25.0, temp_850hpa=30.0))
        result = fe.compute_inversion(df)
        assert result["inversion_flag"].iloc[0] == True
        assert abs(result["inversion_strength"].iloc[0] - 5.0) < 1e-9

    def test_exactly_at_threshold_not_inverted(self, fe):
        # strength = 2.0, threshold = 2.0 → NOT inverted (not strictly greater)
        df = _df(_row(temperature=25.0, temp_850hpa=27.0))
        result = fe.compute_inversion(df)
        assert result["inversion_flag"].iloc[0] == False

    def test_just_above_threshold_is_inverted(self, fe):
        df = _df(_row(temperature=25.0, temp_850hpa=27.01))
        result = fe.compute_inversion(df)
        assert result["inversion_flag"].iloc[0] == True

    def test_nan_temperature_gives_nan_strength(self, fe):
        df = _df(_row(temperature=float("nan"), temp_850hpa=22.0))
        result = fe.compute_inversion(df)
        assert math.isnan(result["inversion_strength"].iloc[0])

    def test_nan_temp_850hpa_gives_nan_strength(self, fe):
        df = _df(_row(temperature=25.0, temp_850hpa=float("nan")))
        result = fe.compute_inversion(df)
        assert math.isnan(result["inversion_strength"].iloc[0])

    def test_missing_column_does_not_raise(self, fe):
        df = pd.DataFrame([{"temperature": 25.0}])   # no temp_850hpa
        result = fe.compute_inversion(df)
        assert "inversion_strength" in result.columns
        assert result["inversion_strength"].isna().all()

    def test_inversion_strength_formula(self, fe):
        df = _df(_row(temperature=20.0, temp_850hpa=26.0))
        result = fe.compute_inversion(df)
        # strength = 26 - 20 = 6.0
        assert abs(result["inversion_strength"].iloc[0] - 6.0) < 1e-9

    def test_not_overwriting_existing_value(self, fe):
        df = _df(_row(temperature=25.0, temp_850hpa=30.0))
        df["inversion_strength"] = 99.0  # pre-existing value
        # compute_inversion overwrites regardless (re-computation)
        result = fe.compute_inversion(df)
        # Value should be recomputed (5.0), not preserved (99.0)
        assert abs(result["inversion_strength"].iloc[0] - 5.0) < 1e-9


# ===========================================================================
# Temperature profile
# ===========================================================================

class TestComputeTemperatureProfile:

    @pytest.fixture
    def fe(self):
        return FeatureEngineer()

    def test_profile_is_valid_json(self, fe):
        df = _df(_row())
        result = fe.compute_temperature_profile(df)
        profile_str = result["temperature_profile"].iloc[0]
        assert isinstance(profile_str, str)
        parsed = json.loads(profile_str)
        assert isinstance(parsed, dict)

    def test_profile_contains_expected_levels(self, fe):
        df = _df(_row(
            temperature=25.0,
            temp_925hpa=24.0,
            temp_850hpa=22.0,
            temp_700hpa=15.0,
        ))
        result = fe.compute_temperature_profile(df)
        parsed = json.loads(result["temperature_profile"].iloc[0])
        assert "1013" in parsed
        assert "925" in parsed
        assert "850" in parsed
        assert "700" in parsed

    def test_profile_values_correct(self, fe):
        df = _df(_row(
            temperature=28.5,
            temp_850hpa=22.1,
        ))
        result = fe.compute_temperature_profile(df)
        parsed = json.loads(result["temperature_profile"].iloc[0])
        assert abs(parsed["1013"] - 28.5) < 0.01
        assert abs(parsed["850"] - 22.1) < 0.01

    def test_nan_levels_omitted_from_profile(self, fe):
        df = _df(_row(
            temperature=25.0,
            temp_925hpa=float("nan"),
            temp_850hpa=22.0,
            temp_700hpa=float("nan"),
        ))
        result = fe.compute_temperature_profile(df)
        parsed = json.loads(result["temperature_profile"].iloc[0])
        assert "925" not in parsed
        assert "700" not in parsed
        assert "850" in parsed

    def test_all_nan_levels_gives_nan_profile(self, fe):
        df = _df(_row(
            temperature=float("nan"),
            temp_925hpa=float("nan"),
            temp_850hpa=float("nan"),
            temp_700hpa=float("nan"),
        ))
        result = fe.compute_temperature_profile(df)
        assert result["temperature_profile"].isna().iloc[0]

    def test_no_level_columns_gives_nan(self, fe):
        df = pd.DataFrame([{"station_id": "X", "pm25": 50.0}])
        result = fe.compute_temperature_profile(df)
        assert "temperature_profile" in result.columns
        assert result["temperature_profile"].isna().all()


# ===========================================================================
# Mixing volume
# ===========================================================================

class TestComputeMixingVolume:

    @pytest.fixture
    def fe(self):
        return FeatureEngineer()

    def test_basic_formula(self, fe):
        # MVI = 500 m × 3 m/s = 1500 m²/s
        df = _df(_row(pbl_height=500.0, wind_speed=3.0))
        result = fe.compute_mixing_volume(df)
        assert abs(result["mixing_volume_idx"].iloc[0] - 1500.0) < 1e-9

    def test_zero_pbl_gives_zero(self, fe):
        df = _df(_row(pbl_height=0.0, wind_speed=5.0))
        result = fe.compute_mixing_volume(df)
        assert result["mixing_volume_idx"].iloc[0] == 0.0

    def test_zero_wind_gives_zero(self, fe):
        df = _df(_row(pbl_height=800.0, wind_speed=0.0))
        result = fe.compute_mixing_volume(df)
        assert result["mixing_volume_idx"].iloc[0] == 0.0

    def test_nan_pbl_gives_nan(self, fe):
        df = _df(_row(pbl_height=float("nan"), wind_speed=5.0))
        result = fe.compute_mixing_volume(df)
        assert math.isnan(result["mixing_volume_idx"].iloc[0])

    def test_nan_wind_gives_nan(self, fe):
        df = _df(_row(pbl_height=500.0, wind_speed=float("nan")))
        result = fe.compute_mixing_volume(df)
        assert math.isnan(result["mixing_volume_idx"].iloc[0])

    def test_missing_column_does_not_raise(self, fe):
        df = pd.DataFrame([{"pbl_height": 500.0}])   # no wind_speed
        result = fe.compute_mixing_volume(df)
        assert "mixing_volume_idx" in result.columns
        assert result["mixing_volume_idx"].isna().all()


# ===========================================================================
# Wind transport index
# ===========================================================================

class TestComputeWindTransport:

    @pytest.fixture
    def fe(self):
        return FeatureEngineer()

    def test_nw_wind_gives_max_score(self, fe):
        df = _df(_row(wind_direction=315.0))
        result = fe.compute_wind_transport(df)
        assert abs(result["wind_transport_idx"].iloc[0] - 1.0) < 1e-9

    def test_se_wind_gives_min_score(self, fe):
        df = _df(_row(wind_direction=135.0))
        result = fe.compute_wind_transport(df)
        assert abs(result["wind_transport_idx"].iloc[0] - 0.0) < 1e-9

    def test_score_in_0_1_range(self, fe):
        df = pd.DataFrame([_row(wind_direction=d) for d in range(0, 360, 10)])
        result = fe.compute_wind_transport(df)
        assert (result["wind_transport_idx"] >= 0.0).all()
        assert (result["wind_transport_idx"] <= 1.0).all()

    def test_nan_wind_gives_nan(self, fe):
        df = _df(_row(wind_direction=float("nan")))
        result = fe.compute_wind_transport(df)
        assert math.isnan(result["wind_transport_idx"].iloc[0])

    def test_missing_column_does_not_raise(self, fe):
        df = pd.DataFrame([{"station_id": "X", "pm25": 50.0}])
        result = fe.compute_wind_transport(df)
        assert "wind_transport_idx" in result.columns


# ===========================================================================
# Fire transport risk
# ===========================================================================

class TestComputeFireTransportRisk:

    @pytest.fixture
    def fe(self):
        return FeatureEngineer()

    def test_high_risk_scenario(self, fe):
        # NW wind (1.0) + nearby fire (low distance) + high FRP
        df = _df(_row(
            wind_transport_idx=1.0,
            fire_distance_km=50.0,
            total_frp_300km=5000.0,
        ))
        result = fe.compute_fire_transport_risk(df)
        score = result["fire_transport_risk"].iloc[0]
        assert score > 0.7

    def test_low_risk_scenario(self, fe):
        # SE wind (0.0) + distant fire + low FRP
        df = _df(_row(
            wind_transport_idx=0.0,
            fire_distance_km=2000.0,
            total_frp_300km=0.0,
        ))
        result = fe.compute_fire_transport_risk(df)
        score = result["fire_transport_risk"].iloc[0]
        assert score < 0.2

    def test_score_always_in_0_1(self, fe):
        df = pd.DataFrame([
            _row(wind_transport_idx=0.0, fire_distance_km=3000.0, total_frp_300km=0.0),
            _row(wind_transport_idx=1.0, fire_distance_km=10.0, total_frp_300km=10000.0),
            _row(wind_transport_idx=0.5, fire_distance_km=300.0, total_frp_300km=500.0),
        ])
        result = fe.compute_fire_transport_risk(df)
        assert (result["fire_transport_risk"] >= 0.0).all()
        assert (result["fire_transport_risk"] <= 1.0).all()

    def test_all_nan_inputs_give_nan(self, fe):
        df = _df(_row(
            wind_transport_idx=float("nan"),
            fire_distance_km=float("nan"),
            total_frp_300km=float("nan"),
        ))
        result = fe.compute_fire_transport_risk(df)
        assert math.isnan(result["fire_transport_risk"].iloc[0])

    def test_partial_nan_still_computes(self, fe):
        # Only wind_transport_idx available, others NaN
        df = _df(_row(
            wind_transport_idx=0.8,
            fire_distance_km=float("nan"),
            total_frp_300km=float("nan"),
        ))
        result = fe.compute_fire_transport_risk(df)
        score = result["fire_transport_risk"].iloc[0]
        assert not math.isnan(score)
        assert 0.0 <= score <= 1.0


# ===========================================================================
# AQI computation
# ===========================================================================

class TestComputeAqi:

    @pytest.fixture
    def fe(self):
        return FeatureEngineer()

    def test_basic_aqi_from_pm25_pm10(self, fe):
        df = _df(_row(pm25=45.0, pm10=90.0))
        result = fe.compute_aqi(df)
        assert not math.isnan(result["aqi_computed"].iloc[0])
        assert result["aqi_computed"].iloc[0] > 0

    def test_zero_pm_gives_zero_aqi(self, fe):
        df = _df(_row(pm25=0.0, pm10=0.0))
        result = fe.compute_aqi(df)
        assert result["aqi_computed"].iloc[0] == 0.0

    def test_existing_aqi_not_overwritten(self, fe):
        df = _df(_row(pm25=45.0, pm10=90.0))
        df["aqi_computed"] = 99.9
        result = fe.compute_aqi(df)
        # existing value should NOT be overwritten
        assert result["aqi_computed"].iloc[0] == 99.9

    def test_fills_nan_aqi_with_computed(self, fe):
        df = _df(_row(pm25=60.0, pm10=100.0))
        df["aqi_computed"] = float("nan")   # explicitly NaN → should fill
        result = fe.compute_aqi(df)
        assert not math.isnan(result["aqi_computed"].iloc[0])

    def test_both_pm_nan_gives_nan(self, fe):
        df = _df(_row(pm25=float("nan"), pm10=float("nan")))
        result = fe.compute_aqi(df)
        assert math.isnan(result["aqi_computed"].iloc[0])

    def test_missing_pm_columns(self, fe):
        df = pd.DataFrame([{"station_id": "X", "temperature": 28.0}])
        result = fe.compute_aqi(df)
        assert "aqi_computed" in result.columns


# ===========================================================================
# compute_all (integration)
# ===========================================================================

class TestComputeAll:

    @pytest.fixture
    def fe(self):
        return FeatureEngineer()

    def test_compute_all_returns_dataframe(self, fe):
        df = _df(_row())
        result = fe.compute_all(df)
        assert isinstance(result, pd.DataFrame)

    def test_compute_all_empty_df(self, fe):
        result = fe.compute_all(pd.DataFrame())
        assert isinstance(result, pd.DataFrame)

    def test_all_derived_columns_present(self, fe):
        df = _df(_row())
        result = fe.compute_all(df)
        for col in [
            "inversion_flag", "inversion_strength", "temperature_profile",
            "wind_transport_idx", "mixing_volume_idx",
            "fire_transport_risk", "aqi_computed",
        ]:
            assert col in result.columns, f"Missing derived column: {col}"

    def test_original_columns_not_dropped(self, fe):
        df = _df(_row())
        result = fe.compute_all(df)
        for col in ["pm25", "pm10", "temperature", "wind_speed", "pbl_height"]:
            assert col in result.columns

    def test_no_rows_dropped(self, fe):
        df = pd.DataFrame([_row() for _ in range(5)])
        result = fe.compute_all(df)
        assert len(result) == 5

    def test_idempotent_second_call(self, fe):
        df = _df(_row())
        result1 = fe.compute_all(df)
        result2 = fe.compute_all(result1)
        # aqi_computed should NOT be changed on second call (it's already filled)
        assert abs(
            result1["aqi_computed"].iloc[0] - result2["aqi_computed"].iloc[0]
        ) < 1e-9
