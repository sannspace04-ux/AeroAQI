"""
tests/integration/conftest.py
==============================
Shared pytest fixtures for all integration tests.

Strategy
--------
- A fresh in-memory SQLite database is created for every test module.
- StaticPool is used so all SQLAlchemy connections share the same
  in-memory database (without it, each new connection gets a blank DB).
- The FastAPI dependency `get_db` is overridden to return a DBClient
  pointed at that in-memory DB.
- A small set of synthetic observations and fire detections is seeded
  with timestamps relative to *now* so they fall inside the default
  24/48 h look-back windows used by the API endpoints.
- No real API keys are needed — all external data is pre-seeded.
- `starlette.testclient.TestClient` (sync) is used so tests run without
  an async event loop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db
from src.api.main import create_app
from src.storage.db_client import Base, DBClient

# ---------------------------------------------------------------------------
# Seed timestamps — relative to now so they are always within the default
# query windows (e.g. last 48 h).  All three timestamps are in the past.
# ---------------------------------------------------------------------------
_NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
_T1 = _NOW - timedelta(hours=3)   # 3 h ago
_T2 = _NOW - timedelta(hours=2)   # 2 h ago
_T3 = _NOW - timedelta(hours=1)   # 1 h ago


# ---------------------------------------------------------------------------
# In-memory DB fixture — fresh for every test module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mem_db() -> DBClient:
    """
    Return a DBClient backed by a shared in-memory SQLite database.

    StaticPool forces every SQLAlchemy connection to reuse the same
    underlying sqlite3 connection, so all tables and rows are visible
    to every query — including those made through different engine
    connect() calls inside request handlers.

    Without StaticPool, `sqlite:///:memory:` creates a *new* blank
    database for each connection, so the seeded data would be invisible
    to the API handler's queries.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create all ORM tables on this engine
    Base.metadata.create_all(engine)

    # Build a DBClient that wraps our StaticPool engine instead of the
    # real file-based one.  We bypass __init__ to avoid creating a second
    # engine pointing at data/db/aeroaqi.db.
    db = DBClient.__new__(DBClient)
    db._engine = engine
    db._Session = sessionmaker(bind=engine)

    _seed(db)
    return db


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed(db: DBClient) -> None:
    """Populate the in-memory DB with minimal synthetic test data."""

    # ── Observations (combined AQ + Weather rows) ──────────────────────
    obs_rows = [
        _obs(_T1, "DEL_ITO",         28.6289, 77.2412, pm25=87.3,  pm10=142.1, temp=25.0, wind_dir=315.0, pbl=500.0),
        _obs(_T2, "DEL_ITO",         28.6289, 77.2412, pm25=95.1,  pm10=155.6, temp=24.5, wind_dir=310.0, pbl=450.0),
        _obs(_T3, "DEL_ITO",         28.6289, 77.2412, pm25=72.4,  pm10=130.0, temp=26.0, wind_dir=320.0, pbl=600.0),
        _obs(_T1, "DEL_ANAND_VIHAR", 28.6469, 77.3152, pm25=120.5, pm10=200.0, temp=26.0, wind_dir=305.0, pbl=480.0),
        _obs(_T2, "DEL_ANAND_VIHAR", 28.6469, 77.3152, pm25=130.8, pm10=215.3, temp=25.5, wind_dir=300.0, pbl=440.0),
        # Row with some NaN fields — realistic (not every sensor always reports)
        _obs(_T1, "NOI_SECTOR62",    28.6275, 77.3644, pm25=None,  pm10=180.0, temp=None, wind_dir=None,  pbl=None),
    ]
    db.write_observations(pd.DataFrame(obs_rows))

    # ── Fire detections ────────────────────────────────────────────────
    fire_rows = [
        _fire(_T1, 30.74, 76.79, frp=25.0, confidence="nominal"),
        _fire(_T1, 31.10, 75.50, frp=42.0, confidence="high"),
        _fire(_T2, 30.90, 76.20, frp=18.5, confidence="nominal"),
    ]
    db.write_fire_detections(pd.DataFrame(fire_rows))


def _obs(ts, station_id, lat, lon, pm25, pm10, temp, wind_dir, pbl,
         data_source="openaq") -> dict:
    return {
        "timestamp_utc": ts,
        "station_id":    station_id,
        "station_name":  station_id.replace("_", " ").title(),
        "latitude":      lat,
        "longitude":     lon,
        "data_source":   data_source,
        "pm25":          pm25,
        "pm10":          pm10,
        "o3":            45.0,
        "no2":           35.0,
        "so2":           12.0,
        "co":            1.2,
        "temperature":   temp,
        "wind_speed":    3.5,
        "wind_direction": wind_dir,
        "pbl_height":    pbl,
        "temp_850hpa":   22.0 if temp is not None else None,
    }


def _fire(ts, lat, lon, frp, confidence) -> dict:
    return {
        "timestamp_utc": ts,
        "latitude":      lat,
        "longitude":     lon,
        "frp":           frp,
        "confidence":    confidence,
        "satellite":     "N",
        "data_source":   "firms",
    }


# ---------------------------------------------------------------------------
# TestClient fixture — overrides get_db with in-memory DB
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client(mem_db: DBClient) -> TestClient:
    """
    Return a `TestClient` for the FastAPI app with the real DB
    dependency replaced by the in-memory test DB.
    """
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mem_db
    return TestClient(app, raise_server_exceptions=True)
