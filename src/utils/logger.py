"""
src/utils/logger.py
===================
Central logging configuration for AeroAQI.

Usage (in any module)
---------------------
    from src.utils.logger import get_logger

    log = get_logger(__name__)
    log.info("Fetching OpenAQ data...")
    log.warning("Station DEL_ITO has no data for this hour.")
    log.error("CDS API returned HTTP 403 — check your API key.")

Design decisions
----------------
- One rotating file handler  →  logs/aeroaqi.log
- One stream (console) handler with coloured output via 'rich' if installed,
  plain output otherwise.
- Log level is read from the LOG_LEVEL environment variable (default: INFO).
- Calling get_logger() multiple times with the same name is safe — Python's
  logging module returns the same Logger object each time.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Attempt to use rich for prettier console output.
# If rich is not installed yet, fall back to a plain StreamHandler.
# ---------------------------------------------------------------------------
try:
    from rich.logging import RichHandler  # type: ignore
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False

# ---------------------------------------------------------------------------
# Module-level flag so we only configure handlers once.
# ---------------------------------------------------------------------------
_LOGGING_CONFIGURED = False

# ---------------------------------------------------------------------------
# Resolve paths relative to the project root (two levels up from this file)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs"


def _configure_root_logger() -> None:
    """
    Set up the root logger with a file handler and a console handler.
    Called once the first time get_logger() is invoked.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    # Read log level from environment (default INFO)
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Ensure log directory exists
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOG_DIR / "aeroaqi.log"

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # --- File handler (rotating) ---
    file_fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_fmt)
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    # --- Console handler ---
    if _RICH_AVAILABLE:
        console_handler = RichHandler(
            level=level,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            markup=False,
        )
    else:
        console_fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_fmt)
        console_handler.setLevel(level)

    root_logger.addHandler(console_handler)

    # Suppress overly verbose third-party loggers
    for noisy in ("urllib3", "httpx", "httpcore", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger for the given module.

    Parameters
    ----------
    name : str
        Typically passed as ``__name__`` from the calling module.

    Returns
    -------
    logging.Logger
        A configured logger that writes to both console and the rotating
        log file at  logs/aeroaqi.log.

    Example
    -------
    >>> log = get_logger(__name__)
    >>> log.info("Pipeline started.")
    """
    _configure_root_logger()
    return logging.getLogger(name)
