"""
src/api/routers/pipeline.py
============================
Pipeline management endpoints.

These endpoints trigger the AeroAQI ingestion + processing pipeline
directly via the HTTP API — the same code that scripts/run_ingestion.py runs.

Security note
-------------
In a real production deployment these endpoints should be protected by an
API key or restricted to internal network access.  For the SIH prototype
they are open but document the expectation clearly.

Endpoints
---------
POST /pipeline/run     — trigger a full ingestion + processing run
GET  /pipeline/runs    — list recent pipeline run audit records
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.api.dependencies import DbDep
from src.api.schemas import (
    PipelineRunRequest, PipelineRunResponse, PipelineRunRecord,
    PipelineRunsResponse, PipelineSourceResult,
)
from src.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.post(
    "/run",
    response_model=PipelineRunResponse,
    status_code=202,
    summary="Trigger data ingestion + processing pipeline",
    description=(
        "Starts a full AeroAQI ingestion run (OpenAQ → Open-Meteo → FIRMS → "
        "feature engineering) and returns immediately with a run_id. "
        "The pipeline runs in a background thread. "
        "Use GET /pipeline/runs to check the result. \n\n"
        "**Note:** API keys (OPENAQ_API_KEY, FIRMS_MAP_KEY) must be "
        "configured in the server's .env file for real data to be fetched."
    ),
)
def trigger_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks,
    db: DbDep,
) -> PipelineRunResponse:
    """
    Validate the request and launch the ingestion pipeline in the background.
    Returns HTTP 202 Accepted immediately.
    """
    if request.mode == "historical":
        if not request.start_date or not request.end_date:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Historical mode requires both start_date and end_date. "
                    "Example: start_date='2023-10-01', end_date='2023-10-31'"
                ),
            )

    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}"

    log.info(
        f"[pipeline.api] Run {run_id} accepted. "
        f"mode={request.mode} skip_sources={request.skip_sources}"
    )

    # Launch in background so HTTP response is not blocked
    background_tasks.add_task(
        _run_pipeline_background,
        run_id=run_id,
        mode=request.mode,
        start_date=request.start_date,
        end_date=request.end_date,
        skip_sources=request.skip_sources,
        skip_processing=request.skip_processing,
    )

    return PipelineRunResponse(
        run_id=run_id,
        mode=request.mode,
        status="accepted",
        total_duration_sec=0.0,
        results=[],
    )


@router.get(
    "/runs",
    response_model=PipelineRunsResponse,
    summary="Recent pipeline run history",
    description=(
        "Returns the N most recent ingestion run audit records from the database. "
        "Each record shows the source, mode, status, rows written, and duration. "
        "Default n=20, max n=200."
    ),
)
def list_runs(db: DbDep, n: int = 20) -> PipelineRunsResponse:
    """Return the last N pipeline run records from the audit table."""
    if n < 1 or n > 200:
        raise HTTPException(status_code=422, detail="n must be between 1 and 200.")
    df = db.read_recent_ingestion_runs(n=n)
    if df.empty:
        return PipelineRunsResponse(count=0, runs=[])

    runs = []
    for row in df.to_dict(orient="records"):
        ts = row.get("run_timestamp")
        if ts is not None and hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        runs.append(PipelineRunRecord(
            id=row.get("id"),
            run_timestamp=str(ts) if ts else None,
            source_name=row.get("source_name"),
            mode=row.get("mode"),
            status=row.get("status"),
            rows_written=int(row.get("rows_written", 0) or 0),
            duration_sec=row.get("duration_sec"),
            error_message=row.get("error_message"),
        ))
    return PipelineRunsResponse(count=len(runs), runs=runs)


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def _run_pipeline_background(
    run_id: str,
    mode: str,
    start_date: Optional[str],
    end_date: Optional[str],
    skip_sources: list[str],
    skip_processing: bool,
) -> None:
    """
    Execute the full ingestion pipeline in a background thread.
    Catches all exceptions so the thread never silently dies.
    """
    # Lazy import to avoid circular dependency at module load time
    from src.pipeline.ingest_pipeline import IngestionPipeline

    log.info(f"[pipeline.bg] {run_id}: starting background run.")
    t0 = time.monotonic()

    try:
        pipeline = IngestionPipeline(
            skip_sources=skip_sources,
            skip_processing=skip_processing,
        )
        results = pipeline.run(
            mode=mode,
            start_date=start_date,
            end_date=end_date,
        )
        elapsed = time.monotonic() - t0
        log.info(
            f"[pipeline.bg] {run_id}: completed in {elapsed:.1f}s. "
            f"Results: {[(r.source_name, r.status) for r in results]}"
        )
    except Exception as exc:
        elapsed = time.monotonic() - t0
        log.error(
            f"[pipeline.bg] {run_id}: unhandled exception after {elapsed:.1f}s: {exc}",
            exc_info=True,
        )
