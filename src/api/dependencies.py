"""
src/api/dependencies.py
========================
FastAPI dependency-injection helpers shared across all routers.

Usage inside a route
--------------------
    from src.api.dependencies import get_db, get_settings, get_stations

    @router.get("/example")
    def example(db: DBClient = Depends(get_db)):
        ...

Design
------
- A single DBClient instance is created per-process (not per-request).
- The instance is stored in a module-level variable so that test overrides
  via `app.dependency_overrides[get_db]` work correctly.
- API keys / secrets are read from environment variables only.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends

from src.storage.db_client import DBClient
from src.utils.config_loader import load_settings, load_stations
from src.utils.logger import get_logger

log = get_logger(__name__)

# Module-level singleton — created lazily on first request.
# Tests override get_db() via app.dependency_overrides so this is
# only used in production runs.
_db_instance: Optional[DBClient] = None


def get_db() -> DBClient:
    """
    FastAPI dependency that returns the shared DBClient.

    The instance is created lazily on the first call and reused.
    Tests override this function via app.dependency_overrides.

    Inject with:
        db: DBClient = Depends(get_db)
    """
    global _db_instance
    if _db_instance is None:
        log.info("[api.deps] Creating application-level DBClient.")
        _db_instance = DBClient()
    return _db_instance


def reset_db_instance() -> None:
    """
    Reset the cached DBClient singleton.
    Call this in tests that need a fresh DB connection.
    """
    global _db_instance
    _db_instance = None


# ---------------------------------------------------------------------------
# Settings and station list
# ---------------------------------------------------------------------------

def get_settings() -> dict:
    """
    FastAPI dependency that returns the loaded project settings dict.
    Cached by config_loader (lru_cache).
    """
    return load_settings()


def get_station_list() -> list[dict]:
    """
    FastAPI dependency that returns all monitoring station records
    from config/stations.yaml. Cached by config_loader (lru_cache).
    """
    return load_stations()


# ---------------------------------------------------------------------------
# Type aliases for annotated deps (cleaner route signatures)
# ---------------------------------------------------------------------------

DbDep       = Annotated[DBClient,    Depends(get_db)]
SettingsDep = Annotated[dict,        Depends(get_settings)]
StationsDep = Annotated[list[dict],  Depends(get_station_list)]
