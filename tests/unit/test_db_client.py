"""
tests/unit/test_db_client.py
=============================
Unit tests for DBClient using an in-memory SQLite database.

No files written to disk — each test gets a fresh in-memory DB.

Run with:
    pytest tests/unit/test_db_client.py -v
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from src.storage.db_client import DBClient


# ---------------------------------------------------------------------------
# Fixture: fresh in-memory database for every test
# ---------------------------------------------------------------------------

@pytest.fixture
def db() -> DBClient:
    """Return a DBClient backed by an in-memory SQLite database."""
    return DBClient(db_url="sqlite:///:memory:")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _obs_row(**overrides) -> dict:
    base = {
        "timestamp_utc": datetime(2023, 10, 15, 6, 0, 0, tzinfo=timezone.utc),
        "station_id": "DEL_ITO",
        "station_name": "ITO",
        "latitude": 28.6289,
        "longitude": 77.2412,
        "data_source": "openaq",
        "pm25": 87.3,
        "pm10": 142.1,
        "temperature": 28.5,
    }
    base.update(overrides)
    return base


def _make_obs_df(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# Tests: write_observations
# ---------------------------------------------------------------------------

class TestWriteObservations:

    def test_write_single_row(self, db):
        df = _make_obs_df(_obs_row())
        inserted = db.write_observations(df)
        assert inserted == 1

    def test_write_multiple_rows(self, db):
        df = _make_obs_df(
            _obs_row(timestamp_utc=datetime(2023, 10, 15, 6, tzinfo=timezone.utc)),
            _obs_row(timestamp_utc=datetime(2023, 10, 15, 7, tzinfo=timezone.utc)),
            _obs_row(timestamp_utc=datetime(2023, 10, 15, 8, tzinfo=timezone.utc)),
        )
        inserted = db.write_observations(df)
        assert inserted == 3

    def test_empty_dataframe_returns_zero(self, db):
        df = pd.DataFrame()
        inserted = db.write_observations(df)
        assert inserted == 0

    def test_missing_required_column_raises(self, db):
        df = pd.DataFrame({"pm25": [45.2]})   # no station_id, no timestamp
        with pytest.raises(ValueError, match="required columns"):
            db.write_observations(df)

    def test_nan_values_stored_as_null_not_zero(self, db):
        """NaN in pm25 should be stored as NULL, not 0."""
        import math
        row = _obs_row(pm25=float("nan"))
        df = _make_obs_df(row)
        db.write_observations(df)

        result = db.read_observations(station_id="DEL_ITO", columns=["pm25"])
        stored = result["pm25"].iloc[0]
        # Should be None/NaN, definitely not 0
        assert stored is None or (isinstance(stored, float) and math.isnan(stored))
        assert stored != 0


# ---------------------------------------------------------------------------
# Tests: read_observations
# ---------------------------------------------------------------------------

class TestReadObservations:

    def test_read_all_rows(self, db):
        df = _make_obs_df(
            _obs_row(timestamp_utc=datetime(2023, 10, 15, 6, tzinfo=timezone.utc)),
            _obs_row(
                station_id="DEL_ROHINI",
                timestamp_utc=datetime(2023, 10, 15, 6, tzinfo=timezone.utc)
            ),
        )
        db.write_observations(df)
        result = db.read_observations()
        assert len(result) == 2

    def test_filter_by_station_id(self, db):
        df = _make_obs_df(
            _obs_row(station_id="DEL_ITO",
                     timestamp_utc=datetime(2023, 10, 15, 6, tzinfo=timezone.utc)),
            _obs_row(station_id="DEL_ROHINI",
                     timestamp_utc=datetime(2023, 10, 15, 6, tzinfo=timezone.utc)),
        )
        db.write_observations(df)
        result = db.read_observations(station_id="DEL_ITO")
        assert len(result) == 1
        assert result["station_id"].iloc[0] == "DEL_ITO"

    def test_filter_by_time_range(self, db):
        df = _make_obs_df(
            _obs_row(station_id="DEL_ITO",
                     timestamp_utc=datetime(2023, 10, 14, 6, tzinfo=timezone.utc)),
            _obs_row(station_id="DEL_ITO",
                     timestamp_utc=datetime(2023, 10, 15, 6, tzinfo=timezone.utc)),
            _obs_row(station_id="DEL_ITO",
                     timestamp_utc=datetime(2023, 10, 16, 6, tzinfo=timezone.utc)),
        )
        db.write_observations(df)
        # Use naive datetimes for SQLite compatibility (SQLite stores without tz)
        result = db.read_observations(
            start_time=datetime(2023, 10, 15, 0, 0, 0),
            end_time=datetime(2023, 10, 15, 23, 59, 59),
        )
        assert len(result) == 1

    def test_returns_empty_df_when_no_match(self, db):
        result = db.read_observations(station_id="NONEXISTENT")
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ---------------------------------------------------------------------------
# Tests: write_fire_detections
# ---------------------------------------------------------------------------

class TestWriteFireDetections:

    def test_write_fire_rows(self, db):
        df = pd.DataFrame({
            "timestamp_utc": [datetime(2023, 10, 15, 6, tzinfo=timezone.utc)],
            "latitude": [30.12],
            "longitude": [75.56],
            "frp": [15.2],
            "confidence": ["nominal"],
            "satellite": ["N"],
            "data_source": ["firms"],
        })
        inserted = db.write_fire_detections(df)
        assert inserted == 1

    def test_empty_fire_df_returns_zero(self, db):
        inserted = db.write_fire_detections(pd.DataFrame())
        assert inserted == 0


# ---------------------------------------------------------------------------
# Tests: log_run / read_recent_ingestion_runs
# ---------------------------------------------------------------------------

class TestIngestionRunLog:

    def test_log_and_read_run(self, db):
        db.log_run("openaq", "success", rows_written=42, mode="realtime", duration_sec=5.3)
        df = db.read_recent_ingestion_runs(n=5)
        assert len(df) == 1
        assert df["source_name"].iloc[0] == "openaq"
        assert df["status"].iloc[0] == "success"
        assert df["rows_written"].iloc[0] == 42

    def test_multiple_runs_ordered_by_recent_first(self, db):
        db.log_run("openaq", "success", rows_written=10)
        db.log_run("openmeteo", "failed", rows_written=0)
        db.log_run("firms", "success", rows_written=5)
        df = db.read_recent_ingestion_runs(n=10)
        assert len(df) == 3
        # Most recent first
        assert df["source_name"].iloc[0] == "firms"

    def test_failed_run_stores_error_message(self, db):
        db.log_run(
            "era5", "failed",
            error_message="CDS API returned 503 Service Unavailable"
        )
        df = db.read_recent_ingestion_runs()
        assert "503" in (df["error_message"].iloc[0] or "")
