"""
src/ingestion/firms_fetcher.py
================================
Fetches near-real-time fire / hotspot data from NASA FIRMS
(Fire Information for Resource Management System).

What this fetcher provides
--------------------------
  Raw fire point data:
    latitude, longitude, fire radiative power (frp), confidence,
    acquisition timestamp, satellite, brightness temperature

  The pipeline's spatial aggregation step (Phase 4) will later convert
  these raw fire points into per-station aggregate features:
    fire_count_300km, fire_count_500km, total_frp_300km

  That spatial aggregation is DEFERRED — this fetcher only saves the
  raw fire locations.

What it does NOT provide (filled as NaN)
-----------------------------------------
  All weather columns, air quality columns.
  station_id is not applicable for raw fire point data.

API reference
-------------
  https://firms.modaps.eosdis.nasa.gov/api/area/
  Endpoint: GET /api/area/csv/<MAP_KEY>/<PRODUCT>/<BBOX>/<DAY_RANGE>
  Authentication: FIRMS_MAP_KEY in .env (free registration at
  https://firms.modaps.eosdis.nasa.gov/api/map_key/)

Bounding box
------------
  Covers Punjab, Haryana, western UP, Rajasthan — the primary
  stubble-burning source regions for Delhi NCR smoke transport.
  Format: lon_min,lat_min,lon_max,lat_max

Confidence filter
-----------------
  Low-confidence detections are excluded to reduce false positives.
  Only 'nominal' and 'high' confidence fires are kept.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
from typing import Any

import pandas as pd
import requests

from src.ingestion.base_fetcher import BaseFetcher
from src.schema.master_schema import COLUMN_NAMES, empty_master_dataframe
from src.utils.config_loader import get_env
from src.utils.logger import get_logger

log = get_logger(__name__)

# FIRMS confidence values ordered from lowest to highest
_CONFIDENCE_ORDER = ["low", "nominal", "high"]

# Columns we care about from the FIRMS CSV
_FIRMS_KEEP_COLS = [
    "latitude", "longitude", "acq_date", "acq_time",
    "frp", "confidence", "satellite", "bright_ti4", "daynight",
]


class FIRMSFetcher(BaseFetcher):
    """
    Fetches VIIRS active fire detections from NASA FIRMS for the
    Punjab–Haryana–Delhi stubble-burning source region.

    The output is a DataFrame of raw fire point records.
    Spatial aggregation to station-level features is done separately
    in the pipeline (deferred to Phase 4 feature engineering).

    Example
    -------
    >>> fetcher = FIRMSFetcher()
    >>> df = fetcher.run(mode="realtime")
    >>> df[["latitude", "longitude", "frp", "confidence", "timestamp_utc"]].head()
    """

    def __init__(self) -> None:
        super().__init__("firms")
        self._map_key: str = get_env("FIRMS_MAP_KEY", required=True)
        self._base_url: str = self.config["base_url"].rstrip("/")
        self._product: str = self.config.get("product", "VIIRS_SNPP_NRT")
        self._bbox: str = self.config.get("bbox", "73.0,27.5,80.0,33.0")
        self._day_range: int = int(self.config.get("day_range", 2))
        self._min_confidence: str = self.config.get("min_confidence", "nominal").lower()
        self._timeout: int = int(self.config.get("request_timeout_sec", 60))

    # ------------------------------------------------------------------
    # BaseFetcher interface
    # ------------------------------------------------------------------

    def _fetch_raw(self, **kwargs) -> str:
        """
        Download FIRMS active fire data as a CSV string.

        The FIRMS area API returns CSV text directly — no JSON wrapper.
        URL format:
          /api/area/csv/<MAP_KEY>/<PRODUCT>/<BBOX>/<DAY_RANGE>

        Returns
        -------
        str  — raw CSV text (may be empty if no fires detected).
        """
        mode = kwargs.get("mode", "realtime")

        if mode == "historical":
            # Historical FIRMS data requires a different endpoint
            # (archive download with date range). Implemented as a
            # future enhancement — realtime is sufficient for the MVP.
            log.warning(
                "[firms] Historical mode is not yet implemented. "
                "Falling back to realtime (last N days)."
            )

        url = f"{self._base_url}/{self._map_key}/{self._product}/{self._bbox}/{self._day_range}"

        log.info(
            f"[firms] Requesting VIIRS fire data | "
            f"product={self._product} | bbox={self._bbox} | "
            f"day_range={self._day_range} | url={url}"
        )

        response = requests.get(url, timeout=self._timeout)

        if response.status_code == 400:
            raise ValueError(
                f"FIRMS returned HTTP 400 Bad Request. "
                f"Check that FIRMS_MAP_KEY is valid and the bbox/product are correct. "
                f"Response: {response.text[:300]}"
            )

        if response.status_code == 401:
            raise PermissionError(
                "FIRMS returned HTTP 401 Unauthorized. "
                "Check that FIRMS_MAP_KEY in your .env file is correct.\n"
                "Register a free key at: https://firms.modaps.eosdis.nasa.gov/api/map_key/"
            )

        response.raise_for_status()

        csv_text = response.text
        line_count = csv_text.count("\n")
        log.info(f"[firms] Received {line_count} lines from FIRMS API.")
        return csv_text

    def _normalise(self, raw_data: str, **kwargs) -> pd.DataFrame:
        """
        Parse the FIRMS CSV text into a DataFrame conforming to the
        master schema.

        FIRMS CSV columns (VIIRS NRT):
          latitude, longitude, bright_ti4, scan, track, acq_date,
          acq_time, satellite, instrument, confidence, version,
          bright_ti5, frp, daynight

        The raw fire point table uses a different shape from the master
        schema (no station_id, multiple records per detection).
        We store it separately in data/raw/firms/ and data/processed/firms/.
        """
        if not raw_data or raw_data.strip() == "":
            log.warning("[firms] FIRMS returned empty response — no fires detected in the region.")
            # Return an empty but schema-compatible frame
            return self._empty_fire_dataframe()

        # Check if the API returned an error message instead of CSV
        if raw_data.strip().startswith("<!"):
            raise ValueError(
                f"[firms] FIRMS API returned HTML instead of CSV. "
                f"This usually means the MAP_KEY is invalid or expired.\n"
                f"Preview: {raw_data[:300]}"
            )

        try:
            df = pd.read_csv(StringIO(raw_data))
        except Exception as exc:
            raise ValueError(f"[firms] Failed to parse FIRMS CSV: {exc}")

        if df.empty:
            log.warning("[firms] FIRMS CSV parsed but contains no rows.")
            return self._empty_fire_dataframe()

        log.info(f"[firms] Parsed {len(df)} raw fire detections.")

        # ── Check expected columns ──────────────────────────────────────
        expected = self.config.get("expected_columns", [])
        missing_cols = [c for c in expected if c not in df.columns]
        if missing_cols:
            log.warning(
                f"[firms] Expected columns not found in CSV: {missing_cols}. "
                f"Actual columns: {list(df.columns)}"
            )

        # ── Build timestamp from acq_date + acq_time ───────────────────
        if "acq_date" in df.columns and "acq_time" in df.columns:
            df["acq_time_str"] = df["acq_time"].astype(str).str.zfill(4)
            df["timestamp_utc"] = pd.to_datetime(
                df["acq_date"].astype(str) + " " + df["acq_time_str"],
                format="%Y-%m-%d %H%M",
                utc=True,
                errors="coerce",
            )
            bad_ts = df["timestamp_utc"].isna().sum()
            if bad_ts > 0:
                log.warning(f"[firms] {bad_ts} rows had unparseable timestamps — dropped.")
                df = df.dropna(subset=["timestamp_utc"])
        else:
            log.error("[firms] 'acq_date' or 'acq_time' columns missing — cannot build timestamp.")
            return self._empty_fire_dataframe()

        # ── Confidence filter ───────────────────────────────────────────
        df = self._filter_confidence(df)

        # ── FRP validation ──────────────────────────────────────────────
        if "frp" in df.columns:
            df["frp"] = pd.to_numeric(df["frp"], errors="coerce")
            neg_frp = (df["frp"] < 0).sum()
            if neg_frp > 0:
                log.warning(
                    f"[firms] {neg_frp} rows have negative FRP values — set to NaN."
                )
                df.loc[df["frp"] < 0, "frp"] = float("nan")
        else:
            log.warning("[firms] 'frp' column not present in FIRMS data.")

        # ── Coordinate validation ───────────────────────────────────────
        if "latitude" in df.columns:
            df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        if "longitude" in df.columns:
            df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

        df = df.dropna(subset=["latitude", "longitude"])

        # ── Build output ────────────────────────────────────────────────
        # Fire data does not map cleanly to a single station row.
        # We store fire-specific columns alongside enough schema columns
        # for the pipeline to later do spatial joins.
        out = pd.DataFrame()
        out["timestamp_utc"] = df["timestamp_utc"]
        out["latitude"] = df["latitude"]
        out["longitude"] = df["longitude"]
        out["data_source"] = "firms"

        if "frp" in df.columns:
            out["frp"] = df["frp"]
        if "confidence" in df.columns:
            out["confidence"] = df["confidence"]
        if "satellite" in df.columns:
            out["satellite"] = df["satellite"]
        if "bright_ti4" in df.columns:
            out["bright_ti4"] = pd.to_numeric(df["bright_ti4"], errors="coerce")
        if "daynight" in df.columns:
            out["daynight"] = df["daynight"]

        log.info(
            f"[firms] Normalised {len(out)} fire detections after confidence filter."
        )
        return out

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _filter_confidence(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Keep only rows whose confidence is >= min_confidence setting.
        VIIRS uses 'low' / 'nominal' / 'high' string values.
        MODIS uses integer 0–100 — we treat values >= 50 as nominal.
        """
        if "confidence" not in df.columns:
            log.warning("[firms] No 'confidence' column — confidence filter skipped.")
            return df

        min_idx = _CONFIDENCE_ORDER.index(self._min_confidence)
        allowed = set(_CONFIDENCE_ORDER[min_idx:])

        # Handle both string and numeric confidence
        sample = str(df["confidence"].dropna().iloc[0]) if not df["confidence"].dropna().empty else ""

        if sample.isdigit():
            # Numeric confidence (MODIS): keep >= 50
            df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
            threshold = 50 if self._min_confidence == "nominal" else (
                80 if self._min_confidence == "high" else 0
            )
            before = len(df)
            df = df[df["confidence"] >= threshold]
            log.info(
                f"[firms] Confidence filter (numeric >= {threshold}): "
                f"{before} → {len(df)} rows."
            )
        else:
            # String confidence (VIIRS)
            before = len(df)
            df = df[df["confidence"].str.lower().isin(allowed)]
            log.info(
                f"[firms] Confidence filter ({allowed}): "
                f"{before} → {len(df)} rows."
            )

        return df

    def _empty_fire_dataframe(self) -> pd.DataFrame:
        """Return an empty DataFrame with the fire output columns."""
        return pd.DataFrame(
            columns=[
                "timestamp_utc", "latitude", "longitude",
                "frp", "confidence", "satellite",
                "bright_ti4", "daynight", "data_source",
            ]
        )

    def _save_raw(self, raw_data: Any, **kwargs):
        """
        Override base _save_raw to save FIRMS CSV text with a .csv extension
        instead of the default .txt extension.
        """
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filepath = self.raw_dir / f"{ts}_realtime_raw.csv"
        filepath.write_text(raw_data, encoding="utf-8")
        log.debug(f"[firms] Raw CSV saved → {filepath}")
        return filepath
