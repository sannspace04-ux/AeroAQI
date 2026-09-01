"""
src/api/routers/stations.py
============================
Station/location endpoints.

Data source: config/stations.yaml (loaded at startup, cached in memory).
No DB query is needed — station metadata is static config.

Endpoints
---------
GET /stations                — list all 15 Delhi NCR monitoring stations
GET /stations/{station_id}   — single station by ID
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.dependencies import StationsDep
from src.api.schemas import StationResponse, StationsListResponse
from src.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/stations", tags=["Stations"])


@router.get(
    "",
    response_model=StationsListResponse,
    summary="List all monitoring stations",
    description=(
        "Returns all 15 Delhi NCR CAAQMS monitoring stations with their "
        "coordinates, operating agency, directional zone, and OpenAQ ID."
    ),
)
def list_stations(stations: StationsDep) -> StationsListResponse:
    """Return all monitoring stations from config/stations.yaml."""
    active = [s for s in stations if s.get("active", True)]
    response_items = [
        StationResponse(
            station_id=s["station_id"],
            name=s["name"],
            city=s["city"],
            state=s["state"],
            latitude=s["latitude"],
            longitude=s["longitude"],
            agency=s["agency"],
            zone=s["zone"],
            active=s.get("active", True),
            openaq_id=s.get("openaq_id"),
        )
        for s in active
    ]
    return StationsListResponse(count=len(response_items), stations=response_items)


@router.get(
    "/{station_id}",
    response_model=StationResponse,
    summary="Get a single station by ID",
    description=(
        "Returns metadata for one monitoring station. "
        "Station IDs are like 'DEL_ITO', 'DEL_ANAND_VIHAR', 'NOI_SECTOR62', etc. "
        "Returns 404 if the station ID is not found."
    ),
)
def get_station(station_id: str, stations: StationsDep) -> StationResponse:
    """Return one station by its station_id."""
    match = next(
        (s for s in stations if s["station_id"] == station_id), None
    )
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Station '{station_id}' not found. "
                f"Use GET /stations to see all valid station IDs."
            ),
        )
    return StationResponse(
        station_id=match["station_id"],
        name=match["name"],
        city=match["city"],
        state=match["state"],
        latitude=match["latitude"],
        longitude=match["longitude"],
        agency=match["agency"],
        zone=match["zone"],
        active=match.get("active", True),
        openaq_id=match.get("openaq_id"),
    )
