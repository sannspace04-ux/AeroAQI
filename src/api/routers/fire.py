"""
src/api/routers/fire.py
========================
Fire/hotspot detection and transport risk endpoints.

Two distinct data sources:
  1. fire_detections table  — raw FIRMS VIIRS point detections
  2. observations table     — fire aggregate features per station
     (fire_count_300km, fire_distance_km, fire_transport_risk, …)

Endpoints
---------
GET /fire/detections              — raw FIRMS fire point records
GET /fire/risk                    — per-station fire transport risk readings
GET /fire/risk/{station_id}       — fire risk history for one station
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.api.dependencies import DbDep
from src.api.schemas import (
    FireDetectionRecord, FireDetectionsResponse,
    FireRiskRecord, FireRiskResponse,
)
from src.api.routers.observations import _resolve_time_range
from src.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/fire", tags=["Fire / Hotspots"])

_FIRE_RISK_COLS = [
    "timestamp_utc", "station_id", "station_name",
    "fire_count_300km", "fire_count_500km",
    "total_frp_300km", "fire_distance_km",
    "fire_nearest_frp", "fire_transport_risk",
    "wind_transport_idx",
]
_MAX_LIMIT = 2000
_DEFAULT_HOURS = 48


# ---------------------------------------------------------------------------
# Raw FIRMS detections
# ---------------------------------------------------------------------------

@router.get(
    "/detections",
    response_model=FireDetectionsResponse,
    summary="Raw fire/hotspot detections from NASA FIRMS",
    description=(
        "Returns raw VIIRS active fire detection records for the "
        "Punjab–Haryana–Delhi NCR source region. "
        "Each record has a lat/lon, Fire Radiative Power (FRP in MW), "
        "confidence level, and acquisition timestamp. "
        "Defaults to the last 48 hours."
    ),
)
def fire_detections(
    db: DbDep,
    start_time: Optional[str] = Query(None, description="UTC start (ISO 8601)"),
    end_time: Optional[str] = Query(None, description="UTC end (ISO 8601)"),
    hours: Optional[int] = Query(
        None, ge=1, le=720,
        description="Look-back hours (default 48, max 720)",
    ),
    min_confidence: Optional[str] = Query(
        None,
        description="Minimum confidence level: 'low', 'nominal', or 'high'",
    ),
    limit: int = Query(500, ge=1, le=_MAX_LIMIT),
) -> FireDetectionsResponse:
    start_dt, end_dt = _resolve_time_range(start_time, end_time, hours or _DEFAULT_HOURS)

    df = db.read_fire_detections(start_time=start_dt, end_time=end_dt)

    if df.empty:
        return FireDetectionsResponse(
            count=0,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            detections=[],
        )

    # Optional confidence filter
    if min_confidence:
        _CONF_ORDER = {"low": 0, "nominal": 1, "high": 2}
        min_val = _CONF_ORDER.get(min_confidence.lower())
        if min_val is None:
            raise HTTPException(
                status_code=422,
                detail="min_confidence must be 'low', 'nominal', or 'high'.",
            )
        if "confidence" in df.columns:
            # Handle both string ('nominal') and numeric (50-100) confidence
            sample = str(df["confidence"].dropna().iloc[0]) if not df["confidence"].dropna().empty else ""
            if sample.isdigit():
                thresholds = {"low": 0, "nominal": 50, "high": 80}
                df = df[pd.to_numeric(df["confidence"], errors="coerce") >= thresholds[min_confidence.lower()]]
            else:
                allowed = [k for k, v in _CONF_ORDER.items() if v >= min_val]
                df = df[df["confidence"].str.lower().isin(allowed)]

    if len(df) > limit:
        df = df.tail(limit)

    records = [
        FireDetectionRecord.from_db_row(row)
        for row in df.to_dict(orient="records")
    ]
    return FireDetectionsResponse(
        count=len(records),
        start_time=start_dt.isoformat(),
        end_time=end_dt.isoformat(),
        detections=records,
    )


# ---------------------------------------------------------------------------
# Per-station fire risk
# ---------------------------------------------------------------------------

@router.get(
    "/risk",
    response_model=FireRiskResponse,
    summary="Fire transport risk per station",
    description=(
        "Returns derived fire transport risk scores per station. "
        "Includes fire counts within 300 km / 500 km, total FRP, "
        "distance to nearest fire, and a composite transport risk score [0-1]. "
        "Defaults to the last 48 hours."
    ),
)
def fire_risk(
    db: DbDep,
    station_id: Optional[str] = Query(None, description="Filter to a specific station"),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    hours: Optional[int] = Query(None, ge=1, le=720),
    limit: int = Query(200, ge=1, le=_MAX_LIMIT),
) -> FireRiskResponse:
    start_dt, end_dt = _resolve_time_range(start_time, end_time, hours or _DEFAULT_HOURS)

    df = db.read_observations(
        station_id=station_id,
        start_time=start_dt,
        end_time=end_dt,
    )

    if len(df) > limit:
        df = df.tail(limit)

    records = [FireRiskRecord.from_db_row(row) for row in df.to_dict(orient="records")]
    return FireRiskResponse(count=len(records), station_id=station_id, records=records)


@router.get(
    "/risk/{station_id}",
    response_model=FireRiskResponse,
    summary="Fire risk history for one station",
    description=(
        "Returns fire transport risk time series for a single station. "
        "Returns 404 for unknown station IDs."
    ),
)
def station_fire_risk(
    station_id: str,
    db: DbDep,
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    hours: Optional[int] = Query(None, ge=1, le=720),
    limit: int = Query(200, ge=1, le=_MAX_LIMIT),
) -> FireRiskResponse:
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
        return FireRiskResponse(count=0, station_id=station_id, records=[])

    if len(df) > limit:
        df = df.tail(limit)

    records = [FireRiskRecord.from_db_row(row) for row in df.to_dict(orient="records")]
    return FireRiskResponse(count=len(records), station_id=station_id, records=records)
