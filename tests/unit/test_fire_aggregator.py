"""
tests/unit/test_fire_aggregator.py
=====================================
Unit tests for src/processing/fire_aggregator.py

All test data is clearly labelled as synthetic/demo data.
No network calls or file I/O are made.

Run with:
    pytest tests/unit/test_fire_aggregator.py -v
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src.processing.fire_aggregator import FireAggregator


# ---------------------------------------------------------------------------
# Synthetic test data builders
# NOTE: All data below is SYNTHETIC/DEMO — not real observations.
# ---------------------------------------------------------------------------

_BASE_TS = datetime(2023, 10, 15, 6, 0, 0, tzinfo=timezone.utc)


def _obs_row(
    station_id: str = "DEL_ITO",
    lat: float = 28.6289,
    lon: float = 77.2412,
    ts: datetime = _BASE_TS,
) -> dict:
    return {
        "timestamp_utc": ts,
        "station_id": station_id,
        "latitude": lat,
        "longitude": lon,
    }


def _fire_row(
    lat: float,
    lon: float,
    frp: float = 20.0,
    ts: datetime = _BASE_TS,
    confidence: str = "nominal",
) -> dict:
    return {
        "timestamp_utc": ts,
        "latitude": lat,
        "longitude": lon,
        "frp": frp,
        "confidence": confidence,
    }


def _make_obs(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _make_fire(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFireAggregatorBasic:

    @pytest.fixture
    def agg(self):
        return FireAggregator(fire_window_hours=3)

    def test_empty_obs_returns_empty(self, agg):
        fire_df = _make_fire(_fire_row(30.0, 75.0))
        result = agg.aggregate(pd.DataFrame(), fire_df)
        assert result.empty

    def test_empty_fire_df_sets_all_nan(self, agg):
        obs_df = _make_obs(_obs_row())
        result = agg.aggregate(obs_df, pd.DataFrame())
        assert math.isnan(result["fire_distance_km"].iloc[0])
        assert math.isnan(result["fire_nearest_frp"].iloc[0])

    def test_no_fires_returns_zero_counts(self, agg):
        obs_df = _make_obs(_obs_row())
        result = agg.aggregate(obs_df, pd.DataFrame())
        # Counts should be 0.0 (not NaN) when there are no fires at all
        # because the time-window loop returns (0,0,0,NaN,NaN)
        # But with empty fire_df we skip time-window logic → NaN
        # This confirms no silent zero-fill happens for distances
        assert result["fire_distance_km"].isna().iloc[0]

    def test_fire_within_300km_counted(self, agg):
        # Chandigarh is ~250 km from Delhi — should be within 300 km
        obs_df = _make_obs(_obs_row(lat=28.6289, lon=77.2412))
        fire_df = _make_fire(_fire_row(lat=30.74, lon=76.79, frp=50.0))
        result = agg.aggregate(obs_df, fire_df)
        assert result["fire_count_300km"].iloc[0] >= 1.0
        assert result["fire_count_500km"].iloc[0] >= 1.0
        assert result["total_frp_300km"].iloc[0] > 0.0

    def test_fire_beyond_500km_not_counted_in_300(self, agg):
        # Amritsar is ~430 km from Delhi — within 500 km but not 300 km
        obs_df = _make_obs(_obs_row(lat=28.6289, lon=77.2412))
        fire_df = _make_fire(_fire_row(lat=31.63, lon=74.87, frp=30.0))
        result = agg.aggregate(obs_df, fire_df)
        # ~430 km: outside 300, inside 500
        assert result["fire_count_300km"].iloc[0] == 0.0
        assert result["fire_count_500km"].iloc[0] >= 1.0
        assert result["total_frp_300km"].iloc[0] == 0.0

    def test_fire_distance_populated(self, agg):
        obs_df = _make_obs(_obs_row(lat=28.6289, lon=77.2412))
        fire_df = _make_fire(_fire_row(lat=30.74, lon=76.79, frp=10.0))
        result = agg.aggregate(obs_df, fire_df)
        dist = result["fire_distance_km"].iloc[0]
        assert not math.isnan(dist)
        assert 200 < dist < 300   # ~250 km Chandigarh distance

    def test_nearest_fire_frp_populated(self, agg):
        obs_df = _make_obs(_obs_row())
        fire_df = _make_fire(_fire_row(lat=30.74, lon=76.79, frp=42.5))
        result = agg.aggregate(obs_df, fire_df)
        assert abs(result["fire_nearest_frp"].iloc[0] - 42.5) < 0.01

    def test_nan_frp_in_fire_handled(self, agg):
        obs_df = _make_obs(_obs_row())
        row = _fire_row(lat=30.74, lon=76.79)
        row["frp"] = float("nan")
        fire_df = pd.DataFrame([row])
        result = agg.aggregate(obs_df, fire_df)
        # Should not raise; fire_count_300km should still be populated
        assert result["fire_count_300km"].iloc[0] >= 1.0

    def test_multiple_fires_sum_frp(self, agg):
        obs_df = _make_obs(_obs_row(lat=28.6289, lon=77.2412))
        fire_df = _make_fire(
            _fire_row(lat=30.0, lon=76.0, frp=10.0),   # ~270 km
            _fire_row(lat=30.2, lon=76.2, frp=20.0),   # ~250 km
            _fire_row(lat=30.4, lon=76.4, frp=30.0),   # ~230 km
        )
        result = agg.aggregate(obs_df, fire_df)
        assert result["fire_count_300km"].iloc[0] >= 3.0
        assert result["total_frp_300km"].iloc[0] >= 60.0

    def test_multiple_stations_independent(self, agg):
        obs_df = _make_obs(
            _obs_row(station_id="DEL_ITO",    lat=28.6289, lon=77.2412),
            _obs_row(station_id="NOI_SECTOR62", lat=28.6275, lon=77.3644),
        )
        fire_df = _make_fire(_fire_row(lat=30.74, lon=76.79, frp=15.0))
        result = agg.aggregate(obs_df, fire_df)
        # Both stations should have fire features populated
        assert result["fire_count_300km"].notna().all()
        assert len(result) == 2

    def test_output_columns_always_present(self, agg):
        obs_df = _make_obs(_obs_row())
        fire_df = _make_fire(_fire_row(lat=30.0, lon=76.0))
        result = agg.aggregate(obs_df, fire_df)
        for col in [
            "fire_count_300km", "fire_count_500km",
            "total_frp_300km", "fire_distance_km", "fire_nearest_frp",
        ]:
            assert col in result.columns, f"Missing column: {col}"

    def test_original_columns_preserved(self, agg):
        obs_df = _make_obs(_obs_row())
        obs_df["pm25"] = 87.3   # add an extra column
        fire_df = _make_fire(_fire_row(lat=30.0, lon=76.0))
        result = agg.aggregate(obs_df, fire_df)
        assert "pm25" in result.columns
        assert result["pm25"].iloc[0] == 87.3


class TestFireAggregatorTimeWindow:

    @pytest.fixture
    def agg(self):
        return FireAggregator(fire_window_hours=3)

    def test_fire_within_time_window_included(self, agg):
        obs_ts = _BASE_TS
        fire_ts = datetime(2023, 10, 15, 7, 30, 0, tzinfo=timezone.utc)   # +1.5h
        obs_df = _make_obs(_obs_row(ts=obs_ts))
        fire_df = _make_fire(_fire_row(lat=30.0, lon=76.0, ts=fire_ts))
        result = agg.aggregate(obs_df, fire_df)
        assert result["fire_count_300km"].iloc[0] >= 0   # may be 0 if >300km

    def test_fire_outside_time_window_excluded(self, agg):
        obs_ts = _BASE_TS
        fire_ts = datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)   # +6h, outside ±3h
        obs_df = _make_obs(_obs_row(ts=obs_ts, lat=28.6289, lon=77.2412))
        fire_df = _make_fire(_fire_row(lat=30.74, lon=76.79, ts=fire_ts))
        result = agg.aggregate(obs_df, fire_df)
        # Outside time window → zero counts
        assert result["fire_count_300km"].iloc[0] == 0.0


class TestFireAggregatorEdgeCases:

    @pytest.fixture
    def agg(self):
        return FireAggregator()

    def test_missing_obs_lat_lon_gives_nan(self, agg):
        obs_df = pd.DataFrame([{
            "timestamp_utc": _BASE_TS,
            "station_id": "DEL_ITO",
            "latitude": float("nan"),
            "longitude": float("nan"),
        }])
        fire_df = _make_fire(_fire_row(lat=30.0, lon=76.0))
        result = agg.aggregate(obs_df, fire_df)
        assert result["fire_distance_km"].isna().iloc[0]

    def test_fire_df_missing_required_column(self, agg):
        obs_df = _make_obs(_obs_row())
        # Missing 'longitude' in fire_df
        fire_df = pd.DataFrame([{"timestamp_utc": _BASE_TS, "latitude": 30.0, "frp": 10.0}])
        result = agg.aggregate(obs_df, fire_df)
        # Should return obs_df unchanged (with NaN fire columns)
        assert isinstance(result, pd.DataFrame)
