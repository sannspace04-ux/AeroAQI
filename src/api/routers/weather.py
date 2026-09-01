"""
src/api/routers/weather.py
===========================
Weather and atmospheric profile endpoints.

Returns meteorological variables and derived atmospheric features
(PBL height, inversion flag, temperature profile) from the observations
table — all sourced from Open-Meteo or ERA5.

Endpoints
---------
GET /weather                   — weather readings for all stations
GET /weather/latest            — most recent weather reading per station
GET /weather/{station_id}      — weather history for one station
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.api.dependencies import DbDep
from src.api.schemas import WeatherObservation, WeatherResponse
from src.api.routers.observations import _resolve_time_range
from src.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/weather", tags=["Weather"])

_WX_COLS = [
    "timestamp_utc", "station_id", "station_name",
    "latitude", "longitude", "data_source",
    "temperature", "relative_humidity",
    "wind_speed", "wind_direction",
    "surface_pressure", "precipitation",
    "solar_radiation", "pbl_height",
    "temp_925hpa", "temp_850hpa", "temp_700hpa",
    "inversion_flag", "inversion_strength",
    "temperature_profile", "mixing_volume_idx",
]
_MAX_LIMIT = 1000
_DEFAULT_HOURS = 24


@router.get(
    "",
    response_model=WeatherResponse,
    summary="Weather observations for all stations",
    description=(
        "Returns hourly meteorological readings including temperature, "
        "humidity, wind, PBL height, and atmospheric profile data. "
        "Defaults to the last 24 hours."
    ),
)
def list_weather(
    db: DbDep,
    station_id: Optional[str] = Query(None, description="Filter to a specific station"),
    start_time: Optional[str] = Query(None, description="UTC start (ISO 8601)"),
    end_time: Optional[str] = Query(None, description="UTC end (ISO 8601)"),
    hours: Optional[int] = Query(None, ge=1, le=720, description="Look-back hours (default 24)"),
    limit: int = Query(200, ge=1, le=_MAX_LIMIT),
) -> WeatherResponse:
    start_dt, end_dt = _resolve_time_range(start_time, end_time, hours or _DEFAULT_HOURS)

    df = db.read_observations(
        station_id=station_id,
        start_time=start_dt,
        end_time=end_dt,
    )

    if len(df) > limit:
        df = df.tail(limit)

    records = [WeatherObservation.from_db_row(row) for row in df.to_dict(orient="records")]
    return WeatherResponse(count=len(records), station_id=station_id, observations=records)


@router.get(
    "/latest",
    response_model=WeatherResponse,
    summary="Most recent weather reading per station",
    description=(
        "Returns the single most recent weather observation for each station. "
        "Useful for populating a live conditions map."
    ),
)
def latest_weather(db: DbDep) -> WeatherResponse:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=48)

    df = db.read_observations(start_time=start_dt, end_time=end_dt)

    if df.empty:
        return WeatherResponse(count=0, observations=[])

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp_utc"])
    latest = df.sort_values("timestamp_utc").groupby("station_id").tail(1)

    records = [WeatherObservation.from_db_row(row) for row in latest.to_dict(orient="records")]
    return WeatherResponse(count=len(records), observations=records)


@router.get(
    "/{station_id}",
    response_model=WeatherResponse,
    summary="Weather history for one station",
    description=(
        "Returns hourly weather data for a specific station. "
        "Defaults to the last 24 hours. Returns 404 for unknown station IDs."
    ),
)
def station_weather(
    station_id: str,
    db: DbDep,
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    hours: Optional[int] = Query(None, ge=1, le=720),
    limit: int = Query(200, ge=1, le=_MAX_LIMIT),
) -> WeatherResponse:
    start_dt, end_dt = _resolve_time_range(start_time, end_time, hours or _DEFAULT_HOURS)

    df = db.read_observations(
        station_id=station_id,
        start_time=start_dt,
        end_time=end_dt,
    )

    if df.empty:
        from src.utils.config_loader import load_stations
        known = {s["station_id"] for s in load_stations()}
        if station_id not in known:
            raise HTTPException(
                status_code=404,
                detail=f"Station '{station_id}' not found.",
            )
        return WeatherResponse(count=0, station_id=station_id, observations=[])

    if len(df) > limit:
        df = df.tail(limit)

    records = [WeatherObservation.from_db_row(row) for row in df.to_dict(orient="records")]
    return WeatherResponse(count=len(records), station_id=station_id, observations=records)
