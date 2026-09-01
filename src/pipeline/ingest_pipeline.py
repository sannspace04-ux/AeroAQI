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

        # --- 7. Phase 6 — AQI forecast inference (runs if model is trained) --
        forecast_result = self._run_forecast_inference(
            start_date=start_date,
            end_date=end_date,
        )
        results.append(forecast_result)

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

    def _run_forecast_inference(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> SourceResult:
        """
        Phase 6: run AQI forecast inference using the pre-trained XGBoost model.

        Loads the model from data/models/, builds features from the latest
        observations, generates 72-hour forecasts for each active station,
        computes SHAP explanations, and writes the results to the forecasts table.

        Gracefully skips if:
          - No trained model exists yet (data/models/ is empty)
          - The observations table has insufficient data
          - xgboost / shap packages are not installed

        Returns a SourceResult so the pipeline summary table can show it.
        """
        log.info("[pipeline] ── Starting Phase 6 forecast inference ──")
        t_start = time.monotonic()

        try:
            from pathlib import Path
            from src.models.aqi_forecaster import AQIForecaster
            from src.models.feature_builder import FeatureBuilder
            from src.models.explainer import ForecastExplainer
            from src.utils.config_loader import get_project_root, load_stations

            model_dir = get_project_root() / "data" / "models"
            forecaster = AQIForecaster()

            if not forecaster.load(str(model_dir)):
                log.info(
                    "[pipeline] No trained model found — skipping forecast inference. "
                    "Run: python scripts/train_model.py"
                )
                return SourceResult(
                    source_name="forecast",
                    status="skipped",
                    error_message="No trained model. Run scripts/train_model.py first.",
                )

            # Load recent observations (last 72 h = enough for lag features)
            from datetime import datetime, timedelta, timezone
            end_dt = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(hours=72)
            obs_df = self._db.read_observations(start_time=start_dt, end_time=end_dt)

            if obs_df.empty:
                log.info("[pipeline] No recent observations — skipping forecast inference.")
                return SourceResult(source_name="forecast", status="no_data")

            import pandas as pd
            obs_df["timestamp_utc"] = pd.to_datetime(
                obs_df["timestamp_utc"], utc=True, errors="coerce"
            )

            fb = FeatureBuilder()
            explainer = ForecastExplainer(forecaster)
            stations = [s for s in load_stations() if s.get("active", True)]
            generated_at = datetime.now(timezone.utc)

            all_forecast_rows: list[dict] = []
            model_version = f"xgb_{len(forecaster._models)}models"

            for station in stations:
                sid = station["station_id"]
                station_df = obs_df[obs_df["station_id"] == sid].copy()
                if station_df.empty:
                    continue

                X, _, feat_names = fb.build(station_df)
                if X.empty:
                    continue

                base_ts = station_df["timestamp_utc"].max()
                forecast_df = forecaster.predict(
                    X,
                    feature_names=feat_names,
                    station_id=sid,
                    base_timestamp=base_ts,
                )
                if forecast_df.empty:
                    continue

                # SHAP explanation for first 24 h
                explanation = explainer.explain(X, target="pm25", horizon_hours=24)
                top_feat_json = None
                explanation_text = ""
                inversion_detected = False
                try:
                    top_feat_json = __import__("json").dumps(
                        explanation.get("top_features", [])
                    )
                    explanation_text = explanation.get("explanation_text", "")
                    inversion_detected = explanation.get("inversion_detected", False)
                except Exception:
                    pass

                for _, row in forecast_df.iterrows():
                    all_forecast_rows.append({
                        "generated_at": generated_at,
                        "station_id": sid,
                        "forecast_hour": int(row["forecast_hour"]),
                        "target_utc": row.get("target_utc"),
                        "pm25": row.get("pm25"),
                        "pm10": row.get("pm10"),
                        "o3": row.get("o3"),
                        "no2": row.get("no2"),
                        "aqi_computed": row.get("aqi_computed"),
                        "aqi_category": row.get("aqi_category"),
                        "top_features": top_feat_json,
                        "explanation_text": explanation_text,
                        "model_version": model_version,
                    })

            if not all_forecast_rows:
                duration = time.monotonic() - t_start
                return SourceResult(
                    source_name="forecast",
                    status="no_data",
                    duration_sec=duration,
                )

            rows_written = self._db.write_forecasts(pd.DataFrame(all_forecast_rows))
            duration = time.monotonic() - t_start

            log.info(
                f"[pipeline] Forecast inference complete — "
                f"{rows_written} rows written for {len(stations)} stations."
            )
            return SourceResult(
                source_name="forecast",
                status="success",
                rows_written=rows_written,
                duration_sec=duration,
            )

        except ImportError as exc:
            duration = time.monotonic() - t_start
            msg = f"Missing dependency: {exc}"
            log.warning(f"[pipeline] Forecast inference skipped — {msg}")
            return SourceResult(
                source_name="forecast",
                status="skipped",
                duration_sec=duration,
                error_message=msg,
            )
        except Exception as exc:
            duration = time.monotonic() - t_start
            msg = f"{type(exc).__name__}: {exc}"
            log.error(f"[pipeline] Forecast inference failed: {msg}", exc_info=True)
            return SourceResult(
                source_name="forecast",
                status="failed",
                duration_sec=duration,
                error_message=msg,
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
