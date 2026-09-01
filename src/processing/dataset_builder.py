"""
src/processing/dataset_builder.py
=====================================
Merges the weather, air-quality, and fire data streams into a single
unified master dataset, applies processing, and persists the result.

Responsibility chain
--------------------
  1. Load observations (AQ + weather) from DB.
  2. Load raw fire detections from DB.
  3. Standardise units (where the DB values may still be in raw units).
  4. Spatially aggregate fire features onto each observation row
     (FireAggregator).
  5. Compute all DERIVED features (FeatureEngineer).
  6. Validate the resulting master dataset.
  7. Persist:
       - Parquet file at data/processed/master/
       - Write back to DB (observations table) to persist derived columns.

Design rules
------------
- Raw data in data/raw/ and the fire_detections table are never modified.
- The observations table is updated to store derived column values.
- The Parquet file is the canonical flat-file version of the master dataset.
- All time alignment uses UTC timestamps truncated to the hour.
- Missing-value policy: NaN stays NaN — no zero-filling.
- Idempotent: running twice produces the same result (derived columns
  are not overwritten when already populated).

Usage
-----
    from src.processing.dataset_builder import DatasetBuilder
    from src.storage.db_client import DBClient

    db = DBClient()
    builder = DatasetBuilder(db)
    master_df = builder.build()         # uses last 48 h by default
    # or:
    master_df = builder.build(start_date="2023-10-01", end_date="2023-10-31")
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from src.processing.feature_engineer import FeatureEngineer
from src.processing.fire_aggregator import FireAggregator
from src.processing.unit_converter import compute_cpcb_aqi
from src.schema.master_schema import COLUMN_NAMES
from src.utils.config_loader import get_project_root, load_settings
from src.utils.logger import get_logger
from src.utils.validators import run_all_validations

log = get_logger(__name__)

# Default look-back window when no dates are specified
_DEFAULT_LOOKBACK_HOURS = 48


class DatasetBuilder:
    """
    Orchestrates the full processing pipeline from raw DB tables to the
    master Parquet dataset.

    Parameters
    ----------
    db : DBClient
        Provides read_observations(), read_fire_detections(),
        and write_master_dataset().
    output_dir : Path | None
        Where to write master Parquet files.  Defaults to
        data/processed/master/.
    """

    def __init__(self, db, output_dir: Optional[Path] = None) -> None:
        self._db = db
        project_root = get_project_root()
        settings = load_settings()
        proc_base = project_root / settings["paths"]["processed_data_dir"]
        self._out_dir = output_dir or (proc_base / "master")
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._fe = FeatureEngineer()
        self._fa = FireAggregator()
        log.info(f"[builder] DatasetBuilder initialised. output_dir={self._out_dir}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        station_id: Optional[str] = None,
        write_db: bool = True,
        write_parquet: bool = True,
    ) -> pd.DataFrame:
        """
        Build and persist the master dataset.

        Parameters
        ----------
        start_date  : ISO date string "YYYY-MM-DD" (inclusive).
                      Defaults to now − 48 h.
        end_date    : ISO date string "YYYY-MM-DD" (inclusive).
                      Defaults to now.
        station_id  : Optionally limit to one station.
        write_db    : If True, persist derived columns back to DB.
        write_parquet : If True, save master Parquet file.

        Returns
        -------
        pd.DataFrame  — master dataset with all OBSERVED + DERIVED columns.
        """
        start_dt, end_dt = self._resolve_dates(start_date, end_date)

        log.info(
            f"[builder] Building master dataset | "
            f"{start_dt.date()} → {end_dt.date()} | "
            f"station_id={station_id or 'all'}"
        )

        # ── Step 1: Load observations ─────────────────────────────────
        obs_df = self._db.read_observations(
            station_id=station_id,
            start_time=start_dt,
            end_time=end_dt,
        )

        if obs_df.empty:
            log.warning(
                "[builder] No observations found for the specified range. "
                "Make sure the ingestion pipeline has run first."
            )
            return pd.DataFrame()

        log.info(f"[builder] Loaded {len(obs_df)} observation rows.")

        # ── Step 2: Standardise units ─────────────────────────────────
        obs_df = self._standardise_units(obs_df)

        # ── Step 3: Load fire detections ──────────────────────────────
        fire_df = self._db.read_fire_detections(
            start_time=start_dt,
            end_time=end_dt,
        )
        log.info(f"[builder] Loaded {len(fire_df)} fire detection rows.")

        # ── Step 4: Aggregate fire features ──────────────────────────
        obs_df = self._fa.aggregate(obs_df, fire_df)

        # ── Step 5: Compute derived features ─────────────────────────
        obs_df = self._fe.compute_all(obs_df)

        # ── Step 6: Validate ─────────────────────────────────────────
        obs_df, success = run_all_validations(
            obs_df,
            source_name="master_dataset",
            required_columns=["timestamp_utc", "station_id", "data_source"],
        )
        if not success:
            log.error("[builder] Validation failed — master dataset not saved.")
            return obs_df

        # ── Step 7: Align columns to schema order (drop extras) ──────
        obs_df = self._align_to_schema(obs_df)

        # ── Step 8: Persist ───────────────────────────────────────────
        if write_parquet:
            parquet_path = self._save_parquet(obs_df, start_dt, end_dt)
            log.info(f"[builder] Master dataset saved → {parquet_path}")

        if write_db:
            rows = self._db.write_master_dataset(obs_df)
            log.info(f"[builder] {rows} rows written/updated in DB.")

        log.info(
            f"[builder] Master dataset build complete — "
            f"{len(obs_df)} rows, {obs_df.shape[1]} columns."
        )
        return obs_df

    # ------------------------------------------------------------------
    # Static: build from Parquet files (no DB needed)
    # ------------------------------------------------------------------

    @staticmethod
    def build_from_parquet(
        aq_parquet: Path,
        weather_parquet: Path,
        fire_parquet: Optional[Path] = None,
    ) -> pd.DataFrame:
        """
        Build a master dataset from individual processed Parquet files
        (as produced by the ingestion fetchers) without using the DB.

        Useful for offline / batch workflows and for unit testing.

        Parameters
        ----------
        aq_parquet      : Path to OpenAQ processed Parquet.
        weather_parquet : Path to Open-Meteo processed Parquet.
        fire_parquet    : Path to FIRMS processed Parquet (optional).

        Returns
        -------
        pd.DataFrame — merged master dataset.
        """
        log.info(f"[builder] build_from_parquet: AQ={aq_parquet.name}")

        aq_df = pd.read_parquet(aq_parquet)
        wx_df = pd.read_parquet(weather_parquet)

        master = DatasetBuilder._merge_aq_weather(aq_df, wx_df)

        if fire_parquet and fire_parquet.exists():
            fire_df = pd.read_parquet(fire_parquet)
            fa = FireAggregator()
            master = fa.aggregate(master, fire_df)

        fe = FeatureEngineer()
        master = fe.compute_all(master)
        return master

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_dates(
        start_date: Optional[str], end_date: Optional[str]
    ) -> tuple[datetime, datetime]:
        """Return (start_dt, end_dt) as UTC datetime objects."""
        now = datetime.now(timezone.utc)
        if end_date:
            end_dt = datetime.fromisoformat(end_date).replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        else:
            end_dt = now

        if start_date:
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        else:
            start_dt = now - timedelta(hours=_DEFAULT_LOOKBACK_HOURS)

        return start_dt, end_dt

    @staticmethod
    def _standardise_units(df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply unit conversions to columns that may arrive in non-canonical
        units from the DB.  Conversions are only applied where values are
        clearly outside the canonical range (suggesting the wrong unit).

        Current checks:
          temperature  > 200  → assume Kelvin, convert to Celsius
          surface_pressure > 2000 → assume Pa, convert to hPa
          solar_radiation > 5_000_000 → assume J/m² (ERA5), convert to W/m²
          precipitation > 10 → assume metres (ERA5), convert to mm/hr

        These checks are conservative — they only trigger when the value
        is physically impossible in the canonical unit.
        """
        df = df.copy()

        # Temperature: K → °C
        if "temperature" in df.columns:
            mask = df["temperature"].notna() & (df["temperature"] > 200)
            if mask.any():
                df.loc[mask, "temperature"] = df.loc[mask, "temperature"] - 273.15
                log.debug(f"[builder] Converted {mask.sum()} temperature values K→°C")

        # Surface pressure: Pa → hPa
        if "surface_pressure" in df.columns:
            mask = df["surface_pressure"].notna() & (df["surface_pressure"] > 2000)
            if mask.any():
                df.loc[mask, "surface_pressure"] = (
                    df.loc[mask, "surface_pressure"] / 100.0
                )
                log.debug(
                    f"[builder] Converted {mask.sum()} pressure values Pa→hPa"
                )

        # Solar radiation: J/m² → W/m²
        if "solar_radiation" in df.columns:
            mask = (
                df["solar_radiation"].notna()
                & (df["solar_radiation"] > 5_000_000)
            )
            if mask.any():
                df.loc[mask, "solar_radiation"] = (
                    df.loc[mask, "solar_radiation"] / 3600.0
                ).clip(lower=0.0)
                log.debug(
                    f"[builder] Converted {mask.sum()} solar_radiation values J/m²→W/m²"
                )

        # Precipitation: m → mm/hr
        if "precipitation" in df.columns:
            mask = (
                df["precipitation"].notna()
                & (df["precipitation"] > 10)
            )
            if mask.any():
                df.loc[mask, "precipitation"] = (
                    df.loc[mask, "precipitation"] * 1000.0
                ).clip(lower=0.0)
                log.debug(
                    f"[builder] Converted {mask.sum()} precipitation values m→mm"
                )

        return df

    @staticmethod
    def _merge_aq_weather(
        aq_df: pd.DataFrame,
        wx_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge air-quality and weather DataFrames on (timestamp_utc, station_id).

        Both DataFrames must have timestamp_utc and station_id columns.
        A left-outer join is used: every AQ row is kept; weather columns
        are NaN where no match exists.
        """
        aq_df = aq_df.copy()
        wx_df = wx_df.copy()

        # Normalise timestamps to UTC hour
        for df_ in (aq_df, wx_df):
            df_["timestamp_utc"] = pd.to_datetime(
                df_["timestamp_utc"], utc=True, errors="coerce"
            ).dt.floor("h")

        # Identify weather-only columns to bring in
        aq_cols = set(aq_df.columns)
        wx_only = [
            c for c in wx_df.columns
            if c not in aq_cols or c in ("timestamp_utc", "station_id")
        ]

        merged = aq_df.merge(
            wx_df[wx_only],
            on=["timestamp_utc", "station_id"],
            how="left",
        )
        log.debug(
            f"[builder] Merged AQ ({len(aq_df)}) + weather ({len(wx_df)}) "
            f"→ {len(merged)} rows."
        )
        return merged

    @staticmethod
    def _align_to_schema(df: pd.DataFrame) -> pd.DataFrame:
        """
        Reorder columns to match COLUMN_NAMES and drop any unknown extras.
        Missing schema columns are added as NaN so the output always has
        the same shape.
        """
        for col in COLUMN_NAMES:
            if col not in df.columns:
                df[col] = pd.NA
        return df[[c for c in COLUMN_NAMES if c in df.columns]]

    def _save_parquet(
        self,
        df: pd.DataFrame,
        start_dt: datetime,
        end_dt: datetime,
    ) -> Path:
        """Save master dataset as a timestamped Parquet file."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        start_str = start_dt.strftime("%Y%m%d")
        end_str = end_dt.strftime("%Y%m%d")
        filename = f"{ts}_master_{start_str}_{end_str}.parquet"
        filepath = self._out_dir / filename
        df.to_parquet(filepath, index=False, compression="snappy")
        return filepath
