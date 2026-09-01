"""
src/api/routers/observations.py
================================
Air quality observation endpoints.

All data comes from the 'observations' table via DBClient.read_observations().
Only air-quality columns are returned (weather/fire columns are on separate
endpoints for clarity and smaller payloads).

Endpoints
---------
GET /observations                     — paginated list with optional filters
GET /observations/latest              — most recent reading per station
GET /observations/{station_id}        — readings for one station
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.dependencies import DbDep
from src.api.schemas import AQIObservation, ObservationsResponse
from src.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/observations", tags=["Air Quality"])

# AQ columns to fetch — avoids pulling weather/fire columns from DB
_AQ_COLS = [
    "timestamp_utc", "station_id", "station_name",
    "latitude", "longitude", "data_source",
    "pm25", "pm10", "o3", "no2", "so2", "co",
    "aqi_raw", "aqi_computed",
]

_MAX_LIMIT = 1000
_DEFAULT_HOURS = 24


@router.get(
    "",
    response_model=ObservationsResponse,
    summary="List air quality observations",
    description=(
        "Returns hourly air quality observations for Delhi NCR stations. "
        "Defaults to the last 24 hours for all stations. "
        "Filter by station, time range, and/or limit the number of rows."
    ),
)
def list_observations(
    db: DbDep,
    station_id: Optional[str] = Query(
        None, description="Filter to a specific station ID, e.g. 'DEL_ITO'"
    ),
    start_time: Optional[str] = Query(
        None,
        description="UTC start datetime (ISO 8601), e.g. '2023-10-01T00:00:00'",
    ),
    end_time: Optional[str] = Query(
        None,
        description="UTC end datetime (ISO 8601), e.g. '2023-10-31T23:59:59'",
    ),
    hours: Optional[int] = Query(
        None,
        ge=1, le=720,
        description="Look-back window in hours (used when start_time is omitted). Default 24.",
    ),
    limit: int = Query(
        200, ge=1, le=_MAX_LIMIT,
        description=f"Maximum rows to return (max {_MAX_LIMIT}).",
    ),
) -> ObservationsResponse:
    start_dt, end_dt = _resolve_time_range(start_time, end_time, hours or _DEFAULT_HOURS)

    df = db.read_observations(
        station_id=station_id,
        start_time=start_dt,
        end_time=end_dt,
        # No columns filter — let DB return all; schema filters on serialisation
    )

    # Apply row limit (DB query already orders by timestamp ASC)
    if len(df) > limit:
        df = df.tail(limit)

    records = [AQIObservation.from_db_row(row) for row in df.to_dict(orient="records")]

    return ObservationsResponse(
        count=len(records),
        station_id=station_id,
        start_time=start_dt.isoformat(),
        end_time=end_dt.isoformat(),
        observations=records,
    )


@router.get(
    "/latest",
    response_model=ObservationsResponse,
    summary="Latest AQI reading per station",
    description=(
        "Returns the single most recent air quality reading for every "
        "Delhi NCR station that has data in the database. "
        "Useful for showing a live AQI map."
    ),
)
def latest_observations(db: DbDep) -> ObservationsResponse:
    """Return the most recent observation row for every station."""
    # Fetch last 48 h so we have data even if ingestion hasn't run recently
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=48)

    df = db.read_observations(start_time=start_dt, end_time=end_dt)

    if df.empty:
        return ObservationsResponse(count=0, observations=[])

    # Keep only the latest row per station
    import pandas as pd
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp_utc"])
    latest = df.sort_values("timestamp_utc").groupby("station_id").tail(1)

    records = [
        AQIObservation.from_db_row(row)
        for row in latest.to_dict(orient="records")
    ]
    return ObservationsResponse(count=len(records), observations=records)


@router.get(
    "/{station_id}",
    response_model=ObservationsResponse,
    summary="Air quality history for one station",
    description=(
        "Returns hourly AQI readings for a specific station. "
        "Defaults to the last 24 hours. "
        "Returns 404 if the station ID is unknown."
    ),
)
def station_observations(
    station_id: str,
    db: DbDep,
    start_time: Optional[str] = Query(None, description="UTC start (ISO 8601)"),
    end_time: Optional[str] = Query(None, description="UTC end (ISO 8601)"),
    hours: Optional[int] = Query(
        None, ge=1, le=720,
        description="Look-back window in hours. Default 24."
    ),
    limit: int = Query(200, ge=1, le=_MAX_LIMIT),
) -> ObservationsResponse:
    start_dt, end_dt = _resolve_time_range(start_time, end_time, hours or _DEFAULT_HOURS)

    df = db.read_observations(
        station_id=station_id,
        start_time=start_dt,
        end_time=end_dt,
    )

    if df.empty:
        # Distinguish "station not in config" vs "station has no data yet"
        from src.utils.config_loader import load_stations
        known_ids = {s["station_id"] for s in load_stations()}
        if station_id not in known_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Station '{station_id}' not found. Use GET /stations for valid IDs.",
            )
        # Station exists but has no data in the requested window
        return ObservationsResponse(
            count=0,
            station_id=station_id,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            observations=[],
        )

    if len(df) > limit:
        df = df.tail(limit)

    records = [AQIObservation.from_db_row(row) for row in df.to_dict(orient="records")]
    return ObservationsResponse(
        count=len(records),
        station_id=station_id,
        start_time=start_dt.isoformat(),
        end_time=end_dt.isoformat(),
        observations=records,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_time_range(
    start_str: Optional[str],
    end_str: Optional[str],
    default_lookback_hours: int,
) -> tuple[datetime, datetime]:
    """Parse optional ISO strings; fall back to now − N hours."""
    now = datetime.now(timezone.utc)
    try:
        end_dt = (
            datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)
            if end_str
            else now
        )
        start_dt = (
            datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
            if start_str
            else now - timedelta(hours=default_lookback_hours)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid datetime format: {exc}. Use ISO 8601, e.g. '2023-10-01T00:00:00'.",
        )
    if start_dt >= end_dt:
        raise HTTPException(
            status_code=422,
            detail="start_time must be earlier than end_time.",
        )
    return start_dt, end_dt
