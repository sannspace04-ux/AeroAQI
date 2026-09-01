"""
src/ingestion/base_fetcher.py
==============================
Abstract base class that every data-source fetcher must inherit from.

Why an abstract base class?
----------------------------
All fetchers share the same outer shell:
  1. Load their config section from data_sources.yaml
  2. Fetch raw data from a source (API, file, etc.)
  3. Save the raw response to  data/raw/<source>/
  4. Normalise the raw data into the master schema
  5. Validate the normalised data
  6. Save the clean result to  data/processed/
  7. Return the clean DataFrame to the pipeline

By putting steps 3, 5, 6 and the retry/error logic here, each concrete
fetcher only needs to implement two focused methods:
  - _fetch_raw()   → how to talk to this specific source
  - _normalise()   → how to map the raw response to the master schema

This keeps every fetcher short and easy to read.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.config_loader import get_project_root, load_data_sources, load_settings
from src.utils.logger import get_logger
from src.utils.validators import run_all_validations

log = get_logger(__name__)


class BaseFetcher(ABC):
    """
    Abstract base class for all AeroAQI data-source fetchers.

    Subclasses must implement
    -------------------------
    _fetch_raw(**kwargs) -> Any
        Hit the remote source and return raw data in whatever native
        format the source uses (dict, list, str, bytes …).
        Should raise an exception on failure — the base class handles
        retries and logging.

    _normalise(raw_data, **kwargs) -> pd.DataFrame
        Convert the raw response into a DataFrame that conforms to the
        master schema.  Use empty_master_dataframe() as a starting point.
        Do NOT call validators here — the base class does that.

    Parameters
    ----------
    source_name : str
        Must match a key under 'sources' in config/data_sources.yaml
        (e.g. "openaq", "openmeteo", "era5", "firms", "gadm").
    """

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        self._settings = load_settings()
        all_sources = load_data_sources()

        if source_name not in all_sources:
            raise KeyError(
                f"Source '{source_name}' not found in config/data_sources.yaml. "
                f"Available sources: {list(all_sources.keys())}"
            )
        self.config: dict = all_sources[source_name]
        self._project_root: Path = get_project_root()

        # Directories
        raw_base = self._project_root / self._settings["paths"]["raw_data_dir"]
        proc_base = self._project_root / self._settings["paths"]["processed_data_dir"]

        self.raw_dir: Path = raw_base / source_name
        self.processed_dir: Path = proc_base / source_name

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        log.debug(
            f"[{self.source_name}] Fetcher initialised. "
            f"raw_dir={self.raw_dir}, processed_dir={self.processed_dir}"
        )

    # ------------------------------------------------------------------
    # Public interface — called by the pipeline
    # ------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """Return True if this source is enabled in data_sources.yaml."""
        return bool(self.config.get("enabled", True))

    def run(self, **kwargs) -> pd.DataFrame | None:
        """
        Execute the full fetch → save_raw → normalise → validate → save cycle.

        Parameters
        ----------
        **kwargs
            Passed through to _fetch_raw() and _normalise().
            Common keys: start_date, end_date, mode ("realtime"|"historical").

        Returns
        -------
        pd.DataFrame | None
            Clean DataFrame conforming to the master schema, or None if the
            fetch failed or the source is disabled.
        """
        if not self.is_enabled():
            log.info(f"[{self.source_name}] Source is disabled — skipping.")
            return None

        log.info(f"[{self.source_name}] Starting fetch. kwargs={kwargs}")

        # --- Step 1: Fetch raw data with retry ---
        raw_data = self._fetch_with_retry(**kwargs)
        if raw_data is None:
            log.error(
                f"[{self.source_name}] Fetch failed after all retries — "
                f"this source will be skipped for this run."
            )
            return None

        # --- Step 2: Persist raw data ---
        self._save_raw(raw_data, **kwargs)

        # --- Step 3: Normalise to master schema ---
        log.info(f"[{self.source_name}] Normalising raw data …")
        try:
            df = self._normalise(raw_data, **kwargs)
        except Exception as exc:
            log.error(
                f"[{self.source_name}] Normalisation failed: {exc}",
                exc_info=True,
            )
            return None

        if df is None or df.empty:
            log.warning(
                f"[{self.source_name}] Normalisation returned an empty DataFrame."
            )
            return None

        # --- Step 4: Validate ---
        df, success = run_all_validations(df, self.source_name)
        if not success:
            log.error(
                f"[{self.source_name}] Validation failed — results not saved."
            )
            return None

        # --- Step 5: Save processed Parquet ---
        self._save_processed(df, **kwargs)

        log.info(
            f"[{self.source_name}] Run complete — {len(df)} validated rows produced."
        )
        return df

    # ------------------------------------------------------------------
    # Abstract methods — subclasses must implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def _fetch_raw(self, **kwargs) -> Any:
        """
        Fetch raw data from the source.

        Must raise an exception on failure (connection error, HTTP error,
        missing API key, etc.).  The base class wraps this in retry logic.

        Returns
        -------
        Any
            Raw data in the source's native format.
        """
        ...

    @abstractmethod
    def _normalise(self, raw_data: Any, **kwargs) -> pd.DataFrame:
        """
        Convert raw source data into a DataFrame matching the master schema.

        Rules
        -----
        - Start with empty_master_dataframe() to get the right column types.
        - Populate only the columns this source actually provides.
        - Leave all other columns as NaN — do NOT fill with zero.
        - Set 'data_source' to self.source_name on every row.
        - Do NOT call validators here; the base class does that after.

        Returns
        -------
        pd.DataFrame
        """
        ...

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_with_retry(self, **kwargs) -> Any | None:
        """
        Call _fetch_raw() up to `retry_attempts` times with exponential backoff.
        Returns None if all attempts fail.
        """
        attempts: int = int(self.config.get("retry_attempts", 3))
        backoff: float = float(self.config.get("retry_backoff_sec", 5))

        for attempt in range(1, attempts + 1):
            try:
                log.debug(
                    f"[{self.source_name}] Fetch attempt {attempt}/{attempts} …"
                )
                result = self._fetch_raw(**kwargs)
                log.debug(f"[{self.source_name}] Fetch attempt {attempt} succeeded.")
                return result

            except Exception as exc:
                log.warning(
                    f"[{self.source_name}] Attempt {attempt}/{attempts} failed: {exc}"
                )
                if attempt < attempts:
                    wait = backoff * (2 ** (attempt - 1))   # exponential back-off
                    log.info(
                        f"[{self.source_name}] Waiting {wait:.0f}s before retry …"
                    )
                    time.sleep(wait)

        return None

    def _save_raw(self, raw_data: Any, **kwargs) -> Path:
        """
        Persist raw_data to  data/raw/<source>/<timestamp>_raw.<ext>.

        The file extension is chosen based on the data type:
          dict/list  →  .json
          str        →  .txt
          bytes      →  .bin
          DataFrame  →  .csv

        Returns the path where the file was written.
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_label = kwargs.get("mode", "run")

        if isinstance(raw_data, (dict, list)):
            filename = f"{ts}_{run_label}_raw.json"
            filepath = self.raw_dir / filename
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(raw_data, fh, indent=2, default=str)

        elif isinstance(raw_data, str):
            filename = f"{ts}_{run_label}_raw.txt"
            filepath = self.raw_dir / filename
            filepath.write_text(raw_data, encoding="utf-8")

        elif isinstance(raw_data, bytes):
            filename = f"{ts}_{run_label}_raw.bin"
            filepath = self.raw_dir / filename
            filepath.write_bytes(raw_data)

        elif isinstance(raw_data, pd.DataFrame):
            filename = f"{ts}_{run_label}_raw.csv"
            filepath = self.raw_dir / filename
            raw_data.to_csv(filepath, index=False)

        else:
            # Unknown type — save repr as text for debugging
            filename = f"{ts}_{run_label}_raw.txt"
            filepath = self.raw_dir / filename
            filepath.write_text(repr(raw_data), encoding="utf-8")

        log.debug(f"[{self.source_name}] Raw data saved → {filepath}")
        return filepath

    def _save_processed(self, df: pd.DataFrame, **kwargs) -> Path:
        """
        Save the validated DataFrame as a Parquet file.

        Path: data/processed/<source>/<timestamp>_processed.parquet
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_label = kwargs.get("mode", "run")
        filename = f"{ts}_{run_label}_processed.parquet"
        filepath = self.processed_dir / filename

        compression = (
            self._settings.get("parquet", {}).get("compression", "snappy")
        )
        df.to_parquet(filepath, index=False, compression=compression)

        log.info(
            f"[{self.source_name}] Processed data saved → {filepath} "
            f"({len(df)} rows, {df.shape[1]} columns)"
        )
        return filepath
