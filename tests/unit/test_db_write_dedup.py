"""
tests/unit/test_db_write_dedup.py
===================================
Verifies that write_observations is truly idempotent (INSERT OR IGNORE):
re-writing the same rows a second time must not create duplicates.

Run with:
    pytest tests/unit/test_db_write_dedup.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.storage.db_client import Base, DBClient


# ---------------------------------------------------------------------------
# Fixture: fresh in-memory DB for each test
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_db():
    """Create an empty in-memory DBClient with the full schema."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = DBClient.__new__(DBClient)
    db._engine = engine
    db._Session = sessionmaker(bind=engine)
    db.migrate_schema()   # creates the unique index
    return db


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _row(ts, station_id, pm25=80.0):
    return {
        "timestamp_utc": ts,
        "station_id": station_id,
        "station_name": station_id,
        "data_source": "openaq",
        "pm25": pm25,
        "latitude": 28.6,
        "longitude": 77.2,
    }


_T1 = datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
_T2 = datetime(2023, 10, 15, 13, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWriteObservationsDedup:

    def test_first_write_inserts_rows(self, clean_db):
        df = pd.DataFrame([_row(_T1, "DEL_ITO"), _row(_T2, "DEL_ITO")])
        inserted = clean_db.write_observations(df)
        assert inserted == 2

    def test_second_identical_write_inserts_zero(self, clean_db):
        df = pd.DataFrame([_row(_T1, "DEL_ITO"), _row(_T2, "DEL_ITO")])
        clean_db.write_observations(df)
        # Write exactly the same rows again
        inserted = clean_db.write_observations(df)
        assert inserted == 0, (
            f"Expected 0 duplicates inserted, got {inserted}"
        )

    def test_total_row_count_unchanged_after_re_write(self, clean_db):
        df = pd.DataFrame([_row(_T1, "DEL_ITO"), _row(_T2, "DEL_ITO")])
        clean_db.write_observations(df)
        clean_db.write_observations(df)
        count = clean_db._count_rows("observations")
        assert count == 2, f"Expected 2 rows, found {count}"

    def test_new_station_gets_inserted_even_after_dedup(self, clean_db):
        df1 = pd.DataFrame([_row(_T1, "DEL_ITO")])
        df2 = pd.DataFrame([_row(_T1, "DEL_ROHINI")])
        clean_db.write_observations(df1)
        inserted = clean_db.write_observations(df2)
        assert inserted == 1

    def test_partial_overlap_inserts_only_new_rows(self, clean_db):
        df_first = pd.DataFrame([_row(_T1, "DEL_ITO"), _row(_T2, "DEL_ITO")])
        df_second = pd.DataFrame([
            _row(_T1, "DEL_ITO"),        # duplicate
            _row(_T2, "DEL_ITO"),        # duplicate
            _row(_T1, "DEL_ROHINI"),     # new station
        ])
        clean_db.write_observations(df_first)
        inserted = clean_db.write_observations(df_second)
        assert inserted == 1

    def test_different_data_source_treated_as_different_row(self, clean_db):
        """Same timestamp + station but different data_source → distinct row."""
        df_aq = pd.DataFrame([_row(_T1, "DEL_ITO")])
        df_weather = pd.DataFrame([{
            **_row(_T1, "DEL_ITO"),
            "data_source": "openmeteo",
        }])
        clean_db.write_observations(df_aq)
        inserted = clean_db.write_observations(df_weather)
        assert inserted == 1

    def test_empty_dataframe_returns_zero(self, clean_db):
        inserted = clean_db.write_observations(pd.DataFrame())
        assert inserted == 0

    def test_migrate_schema_idempotent(self, clean_db):
        """Calling migrate_schema twice must not raise."""
        added1 = clean_db.migrate_schema()
        added2 = clean_db.migrate_schema()
        # Both calls are fine; second should add nothing new
        assert isinstance(added1, list)
        assert isinstance(added2, list)
