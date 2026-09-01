"""
tests/unit/test_validators.py
==============================
Unit tests for src/utils/validators.py

These tests run entirely in memory with no network calls or file I/O.
They verify every validation function independently.

Run with:
    pytest tests/unit/test_validators.py -v
"""

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src.utils.validators import (
    check_completeness,
    check_required_columns,
    normalise_timestamps,
    remove_duplicates,
    run_all_validations,
    validate_coordinates,
    validate_physical_ranges,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(**kwargs) -> pd.DataFrame:
    """Build a small DataFrame from keyword columns for testing."""
    return pd.DataFrame(kwargs)


def _minimal_obs_df(n: int = 3) -> pd.DataFrame:
    """
    Return a small DataFrame that passes all required-column checks.
    Values are all within valid physical ranges.
    """
    return _make_df(
        timestamp_utc=[
            "2023-10-15T00:00:00Z",
            "2023-10-15T01:00:00Z",
            "2023-10-15T02:00:00Z",
        ][:n],
        station_id=["DEL_ITO", "DEL_ITO", "DEL_ITO"][:n],
        station_name=["ITO", "ITO", "ITO"][:n],
        latitude=[28.6289, 28.6289, 28.6289][:n],
        longitude=[77.2412, 77.2412, 77.2412][:n],
        data_source=["openaq", "openaq", "openaq"][:n],
        pm25=[45.2, 67.8, 120.1][:n],
    )


# ===========================================================================
# 1. check_required_columns
# ===========================================================================

class TestCheckRequiredColumns:

    def test_all_present_returns_empty_list(self):
        df = _minimal_obs_df()
        errors = check_required_columns(df, required=["timestamp_utc", "station_id"])
        assert errors == []

    def test_missing_column_returns_error_message(self):
        df = pd.DataFrame({"timestamp_utc": ["2023-01-01T00:00:00Z"]})
        errors = check_required_columns(df, required=["timestamp_utc", "station_id"])
        assert len(errors) == 1
        assert "station_id" in errors[0]

    def test_multiple_missing_columns(self):
        df = pd.DataFrame({"col_a": [1]})
        errors = check_required_columns(df, required=["timestamp_utc", "station_id", "latitude"])
        assert len(errors) == 1  # one message listing all missing
        for col in ["timestamp_utc", "station_id", "latitude"]:
            assert col in errors[0]

    def test_empty_dataframe_with_columns_present(self):
        df = pd.DataFrame(columns=["timestamp_utc", "station_id"])
        errors = check_required_columns(df, required=["timestamp_utc", "station_id"])
        assert errors == []


# ===========================================================================
# 2. normalise_timestamps
# ===========================================================================

class TestNormaliseTimestamps:

    def test_iso_string_converts_to_utc(self):
        df = _make_df(timestamp_utc=["2023-10-15T06:30:00Z"])
        df_out, issues = normalise_timestamps(df)
        assert pd.api.types.is_datetime64_any_dtype(df_out["timestamp_utc"])
        # pandas 2+ stores UTC as datetime.timezone.utc; pandas 1.x had .tz.zone
        tz = df_out["timestamp_utc"].dt.tz
        tz_name = getattr(tz, "zone", None) or str(tz)
        assert "UTC" in tz_name.upper()
        assert not issues

    def test_timestamps_truncated_to_hour(self):
        df = _make_df(timestamp_utc=["2023-10-15T06:37:22Z", "2023-10-15T06:59:59Z"])
        df_out, _ = normalise_timestamps(df)
        # Both should be truncated to 06:00
        assert df_out["timestamp_utc"].iloc[0].hour == 6
        assert df_out["timestamp_utc"].iloc[0].minute == 0
        assert df_out["timestamp_utc"].iloc[1].hour == 6

    def test_unparseable_timestamp_row_is_dropped(self):
        df = _make_df(timestamp_utc=["2023-10-15T06:00:00Z", "not_a_date", "also_bad"])
        df_out, issues = normalise_timestamps(df)
        assert len(df_out) == 1
        assert any("unparseable" in i for i in issues)

    def test_timezone_aware_input_converted_to_utc(self):
        # Simulate IST (UTC+5:30) timestamp
        df = _make_df(timestamp_utc=["2023-10-15T11:30:00+05:30"])
        df_out, _ = normalise_timestamps(df)
        # 11:30 IST = 06:00 UTC
        assert df_out["timestamp_utc"].iloc[0].hour == 6

    def test_missing_column_returns_error(self):
        df = pd.DataFrame({"other_col": [1]})
        _, issues = normalise_timestamps(df, timestamp_col="timestamp_utc")
        assert any("not found" in i for i in issues)

    def test_all_bad_timestamps_returns_empty_df(self):
        df = _make_df(timestamp_utc=["garbage", "trash", "rubbish"])
        df_out, issues = normalise_timestamps(df)
        assert df_out.empty
        assert any("unparseable" in i for i in issues)


# ===========================================================================
# 3. validate_coordinates
# ===========================================================================

class TestValidateCoordinates:

    def test_valid_delhi_coordinates_pass(self):
        df = _make_df(latitude=[28.6289], longitude=[77.2412])
        df_out, issues = validate_coordinates(df)
        assert len(df_out) == 1
        assert not issues

    def test_latitude_out_of_range_row_dropped(self):
        df = _make_df(latitude=[28.6, 10.0, 35.0], longitude=[77.2, 77.2, 77.2])
        df_out, issues = validate_coordinates(df, lat_bounds=(23.0, 32.0))
        # 10.0 and 35.0 are out of [23, 32]
        assert len(df_out) == 1
        assert df_out["latitude"].iloc[0] == 28.6
        assert any("latitude" in i for i in issues)

    def test_longitude_out_of_range_row_dropped(self):
        df = _make_df(latitude=[28.6, 28.6], longitude=[77.2, 90.0])
        df_out, issues = validate_coordinates(df, lon_bounds=(73.0, 80.0))
        assert len(df_out) == 1
        assert any("longitude" in i for i in issues)

    def test_non_numeric_coordinate_row_dropped(self):
        df = _make_df(latitude=["28.6", "bad_value"], longitude=[77.2, 77.2])
        df_out, issues = validate_coordinates(df)
        assert len(df_out) == 1

    def test_missing_lat_column_returns_issue(self):
        df = pd.DataFrame({"longitude": [77.2]})
        _, issues = validate_coordinates(df)
        assert any("latitude" in i for i in issues)


# ===========================================================================
# 4. validate_physical_ranges
# ===========================================================================

class TestValidatePhysicalRanges:

    def test_valid_pm25_unchanged(self):
        df = _make_df(pm25=[45.2, 120.5, 0.1])
        df_out, issues = validate_physical_ranges(df, columns=["pm25"])
        assert not df_out["pm25"].isna().any()
        assert not issues

    def test_negative_pm25_becomes_nan_not_zero(self):
        df = _make_df(pm25=[-5.0, 45.2])
        df_out, issues = validate_physical_ranges(df, columns=["pm25"])
        # First value must be NaN, NOT 0
        assert math.isnan(df_out["pm25"].iloc[0])
        assert df_out["pm25"].iloc[0] != 0.0
        assert any("pm25" in i for i in issues)

    def test_impossibly_high_pm25_becomes_nan(self):
        # valid_max for pm25 is 2000.0
        df = _make_df(pm25=[100.0, 9999.9])
        df_out, issues = validate_physical_ranges(df, columns=["pm25"])
        assert math.isnan(df_out["pm25"].iloc[1])
        assert df_out["pm25"].iloc[0] == 100.0

    def test_temperature_out_of_range_becomes_nan(self):
        # valid range: -10 to 55 °C
        df = _make_df(temperature=[28.5, 80.0, -20.0])
        df_out, issues = validate_physical_ranges(df, columns=["temperature"])
        assert df_out["temperature"].iloc[0] == 28.5
        assert math.isnan(df_out["temperature"].iloc[1])
        assert math.isnan(df_out["temperature"].iloc[2])

    def test_column_not_in_schema_is_ignored_gracefully(self):
        df = _make_df(some_unknown_column=[1, 2, 3])
        df_out, issues = validate_physical_ranges(df, columns=["some_unknown_column"])
        assert not issues   # no schema entry → no check → no error

    def test_nan_input_values_remain_nan(self):
        df = _make_df(pm25=[float("nan"), 45.2])
        df_out, issues = validate_physical_ranges(df, columns=["pm25"])
        assert math.isnan(df_out["pm25"].iloc[0])


# ===========================================================================
# 5. remove_duplicates
# ===========================================================================

class TestRemoveDuplicates:

    def test_no_duplicates_unchanged(self):
        df = _make_df(
            timestamp_utc=["2023-10-15T00:00:00Z", "2023-10-15T01:00:00Z"],
            station_id=["DEL_ITO", "DEL_ITO"],
        )
        df_out, issues = remove_duplicates(df)
        assert len(df_out) == 2
        assert not issues

    def test_exact_duplicate_keeps_first(self):
        df = _make_df(
            timestamp_utc=["2023-10-15T00:00:00Z"] * 3,
            station_id=["DEL_ITO"] * 3,
            pm25=[45.2, 50.0, 55.0],
        )
        df_out, issues = remove_duplicates(df)
        assert len(df_out) == 1
        assert df_out["pm25"].iloc[0] == 45.2   # first value kept
        assert any("duplicate" in i.lower() for i in issues)

    def test_different_stations_same_time_kept(self):
        df = _make_df(
            timestamp_utc=["2023-10-15T00:00:00Z", "2023-10-15T00:00:00Z"],
            station_id=["DEL_ITO", "DEL_ROHINI"],
        )
        df_out, issues = remove_duplicates(df)
        assert len(df_out) == 2
        assert not issues

    def test_fallback_to_latlon_key_when_station_id_absent(self):
        df = _make_df(
            timestamp_utc=["2023-10-15T00:00:00Z", "2023-10-15T00:00:00Z"],
            latitude=[28.6, 28.6],
            longitude=[77.2, 77.2],
        )
        df_out, issues = remove_duplicates(df)
        assert len(df_out) == 1


# ===========================================================================
# 6. check_completeness
# ===========================================================================

class TestCheckCompleteness:

    def test_fully_complete_column_no_warnings(self):
        df = _make_df(pm25=[45.2, 67.8, 120.1])
        warnings = check_completeness(df, columns=["pm25"], min_fraction=0.5)
        assert not warnings

    def test_half_null_column_below_threshold_warns(self):
        df = _make_df(pm25=[45.2, None, None, None])
        warnings = check_completeness(df, columns=["pm25"], min_fraction=0.5)
        assert any("pm25" in w for w in warnings)

    def test_empty_dataframe_warns(self):
        df = pd.DataFrame()
        warnings = check_completeness(df)
        assert any("empty" in w.lower() for w in warnings)

    def test_all_null_column_warns(self):
        df = _make_df(pm25=[None, None, None])
        warnings = check_completeness(df, columns=["pm25"], min_fraction=0.5)
        assert any("pm25" in w for w in warnings)


# ===========================================================================
# 7. run_all_validations (integration of all checks)
# ===========================================================================

class TestRunAllValidations:

    def test_clean_dataframe_passes(self):
        df = _minimal_obs_df()
        df_out, success = run_all_validations(df, "test_source")
        assert success is True
        assert len(df_out) > 0

    def test_empty_dataframe_fails(self):
        df = pd.DataFrame()
        df_out, success = run_all_validations(df, "test_source")
        assert success is False

    def test_missing_required_column_fails(self):
        df = pd.DataFrame({"some_col": [1, 2, 3]})
        df_out, success = run_all_validations(
            df, "test_source",
            required_columns=["timestamp_utc", "station_id"],
        )
        assert success is False

    def test_out_of_range_values_become_nan_not_zero(self):
        df = _minimal_obs_df()
        df["pm25"] = [-5.0, 45.2, 99999.0]
        df_out, success = run_all_validations(df, "test_source")
        # Out-of-range values must be NaN
        assert math.isnan(df_out["pm25"].iloc[0])
        assert math.isnan(df_out["pm25"].iloc[2])
        # In-range value must be preserved
        assert df_out["pm25"].iloc[1] == 45.2
        # success should still be True (range issues are warnings not errors)
        assert success is True

    def test_duplicates_removed_by_pipeline(self):
        df = _minimal_obs_df()
        # Add a duplicate of the first row
        dup = df.iloc[[0]].copy()
        df = pd.concat([df, dup], ignore_index=True)
        assert len(df) == 4
        df_out, success = run_all_validations(df, "test_source")
        assert len(df_out) == 3   # duplicate removed
        assert success is True

    def test_timestamps_normalised_to_utc_hour(self):
        df = _minimal_obs_df()
        df["timestamp_utc"] = [
            "2023-10-15T06:37:22Z",
            "2023-10-15T07:15:00Z",
            "2023-10-15T08:59:59Z",
        ]
        df_out, success = run_all_validations(df, "test_source")
        assert success is True
        hours = df_out["timestamp_utc"].dt.hour.tolist()
        assert hours == [6, 7, 8]
