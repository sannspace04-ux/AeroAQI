"""
src/ingestion/gadm_fetcher.py
==============================
Downloads and processes GADM administrative boundary shapefiles for India.

What this fetcher provides
--------------------------
  State-level polygons (Level 1) covering:
    - Delhi NCR states (Delhi, Haryana, Uttar Pradesh, Rajasthan)
    - Fire source region states (Punjab, Haryana, western UP)

  District-level polygons (Level 2) covering:
    - All Delhi NCR districts
    - Punjab and Haryana districts (for fire source region mapping)

  Output is saved as GeoJSON files in data/processed/gadm/.

What it does NOT provide
-----------------------------------------
  No time-series data — GADM is static reference data.
  This fetcher produces GeoJSON files, not master-schema DataFrames.
  The resulting files are used by the pipeline for:
    1. Spatial joins (assigning station lat/lon to district)
    2. Map visualisations in the dashboard

API / Source reference
----------------------
  GADM v4.1:  https://gadm.org/download_country.html
  Direct download URL:
    https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_IND_shp.zip
  License: free for non-commercial academic use (with attribution).

One-time download
-----------------
  GADM data rarely changes.  After the first download, the pipeline
  re-uses the cached ZIP file unless force_download is set to true
  in data_sources.yaml.
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.ingestion.base_fetcher import BaseFetcher
from src.utils.logger import get_logger

log = get_logger(__name__)

# States relevant to Delhi NCR + fire source region
_STATES_OF_INTEREST = {
    "Delhi", "Haryana", "Punjab", "Uttar Pradesh",
    "Rajasthan", "Himachal Pradesh", "Uttarakhand",
}


class GADMFetcher(BaseFetcher):
    """
    Downloads GADM India shapefiles and exports the Delhi NCR + source
    region administrative boundaries as GeoJSON files.

    This fetcher outputs files to disk, not a master-schema DataFrame.
    The run() method returns an empty DataFrame (as required by the
    BaseFetcher contract) but the side-effect is the GeoJSON files.

    Example
    -------
    >>> fetcher = GADMFetcher()
    >>> fetcher.run(mode="static")
    # Produces:
    #   data/processed/gadm/india_states.geojson
    #   data/processed/gadm/india_districts.geojson
    """

    def __init__(self) -> None:
        super().__init__("gadm")
        self._download_url: str = self.config["download_url"]
        self._download_dir: Path = (
            self._project_root / self.config.get("download_dir", "data/raw/gadm")
        )
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._timeout: int = int(self.config.get("request_timeout_sec", 120))
        self._force: bool = bool(self.config.get("force_download", False))
        self._zip_path: Path = self._download_dir / "gadm41_IND_shp.zip"

    # ------------------------------------------------------------------
    # BaseFetcher interface
    # ------------------------------------------------------------------

    def _fetch_raw(self, **kwargs) -> dict:
        """
        Download the GADM India shapefile ZIP (one-time).
        If the file already exists and force_download is False,
        the existing file is reused.

        Returns
        -------
        dict with key "zip_path" pointing to the local ZIP file.
        """
        if self._zip_path.exists() and not self._force:
            size_mb = self._zip_path.stat().st_size / (1024 * 1024)
            log.info(
                f"[gadm] Shapefile ZIP already exists "
                f"({size_mb:.1f} MB) — reusing cached file. "
                f"Set force_download: true in data_sources.yaml to re-download."
            )
            return {"zip_path": self._zip_path}

        log.info(
            f"[gadm] Downloading GADM India shapefile from:\n"
            f"  {self._download_url}\n"
            f"  This is a large file (~85 MB) — please wait …"
        )

        response = requests.get(
            self._download_url,
            stream=True,
            timeout=self._timeout,
        )

        if response.status_code == 404:
            raise FileNotFoundError(
                f"GADM download URL returned 404 Not Found.\n"
                f"URL: {self._download_url}\n"
                f"The GADM URL may have changed. Check https://gadm.org for the "
                f"latest download links and update config/data_sources.yaml."
            )

        response.raise_for_status()

        total_bytes = 0
        with open(self._zip_path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
                if chunk:
                    fh.write(chunk)
                    total_bytes += len(chunk)

        size_mb = total_bytes / (1024 * 1024)
        log.info(f"[gadm] Download complete: {self._zip_path} ({size_mb:.1f} MB)")
        return {"zip_path": self._zip_path}

    def _normalise(self, raw_data: dict, **kwargs) -> pd.DataFrame:
        """
        Extract shapefiles from the ZIP and export filtered GeoJSON files.

        Requires geopandas.  If geopandas is not installed, logs an error
        and returns an empty DataFrame rather than crashing the pipeline.

        Returns an empty DataFrame (GADM data is geographic, not tabular
        time-series; GeoJSON files are the real output).
        """
        try:
            import geopandas as gpd
        except ImportError:
            log.error(
                "[gadm] geopandas is not installed. Cannot process shapefiles.\n"
                "Install it with:  pip install geopandas"
            )
            return pd.DataFrame()

        zip_path: Path = raw_data["zip_path"]

        if not zip_path.exists():
            log.error(f"[gadm] ZIP file not found: {zip_path}")
            return pd.DataFrame()

        # --- Extract the ZIP ---
        extract_dir = self._download_dir / "extracted"
        if not extract_dir.exists() or self._force:
            log.info(f"[gadm] Extracting shapefile ZIP → {extract_dir} …")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            log.info("[gadm] Extraction complete.")
        else:
            log.info(f"[gadm] Using previously extracted files in {extract_dir}")

        # --- Process Level 1 (states) ---
        levels_to_process = self.config.get("levels_to_keep", [1, 2])
        output_files: list[str] = []

        if 1 in levels_to_process:
            shp_path = extract_dir / "gadm41_IND_1.shp"
            if shp_path.exists():
                out = self._process_level(gpd, shp_path, level=1)
                if out is not None:
                    outfile = self.processed_dir / "india_states.geojson"
                    out.to_file(str(outfile), driver="GeoJSON")
                    log.info(
                        f"[gadm] Saved {len(out)} state polygons → {outfile}"
                    )
                    output_files.append(str(outfile))
            else:
                log.warning(f"[gadm] Level-1 shapefile not found: {shp_path}")

        if 2 in levels_to_process:
            shp_path = extract_dir / "gadm41_IND_2.shp"
            if shp_path.exists():
                out = self._process_level(gpd, shp_path, level=2)
                if out is not None:
                    outfile = self.processed_dir / "india_districts.geojson"
                    out.to_file(str(outfile), driver="GeoJSON")
                    log.info(
                        f"[gadm] Saved {len(out)} district polygons → {outfile}"
                    )
                    output_files.append(str(outfile))
            else:
                log.warning(f"[gadm] Level-2 shapefile not found: {shp_path}")

        if output_files:
            log.info(
                f"[gadm] Geographic data ready. Output files:\n"
                + "\n".join(f"  {f}" for f in output_files)
            )
        else:
            log.warning("[gadm] No output GeoJSON files were created.")

        # Return empty DataFrame — geographic output is via GeoJSON files
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_level(self, gpd, shp_path: Path, level: int):
        """
        Load a GADM shapefile, filter to states of interest, and
        return a GeoDataFrame ready for export.
        """
        log.info(f"[gadm] Loading Level-{level} shapefile: {shp_path}")
        try:
            gdf = gpd.read_file(str(shp_path))
        except Exception as exc:
            log.error(f"[gadm] Failed to read shapefile {shp_path}: {exc}")
            return None

        log.info(f"[gadm] Level-{level}: {len(gdf)} total features loaded.")

        # Column names differ by level
        name_col = "NAME_1" if level in (1, 2) else "NAME_0"
        filter_col = "NAME_1"   # always filter on state name

        if filter_col not in gdf.columns:
            log.warning(
                f"[gadm] Column '{filter_col}' not found. "
                f"Available columns: {list(gdf.columns)}"
            )
            # Keep all rows if column is missing
            filtered = gdf
        else:
            filtered = gdf[gdf[filter_col].isin(_STATES_OF_INTEREST)].copy()
            log.info(
                f"[gadm] Level-{level}: filtered to {len(filtered)} features "
                f"(states: {_STATES_OF_INTEREST})"
            )

        # Simplify geometry slightly for smaller file size (tolerance in degrees)
        try:
            filtered["geometry"] = filtered["geometry"].simplify(
                tolerance=0.005, preserve_topology=True
            )
        except Exception:
            pass  # Non-critical — keep original geometry

        return filtered

    def _save_processed(self, df: pd.DataFrame, **kwargs) -> Path:
        """
        Override: GADM output is GeoJSON (written in _normalise), not Parquet.
        This override prevents the base class from trying to save an empty
        DataFrame as a Parquet file.
        """
        log.debug("[gadm] _save_processed skipped — GeoJSON files written in _normalise.")
        return self.processed_dir

    def _save_raw(self, raw_data: Any, **kwargs) -> Path:
        """
        Override: raw data is already the ZIP file on disk.
        No additional saving needed.
        """
        log.debug(f"[gadm] Raw data is the ZIP file at {raw_data.get('zip_path')}")
        return raw_data.get("zip_path", self._zip_path)
