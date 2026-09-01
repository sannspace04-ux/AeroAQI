"""
src/api/routers/health.py
==========================
Health and status endpoints.

Endpoints
---------
GET /health  — lightweight liveness probe (no DB query)
GET /status  — full readiness check with DB row counts + last ingestion run
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from src.api.dependencies import DbDep
from src.api.schemas import HealthResponse
from src.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])

_VERSION = "0.6.0"  # Phase 6 — XGBoost forecasting + SHAP explainability


@router.get(
    "",
    response_model=HealthResponse,
    summary="Liveness probe",
    description=(
        "Returns immediately to confirm the API process is running. "
        "Does not query the database. Use this for container health checks."
    ),
)
def health_check(db: DbDep) -> HealthResponse:
    """
    Lightweight liveness check.

    Returns HTTP 200 with status='ok' when the API is running.
    Includes a quick DB connectivity check and row counts.
    """
    db_status = "connected"
    obs_count = 0
    fire_count = 0
    last_run_ts: str | None = None
    last_run_status: str | None = None

    try:
        obs_count = db._count_rows("observations")
        fire_count = db._count_rows("fire_detections")

        runs = db.read_recent_ingestion_runs(n=1)
        if not runs.empty:
            ts_val = runs["run_timestamp"].iloc[0]
            last_run_ts = (
                ts_val.isoformat()
                if hasattr(ts_val, "isoformat")
                else str(ts_val)
            )
            last_run_status = str(runs["status"].iloc[0])
    except Exception as exc:
        db_status = f"error: {exc}"
        log.warning(f"[health] DB check failed: {exc}")

    return HealthResponse(
        status="ok",
        version=_VERSION,
        database=db_status,
        observations_count=obs_count,
        fire_detections_count=fire_count,
        last_ingestion_run=last_run_ts,
        last_ingestion_status=last_run_status,
    )


@router.get(
    "/status",
    response_model=HealthResponse,
    summary="Readiness probe",
    description=(
        "Full status check. Returns database connectivity, row counts, "
        "and the most recent ingestion run result. "
        "Returns HTTP 503 if the database is not reachable."
    ),
)
def readiness_check(db: DbDep) -> HealthResponse:
    """
    Detailed readiness check — returns HTTP 503 if the DB is unreachable.
    """
    try:
        obs_count = db._count_rows("observations")
        fire_count = db._count_rows("fire_detections")
    except Exception as exc:
        log.error(f"[health/status] DB unreachable: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"Database not reachable: {exc}",
        )

    last_run_ts = None
    last_run_status = None
    try:
        runs = db.read_recent_ingestion_runs(n=1)
        if not runs.empty:
            ts_val = runs["run_timestamp"].iloc[0]
            last_run_ts = (
                ts_val.isoformat()
                if hasattr(ts_val, "isoformat")
                else str(ts_val)
            )
            last_run_status = str(runs["status"].iloc[0])
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        version=_VERSION,
        database="connected",
        observations_count=obs_count,
        fire_detections_count=fire_count,
        last_ingestion_run=last_run_ts,
        last_ingestion_status=last_run_status,
    )
