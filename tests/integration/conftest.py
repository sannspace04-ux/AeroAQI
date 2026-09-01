"""
tests/integration/conftest.py
==============================
Shared pytest fixtures for all integration tests.

Strategy
--------
- A fresh in-memory SQLite database is created for every test session.
- The FastAPI dependency `get_db` is overridden to return a DBClient
  pointed at that in-memory DB.
- A small set of synthetic observations and fire detections is seeded
  so every endpoint that queries the DB has something to return.
- No real API keys are needed — all external data is pre-seeded.
- The `httpx.TestClient` (sync) is used so tests run without an event loop.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db
from src.api.main import create_app
from src.storage.db_client import DBClient, Base

# ---------------------------------------------------------------------------
# Timestamps used across test fixtures
# ---------------------------------------------------------------------------
_T1 = datetime(2023, 10, 15, 6, 0, 0, tzinfo=timezone.utc)
_T2 = datetime(2023, 10, 15, 7, 0, 0, tzinfo=timezone.utc)
_T3 = datetime(2023, 10, 15, 8, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# In-memory DB fixture — fresh for every test module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mem_db() -> DBClient:
    """
    Return a DBClient backed by an in-memory SQLite database.
    Tables are created explicitly for this engine so the module-level
    SQLAlchemy metadata does not interfere with the real DB engine.
    Data is seeded once per module.
    """
    db = DBClient(db_url="sqlite:///:memory:")
    # Force-create ALL tables on this specific engine (handles metadata caching)
    Base.metadata.create_all(db.get_engine())
    _seed(db)
    return db


def _seed(db: DBClient) -> None:
    """Populate the in-memory DB with minimal synthetic test data."""
    # ── Observations (AQ + Weather combined rows) ──────────────────────
    obs_rows = [
        _obs(_T1, "DEL_ITO",        28.6289, 77.2412, pm25=87.3,  pm10=142.1, temp=25.0, wind_dir=315.0, pbl=500.0),
        _obs(_T2, "DEL_ITO",        28.6289, 77.2412, pm25=95.1,  pm10=155.6, temp=24.5, wind_dir=310.0, pbl=450.0),
        _obs(_T3, "DEL_ITO",        28.6289, 77.2412, pm25=72.4,  pm10=130.0, temp=26.0, wind_dir=320.0, pbl=600.0),
        _obs(_T1, "DEL_ANAND_VIHAR",28.6469, 77.3152, pm25=120.5, pm10=200.0, temp=26.0, wind_dir=305.0, pbl=480.0),
        _obs(_T2, "DEL_ANAND_VIHAR",28.6469, 77.3152, pm25=130.8, pm10=215.3, temp=25.5, wind_dir=300.0, pbl=440.0),
        # Row with some NaN fields (realistic — not every sensor always reports)
        _obs(_T1, "NOI_SECTOR62",   28.6275, 77.3644, pm25=None,  pm10=180.0, temp=None, wind_dir=None,  pbl=None),
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
        "station_id": station_id,
        "station_name": station_id.replace("_", " ").title(),
        "latitude": lat,
        "longitude": lon,
        "data_source": data_source,
        "pm25": pm25,
        "pm10": pm10,
        "o3": 45.0,
        "no2": 35.0,
        "so2": 12.0,
        "co": 1.2,
        "temperature": temp,
        "wind_speed": 3.5,
        "wind_direction": wind_dir,
        "pbl_height": pbl,
        "temp_850hpa": 22.0 if temp is not None else None,
    }


def _fire(ts, lat, lon, frp, confidence) -> dict:
    return {
        "timestamp_utc": ts,
        "latitude": lat,
        "longitude": lon,
        "frp": frp,
        "confidence": confidence,
        "satellite": "N",
        "data_source": "firms",
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
