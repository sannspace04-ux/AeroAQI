"""
src/pipeline/ingest_pipeline.py
================================
Pipeline orchestrator for the AeroAQI data ingestion layer.

Responsibilities
----------------
1. Instantiate each enabled fetcher in the correct order.
2. Call fetcher.run() with the right mode and date arguments.
3. Route the returned DataFrame to the correct DB writer.
4. Write an audit record for every source (success or failure).
5. Print a final summary of all source results.

Run order
---------
  GADM   → static boundaries (run once; skipped if already downloaded)
  OpenAQ → air quality observations
  Open-Meteo → weather + atmospheric profile
  FIRMS  → fire detections
  ERA5   → historical weather (only in 'historical' mode)

ERA5 is placed last because it submits an asynchronous CDS job that
can take several minutes.  Running it after the faster sources means
you see AQ and weather data in the database even if ERA5 is slow.

Usage
-----
    from src.pipeline.ingest_pipeline import IngestionPipeline

    # Real-time run (fetch latest 48 h of data)
    pipeline = IngestionPipeline()
    pipeline.run(mode="realtime")

    # Historical backfill for a date range
    pipeline.run(
        mode="historical",
        start_date="2023-10-01",
        end_date="2023-10-31",
    )
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from src.ingestion.firms_fetcher import FIRMSFetcher
from src.ingestion.gadm_fetcher import GADMFetcher
from src.ingestion.openaq_fetcher import OpenAQFetcher
from src.ingestion.openmeteo_fetcher import OpenMeteoFetcher
from src.ingestion.era5_fetcher import ERA5Fetcher
from src.processing.dataset_builder import DatasetBuilder
from src.processing.quality_report import QualityReport
from src.storage.db_client import DBClient
from src.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result record — one per source per run
# ---------------------------------------------------------------------------

@dataclass
class SourceResult:
    source_name: str
    status: str               # "success" | "failed" | "skipped" | "no_data"
    rows_written: int = 0
    duration_sec: float = 0.0
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class IngestionPipeline:
    """
    Orchestrates a full ingestion run across all enabled data sources,
    followed by Phase 4 processing (fire aggregation + feature engineering).

    Parameters
    ----------
    db_url : str | None
        Override the database connection URL.  Defaults to DATABASE_URL
        in .env, falling back to SQLite at data/db/aeroaqi.db.
    skip_sources : list[str] | None
        Source names to skip even if enabled in config.
        e.g. skip_sources=["era5", "gadm"]
    skip_processing : bool
        If True, skip the Phase 4 processing step (useful when you only
        want to ingest raw data without computing derived features).

    Example
    -------
    >>> pipeline = IngestionPipeline()
    >>> results = pipeline.run(mode="realtime")
    >>> pipeline.print_summary(results)
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        skip_sources: Optional[list[str]] = None,
        skip_processing: bool = False,
    ) -> None:
        self._db = DBClient(db_url=db_url)
        self._skip_sources: set[str] = set(skip_sources or [])
        self._skip_processing = skip_processing
        log.info("[pipeline] IngestionPipeline initialised.")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        mode: str = "realtime",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[SourceResult]:
        """
        Execute a full ingestion cycle.

        Parameters
        ----------
        mode        : "realtime" or "historical"
        start_date  : ISO date string (required for historical mode)
        end_date    : ISO date string (required for historical mode)

        Returns
        -------
        list[SourceResult]  — one result record per source attempted.
        """
        run_start = datetime.now(timezone.utc)
        log.info(
            f"[pipeline] ========== INGESTION RUN STARTED ==========\n"
            f"           mode={mode}  start={start_date}  end={end_date}\n"
            f"           time={run_start.isoformat()}"
        )

        kwargs = {"mode": mode}
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date

        results: list[SourceResult] = []

        # --- 1. GADM (static boundaries — run once) ----------------------
        results.append(self._run_gadm(**kwargs))

        # --- 2. OpenAQ (air quality observations) ------------------------
        results.append(self._run_openaq(**kwargs))

        # --- 3. Open-Meteo (weather + profile) ---------------------------
        results.append(self._run_openmeteo(**kwargs))

        # --- 4. FIRMS (fire detections) ----------------------------------
        results.append(self._run_firms(**kwargs))

        # --- 5. ERA5 (historical only — slow, run last) ------------------
        if mode == "historical":
            results.append(self._run_era5(**kwargs))
        else:
            log.info(
                "[pipeline] ERA5 skipped (realtime mode). "
                "ERA5 is only used for historical training data."
            )
            results.append(SourceResult(
                source_name="era5",
                status="skipped",
                error_message="ERA5 not run in realtime mode.",
            ))

        # --- 6. Phase 4 processing (fire aggregation + feature engineering) ---
        processing_result = self._run_processing(
            mode=mode,
            start_date=start_date,
            end_date=end_date,
        )
        results.append(processing_result)

        # --- Summary -------------------------------------------------
        total_sec = (datetime.now(timezone.utc) - run_start).total_seconds()
        self.print_summary(results, total_sec)

        log.info(
            f"[pipeline] ========== INGESTION RUN COMPLETE ==========\n"
            f"           total_duration={total_sec:.1f}s"
        )
        return results

    # ------------------------------------------------------------------
    # Per-source runners
    # ------------------------------------------------------------------

    def _run_gadm(self, **kwargs) -> SourceResult:
        return self._run_source(
            source_name="gadm",
            fetcher_cls=GADMFetcher,
            db_writer=None,    # GADM writes GeoJSON, not DB rows
            **kwargs,
        )

    def _run_openaq(self, **kwargs) -> SourceResult:
        return self._run_source(
            source_name="openaq",
            fetcher_cls=OpenAQFetcher,
            db_writer=self._db.write_observations,
            **kwargs,
        )

    def _run_openmeteo(self, **kwargs) -> SourceResult:
        return self._run_source(
            source_name="openmeteo",
            fetcher_cls=OpenMeteoFetcher,
            db_writer=self._db.write_observations,
            **kwargs,
        )

    def _run_firms(self, **kwargs) -> SourceResult:
        return self._run_source(
            source_name="firms",
            fetcher_cls=FIRMSFetcher,
            db_writer=self._db.write_fire_detections,
            **kwargs,
        )

    def _run_era5(self, **kwargs) -> SourceResult:
        return self._run_source(
            source_name="era5",
            fetcher_cls=ERA5Fetcher,
            db_writer=self._db.write_observations,
            **kwargs,
        )

    def _run_processing(
        self,
        mode: str = "realtime",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> SourceResult:
        """
        Phase 4: fire spatial aggregation + feature engineering + master
        dataset build.

        Runs after all ingestion sources so all raw data is in the DB.
        Returns a SourceResult with source_name="processing".
        """
        if self._skip_processing:
            log.info("[pipeline] Processing step skipped (skip_processing=True).")
            return SourceResult(source_name="processing", status="skipped")

        log.info("[pipeline] ── Starting Phase 4 processing ──")
        t_start = time.monotonic()

        try:
            builder = DatasetBuilder(self._db)
            master_df = builder.build(
                start_date=start_date,
                end_date=end_date,
                write_db=True,
                write_parquet=True,
            )
            duration = time.monotonic() - t_start

            if master_df.empty:
                log.warning(
                    "[pipeline] Processing returned an empty master dataset. "
                    "This is normal when no observations are in the DB yet."
                )
                return SourceResult(
                    source_name="processing",
                    status="no_data",
                    duration_sec=duration,
                )

            # Print quality report
            report = QualityReport(master_df, source_name="master_dataset")
            report.print_report()

            return SourceResult(
                source_name="processing",
                status="success",
                rows_written=len(master_df),
                duration_sec=duration,
            )

        except Exception as exc:
            duration = time.monotonic() - t_start
            msg = f"{type(exc).__name__}: {exc}"
            log.error(
                f"[pipeline] Processing step failed: {msg}",
                exc_info=True,
            )
            return SourceResult(
                source_name="processing",
                status="failed",
                duration_sec=duration,
                error_message=msg,
            )

    # ------------------------------------------------------------------
    # Generic source runner
    # ------------------------------------------------------------------

    def _run_source(
        self,
        source_name: str,
        fetcher_cls,
        db_writer,
        **kwargs,
    ) -> SourceResult:
        """
        Instantiate a fetcher, call run(), write results to DB,
        log the audit record, and return a SourceResult.

        All exceptions are caught here so one source failure
        does not abort the entire pipeline run.
        """
        if source_name in self._skip_sources:
            log.info(f"[pipeline] {source_name}: skipped by caller request.")
            self._db.log_run(source_name, "skipped", mode=kwargs.get("mode", "realtime"))
            return SourceResult(source_name=source_name, status="skipped")

        log.info(f"[pipeline] ── Starting source: {source_name} ──")
        t_start = time.monotonic()

        try:
            fetcher = fetcher_cls()

            if not fetcher.is_enabled():
                log.info(f"[pipeline] {source_name}: disabled in config — skipping.")
                self._db.log_run(
                    source_name, "skipped",
                    mode=kwargs.get("mode", "realtime"),
                )
                return SourceResult(source_name=source_name, status="skipped")

            df: Optional[pd.DataFrame] = fetcher.run(**kwargs)
            duration = time.monotonic() - t_start

            if df is None:
                # Fetcher returned None — fetch or validation failed
                self._db.log_run(
                    source_name, "failed",
                    mode=kwargs.get("mode", "realtime"),
                    duration_sec=duration,
                    error_message="Fetcher returned None",
                )
                return SourceResult(
                    source_name=source_name,
                    status="failed",
                    duration_sec=duration,
                    error_message="Fetcher returned None",
                )

            # GADM returns an empty DataFrame (output is GeoJSON files)
            if df.empty:
                status = "success" if source_name == "gadm" else "no_data"
                self._db.log_run(
                    source_name, status,
                    rows_written=0,
                    mode=kwargs.get("mode", "realtime"),
                    duration_sec=duration,
                )
                return SourceResult(
                    source_name=source_name,
                    status=status,
                    duration_sec=duration,
                )

            # Write to database
            rows_written = 0
            if db_writer is not None:
                rows_written = db_writer(df)

            self._db.log_run(
                source_name, "success",
                rows_written=rows_written,
                mode=kwargs.get("mode", "realtime"),
                duration_sec=duration,
            )
            return SourceResult(
                source_name=source_name,
                status="success",
                rows_written=rows_written,
                duration_sec=duration,
            )

        except EnvironmentError as exc:
            # Missing API key — clear, actionable error
            duration = time.monotonic() - t_start
            msg = (
                f"API key / credentials not configured for '{source_name}'. "
                f"Details: {exc}"
            )
            log.error(f"[pipeline] {source_name}: {msg}")
            self._db.log_run(
                source_name, "failed",
                mode=kwargs.get("mode", "realtime"),
                duration_sec=duration,
                error_message=msg,
            )
            return SourceResult(
                source_name=source_name,
                status="failed",
                duration_sec=duration,
                error_message=msg,
            )

        except Exception as exc:
            duration = time.monotonic() - t_start
            msg = f"{type(exc).__name__}: {exc}"
            log.error(
                f"[pipeline] {source_name}: unexpected error — {msg}",
                exc_info=True,
            )
            self._db.log_run(
                source_name, "failed",
                mode=kwargs.get("mode", "realtime"),
                duration_sec=duration,
                error_message=msg,
            )
            return SourceResult(
                source_name=source_name,
                status="failed",
                duration_sec=duration,
                error_message=msg,
            )

    # ------------------------------------------------------------------
    # Summary printer
    # ------------------------------------------------------------------

    @staticmethod
    def print_summary(
        results: list[SourceResult],
        total_sec: float = 0.0,
    ) -> None:
        """Print a formatted table of per-source run results."""
        divider = "─" * 72
        print(f"\n{divider}")
        print(f"  AeroAQI Ingestion Run Summary")
        print(divider)
        print(
            f"  {'Source':<16} {'Status':<12} {'Rows written':>14} "
            f"{'Duration':>10}"
        )
        print(divider)

        status_icons = {
            "success": "✓",
            "failed":  "✗",
            "skipped": "–",
            "no_data": "○",
        }

        for r in results:
            icon = status_icons.get(r.status, "?")
            rows_str = str(r.rows_written) if r.rows_written else "—"
            dur_str = f"{r.duration_sec:.1f}s" if r.duration_sec else "—"
            print(
                f"  {icon} {r.source_name:<14} {r.status:<12} "
                f"{rows_str:>14} {dur_str:>10}"
            )
            if r.error_message and r.status == "failed":
                # Truncate long errors for readability
                short_err = r.error_message[:80]
                print(f"    ↳ {short_err}")

        print(divider)
        total_rows = sum(r.rows_written for r in results)
        success_count = sum(1 for r in results if r.status == "success")
        print(
            f"  Total: {success_count}/{len(results)} sources succeeded | "
            f"{total_rows} rows written | {total_sec:.1f}s elapsed"
        )
        print(f"{divider}\n")
