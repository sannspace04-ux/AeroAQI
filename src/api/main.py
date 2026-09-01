"""
src/api/main.py
================
FastAPI application factory for AeroAQI.

Creates the app, registers all routers, configures CORS, and adds
a startup event that logs the DB connection state.

Usage
-----
    # Development
    python scripts/run_api.py

    # Production (example with gunicorn + uvicorn workers)
    gunicorn src.api.main:app -w 4 -k uvicorn.workers.UvicornWorker

Environment variables
---------------------
  DATABASE_URL     — SQLAlchemy URL (default: SQLite at data/db/aeroaqi.db)
  ALLOWED_ORIGINS  — comma-separated CORS origins (default: localhost:3000,5173)
  LOG_LEVEL        — DEBUG | INFO | WARNING | ERROR (default: INFO)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routers import fire, health, observations, pipeline, stations, weather
from src.utils.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------

_DESCRIPTION = """
## AeroAQI Backend API

Weather–chemistry coupled air pollution forecasting for **Delhi NCR** (PS 82 — MoES).

### Data sources
| Source | Description |
|--------|-------------|
| OpenAQ / CPCB | Ground-level PM2.5, PM10, NO₂, O₃, SO₂, CO |
| Open-Meteo | Hourly weather + atmospheric profile (PBL height, temp inversion) |
| ERA5 | Historical reanalysis weather (training data) |
| NASA FIRMS | Near-real-time fire/hotspot detections (VIIRS 375 m) |
| GADM | Administrative boundaries (India states + districts) |

### Feature pipeline
Raw observations → unit standardisation → spatial fire aggregation →
feature engineering (inversion, AQI, transport risk) → master dataset.

### Notes
- All timestamps are **UTC**.
- Missing measurements are returned as `null` — never filled with zero.
- API keys are configured server-side in `.env` and never exposed through the API.
"""

_TAGS = [
    {"name": "Health",          "description": "Liveness / readiness probes"},
    {"name": "Stations",        "description": "Delhi NCR monitoring station metadata"},
    {"name": "Air Quality",     "description": "PM2.5, PM10, NO₂, O₃, SO₂, CO, AQI"},
    {"name": "Weather",         "description": "Temperature, wind, humidity, PBL, inversion"},
    {"name": "Fire / Hotspots", "description": "NASA FIRMS fire detections and transport risk"},
    {"name": "Pipeline",        "description": "Trigger and monitor the ingestion pipeline"},
]


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup info and verify DB connectivity on startup."""
    from src.api.dependencies import get_db
    log.info("AeroAQI API starting up …")
    try:
        db = get_db()
        n = db._count_rows("observations")
        log.info(f"DB connected. observations table has {n} rows.")
    except Exception as exc:
        log.warning(f"DB check on startup failed (will retry on first request): {exc}")
    log.info("AeroAQI API ready.")
    yield
    log.info("AeroAQI API shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="AeroAQI",
        description=_DESCRIPTION,
        version="0.5.0",
        openapi_tags=_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    raw_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
    )
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Global exception handler ──────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        log.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred.", "status_code": 500},
        )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(stations.router)
    app.include_router(observations.router)
    app.include_router(weather.router)
    app.include_router(fire.router)
    app.include_router(pipeline.router)

    # ── Root redirect to docs ─────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/docs")

    return app


# ---------------------------------------------------------------------------
# Module-level app instance (used by uvicorn)
# ---------------------------------------------------------------------------

app = create_app()
