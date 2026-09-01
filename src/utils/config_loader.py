"""
src/utils/config_loader.py
==========================
Loads YAML configuration files and merges them with environment variables.

Usage
-----
    from src.utils.config_loader import load_settings, load_data_sources, load_stations

    settings = load_settings()
    sources  = load_data_sources()
    stations = load_stations()

All functions return plain Python dicts / lists so callers don't need to
import YAML parsing themselves.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from src.utils.logger import get_logger

log = get_logger(__name__)

# Project root = two levels up from this file (src/utils/config_loader.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"
_ENV_FILE = _PROJECT_ROOT / ".env"


def _load_env() -> None:
    """Load .env into os.environ once.  Safe to call multiple times."""
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
        log.debug(f"Loaded environment variables from {_ENV_FILE}")
    else:
        log.warning(
            f".env file not found at {_ENV_FILE}. "
            "API keys may be missing. Copy .env.example to .env and fill in your keys."
        )


def _read_yaml(path: Path) -> Any:
    """Read a YAML file and return its parsed content."""
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}\n"
            f"Expected location: {path}"
        )
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def load_settings() -> dict:
    """
    Load config/settings.yaml.

    Returns
    -------
    dict  — project-wide settings (paths, logging, quality thresholds).
    """
    _load_env()
    data = _read_yaml(_CONFIG_DIR / "settings.yaml")
    log.debug("Loaded settings.yaml")
    return data


@lru_cache(maxsize=1)
def load_data_sources() -> dict:
    """
    Load config/data_sources.yaml.

    Returns
    -------
    dict  — keyed by source name (openaq, openmeteo, era5, firms, gadm).
            Each value is the config dict for that source.
    """
    _load_env()
    data = _read_yaml(_CONFIG_DIR / "data_sources.yaml")
    log.debug("Loaded data_sources.yaml")
    return data.get("sources", {})


@lru_cache(maxsize=1)
def load_stations() -> list[dict]:
    """
    Load config/stations.yaml.

    Returns
    -------
    list[dict]  — one dict per monitoring station.
    """
    _load_env()
    data = _read_yaml(_CONFIG_DIR / "stations.yaml")
    stations = data.get("stations", [])
    log.debug(f"Loaded {len(stations)} stations from stations.yaml")
    return stations


def get_env(key: str, required: bool = True) -> str | None:
    """
    Read a single environment variable.

    Parameters
    ----------
    key      : Environment variable name (e.g. "OPENAQ_API_KEY").
    required : If True, raises EnvironmentError when the key is missing
               or still set to its placeholder value.

    Returns
    -------
    str | None
    """
    _load_env()
    value = os.getenv(key)
    placeholder_prefixes = ("your_", "replace_", "<", "CHANGE_ME")

    if not value or any(value.startswith(p) for p in placeholder_prefixes):
        msg = (
            f"Environment variable '{key}' is not set or still contains "
            f"a placeholder value. "
            f"Edit your .env file (copy from .env.example) and set a real value."
        )
        if required:
            log.error(msg)
            raise EnvironmentError(msg)
        else:
            log.warning(msg)
            return None

    return value


def get_project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return _PROJECT_ROOT
