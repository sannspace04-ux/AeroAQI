"""
src/ingestion/era5_fetcher.py
==============================
Downloads ERA5 reanalysis data from the Copernicus Climate Data Store (CDS)
for use as historical training data.

What this fetcher provides
--------------------------
  temperature, relative_humidity, wind_speed, wind_direction,
  surface_pressure, precipitation, solar_radiation, pbl_height,
  temp_925hpa, temp_850hpa, temp_700hpa

  Data covers the Delhi NCR bounding box at 0.25° × 0.25° resolution.

What it does NOT provide (filled as NaN)
-----------------------------------------
  All air quality columns (pm25, pm10, etc.), fire columns, station_id.
  (station_id is left as NaN — ERA5 produces gridded data, not station data)

IMPORTANT — latency and use case
----------------------------------
  ERA5 has approximately a 5-day data latency.
  It is ONLY used for building the historical training dataset.
  For real-time inference, use OpenMeteoFetcher instead.

API reference
-------------
  https://cds.climate.copernicus.eu/how-to-api
  Python library: cdsapi (must be installed: pip install cdsapi)
  Registration: free at https://cds.climate.copernicus.eu

Authentication
--------------
  The cdsapi library looks for credentials in ~/.cdsapirc first.
  We also support CDS_API_KEY / CDS_API_URL in .env as a fallback,
  which is more portable for team environments.

  ~/.cdsapirc format:
      url: https://cds.climate.copernicus.eu/api
      key: <your-uid>:<your-api-key>

Output
------
  ERA5 data is downloaded as NetCDF files into data/raw/era5/.
  The _normalise() step converts NetCDF → flat hourly DataFrame.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.ingestion.base_fetcher import BaseFetcher
from src.schema.master_schema import COLUMN_NAMES, empty_master_dataframe
from src.utils.config_loader import get_env
from src.utils.logger import get_logger

log = get_logger(__name__)

# CDS variable names → master schema column names (single-level)
_SINGLE_LEVEL_MAP: dict[str, str] = {
    "2m_temperature":                    "temperature",
    "10m_u_component_of_wind":           "_u_wind",     # combined below
    "10m_v_component_of_wind":           "_v_wind",
    "surface_pressure":                  "surface_pressure",
    "total_precipitation":               "precipitation",
    "surface_solar_radiation_downwards": "solar_radiation",
    "boundary_layer_height":             "pbl_height",
}

# xarray variable names inside the NetCDF file (short names from ECMWF)
_NETCDF_VAR_MAP: dict[str, str] = {
    "t2m":    "temperature",
    "u10":    "_u_wind",
    "v10":    "_v_wind",
    "sp":     "surface_pressure",
    "tp":     "precipitation",
    "ssrd":   "solar_radiation",
    "blh":    "pbl_height",
    "r":      "relative_humidity",   # pressure-level relative humidity
    "t":      "_temp_plevel",        # pressure-level temperature (multi-level)
    "q":      "_specific_humidity",  # specific humidity at pressure levels
}


class ERA5Fetcher(BaseFetcher):
    """
    Downloads ERA5 reanalysis NetCDF files from CDS and converts them
    to hourly DataFrames for the Delhi NCR domain.

    This fetcher always runs in 'historical' mode.

    Example
    -------
    >>> fetcher = ERA5Fetcher()
    >>> df = fetcher.run(
    ...     mode="historical",
    ...     start_date="2023-10-01",
    ...     end_date="2023-10-31",
    ... )
    >>> df[["timestamp_utc", "latitude", "longitude", "temperature", "pbl_height"]].head()
    """

    def __init__(self) -> None:
        super().__init__("era5")
        self._download_dir: Path = (
            self._project_root / self.config.get("download_dir", "data/raw/era5")
        )
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._timeout: int = int(self.config.get("request_timeout_sec", 600))

    # ------------------------------------------------------------------
    # BaseFetcher interface
    # ------------------------------------------------------------------

    def _fetch_raw(self, **kwargs) -> dict:
        """
        Download ERA5 NetCDF files via cdsapi.

        Returns a dict with keys:
          "single_level_file"  : Path to downloaded single-level NetCDF
          "pressure_level_file": Path to downloaded pressure-level NetCDF

        Raises ImportError if cdsapi is not installed.
        Raises EnvironmentError if CDS credentials are not configured.
        """
        try:
            import cdsapi  # noqa: F401 — import check
        except ImportError:
            raise ImportError(
                "The 'cdsapi' package is required for ERA5 downloads.\n"
                "Install it with:  pip install cdsapi\n"
                "Then configure your CDS credentials in ~/.cdsapirc "
                "or set CDS_API_KEY and CDS_API_URL in your .env file."
            )

        mode = kwargs.get("mode", "historical")
        if mode != "historical":
            raise ValueError(
                "ERA5Fetcher only supports mode='historical'. "
                "Use OpenMeteoFetcher for real-time weather data."
            )

        start_date = kwargs.get("start_date", self.config.get("historical_start"))
        end_date = kwargs.get("end_date", self.config.get("historical_end"))

        if not start_date or not end_date:
            raise ValueError(
                "ERA5 fetch requires start_date and end_date. "
                "Pass them as kwargs or set historical_start/historical_end "
                "in config/data_sources.yaml."
            )

        log.info(
            f"[era5] Requesting ERA5 data: {start_date} → {end_date} | "
            f"area={self.config['area']}"
        )

        c = self._build_cds_client()
        years, months, days = self._expand_date_range(start_date, end_date)

        # --- Single-level download ---
        sl_file = self._download_single_level(c, years, months, days)

        # --- Pressure-level download ---
        pl_file = self._download_pressure_levels(c, years, months, days)

        return {
            "single_level_file": sl_file,
            "pressure_level_file": pl_file,
            "start_date": start_date,
            "end_date": end_date,
        }

    def _normalise(self, raw_data: dict, **kwargs) -> pd.DataFrame:
        """
        Convert ERA5 NetCDF files to the master schema DataFrame.

        Requires xarray and netCDF4/cfgrib to read the files.
        """
        try:
            import xarray as xr
        except ImportError:
            raise ImportError(
                "The 'xarray' package is required to process ERA5 NetCDF files.\n"
                "Install it with:  pip install xarray netCDF4"
            )

        sl_file: Path = raw_data["single_level_file"]
        pl_file: Path = raw_data["pressure_level_file"]

        log.info(f"[era5] Opening single-level file: {sl_file}")
        ds_sl = xr.open_dataset(str(sl_file))

        log.info(f"[era5] Opening pressure-level file: {pl_file}")
        ds_pl = xr.open_dataset(str(pl_file))

        # Convert to DataFrames
        df_sl = self._xr_to_dataframe(ds_sl, is_pressure_level=False)
        df_pl = self._xr_to_dataframe(ds_pl, is_pressure_level=True)

        ds_sl.close()
        ds_pl.close()

        # Merge on time × lat × lon
        if df_sl.empty:
            log.warning("[era5] Single-level DataFrame is empty after conversion.")
            return empty_master_dataframe()

        if not df_pl.empty:
            merge_keys = ["timestamp_utc", "latitude", "longitude"]
            df_merged = df_sl.merge(df_pl, on=merge_keys, how="left")
        else:
            log.warning("[era5] Pressure-level DataFrame is empty — skipping merge.")
            df_merged = df_sl

        # Apply schema columns
        base = empty_master_dataframe()
        df_out = pd.concat([base, df_merged], ignore_index=True)

        # Drop non-schema columns
        extra = [c for c in df_out.columns if c not in COLUMN_NAMES]
        if extra:
            df_out = df_out.drop(columns=extra)

        df_out["data_source"] = "era5"

        # ERA5 is gridded — no station_id
        # station_id stays NaN; spatial join to stations happens in pipeline

        log.info(
            f"[era5] Normalised {len(df_out)} grid-point rows from ERA5 NetCDF."
        )
        return df_out

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_cds_client(self):
        """
        Build a cdsapi.Client, injecting credentials from .env if
        ~/.cdsapirc is absent.
        """
        import cdsapi

        # If ~/.cdsapirc exists, cdsapi will use it automatically
        cdsapirc = Path.home() / ".cdsapirc"
        if cdsapirc.exists():
            log.debug("[era5] Using credentials from ~/.cdsapirc")
            return cdsapi.Client(quiet=True, wait_until_complete=True)

        # Otherwise, read from environment
        log.debug("[era5] ~/.cdsapirc not found — reading CDS credentials from .env")
        api_key = get_env("CDS_API_KEY", required=True)
        api_url = os.getenv("CDS_API_URL", "https://cds.climate.copernicus.eu/api")

        return cdsapi.Client(
            url=api_url,
            key=api_key,
            quiet=True,
            wait_until_complete=True,
        )

    def _expand_date_range(
        self, start_date: str, end_date: str
    ) -> tuple[list[str], list[str], list[str]]:
        """
        Expand a date range into sorted unique year/month/day lists
        for CDS API requests.
        """
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        years: set[str] = set()
        months: set[str] = set()
        days: set[str] = set()

        current = start
        while current <= end:
            years.add(str(current.year))
            months.add(f"{current.month:02d}")
            days.add(f"{current.day:02d}")
            current = current.replace(day=1)
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return sorted(years), sorted(months), sorted(days)

    def _download_single_level(
        self, client, years: list[str], months: list[str], days: list[str]
    ) -> Path:
        """Download ERA5 single-level variables. Returns path to NetCDF file."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        outfile = self._download_dir / f"{ts}_era5_single_level.nc"

        request = {
            "product_type": "reanalysis",
            "variable": self.config.get("single_level_variables", []),
            "year": years,
            "month": months,
            "day": days,
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": self.config.get("area", [33.0, 72.5, 27.0, 80.0]),
            "grid": self.config.get("grid", [0.25, 0.25]),
            "format": "netcdf",
        }

        log.info(
            f"[era5] Submitting single-level CDS request → {outfile.name} "
            f"(this may take several minutes) …"
        )
        client.retrieve(
            self.config.get("single_level_dataset", "reanalysis-era5-single-levels"),
            request,
            str(outfile),
        )
        log.info(f"[era5] Single-level download complete: {outfile}")
        return outfile

    def _download_pressure_levels(
        self, client, years: list[str], months: list[str], days: list[str]
    ) -> Path:
        """Download ERA5 pressure-level temperature. Returns path to NetCDF file."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        outfile = self._download_dir / f"{ts}_era5_pressure_levels.nc"

        request = {
            "product_type": "reanalysis",
            "variable": self.config.get(
                "pressure_level_variables", ["temperature", "specific_humidity"]
            ),
            "pressure_level": self.config.get("pressure_levels", ["700", "850", "925"]),
            "year": years,
            "month": months,
            "day": days,
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": self.config.get("area", [33.0, 72.5, 27.0, 80.0]),
            "grid": self.config.get("grid", [0.25, 0.25]),
            "format": "netcdf",
        }

        log.info(
            f"[era5] Submitting pressure-level CDS request → {outfile.name} "
            f"(this may take several minutes) …"
        )
        client.retrieve(
            self.config.get("pressure_level_dataset", "reanalysis-era5-pressure-levels"),
            request,
            str(outfile),
        )
        log.info(f"[era5] Pressure-level download complete: {outfile}")
        return outfile

    def _xr_to_dataframe(
        self, ds, is_pressure_level: bool = False
    ) -> pd.DataFrame:
        """
        Convert an xarray Dataset to a flat pandas DataFrame.

        For single-level data:
          - Converts K → °C for temperature
          - Converts Pa → hPa for surface pressure
          - Computes wind speed + direction from U/V components
          - Converts J/m² → W/m² for solar radiation (hourly accumulation)
          - Converts m of water → mm/hr for precipitation

        For pressure-level data:
          - Extracts temperature at 925, 850, 700 hPa
          - Converts K → °C
        """
        try:
            df = ds.to_dataframe().reset_index()
        except Exception as exc:
            log.error(f"[era5] Failed to convert xarray Dataset to DataFrame: {exc}")
            return pd.DataFrame()

        # Rename dimension columns
        rename = {}
        if "valid_time" in df.columns:
            rename["valid_time"] = "timestamp_utc"
        elif "time" in df.columns:
            rename["time"] = "timestamp_utc"
        if "latitude" in df.columns:
            rename["latitude"] = "latitude"
        if "longitude" in df.columns:
            rename["longitude"] = "longitude"
        if "lat" in df.columns:
            rename["lat"] = "latitude"
        if "lon" in df.columns:
            rename["lon"] = "longitude"
        df = df.rename(columns=rename)

        if is_pressure_level:
            return self._process_pressure_levels(df)
        else:
            return self._process_single_level(df)

    def _process_single_level(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply unit conversions for single-level ERA5 variables."""
        out = pd.DataFrame()
        out["timestamp_utc"] = pd.to_datetime(df.get("timestamp_utc"), utc=True)
        out["latitude"] = df.get("latitude")
        out["longitude"] = df.get("longitude")

        # Temperature: Kelvin → Celsius
        if "t2m" in df.columns:
            out["temperature"] = df["t2m"] - 273.15

        # Wind: U + V components → speed (m/s) + direction (degrees)
        if "u10" in df.columns and "v10" in df.columns:
            u = df["u10"]
            v = df["v10"]
            out["wind_speed"] = np.sqrt(u**2 + v**2)
            # Meteorological convention: direction the wind comes FROM
            out["wind_direction"] = (270 - np.degrees(np.arctan2(v, u))) % 360

        # Surface pressure: Pa → hPa
        if "sp" in df.columns:
            out["surface_pressure"] = df["sp"] / 100.0

        # Precipitation: m (hourly accumulation) → mm
        if "tp" in df.columns:
            out["precipitation"] = df["tp"] * 1000.0
            out["precipitation"] = out["precipitation"].clip(lower=0.0)

        # Solar radiation: J/m² (hourly accumulation) → W/m² (÷3600)
        if "ssrd" in df.columns:
            out["solar_radiation"] = (df["ssrd"] / 3600.0).clip(lower=0.0)

        # Boundary layer height: already in metres
        if "blh" in df.columns:
            out["pbl_height"] = df["blh"]

        # Relative humidity (if available at single level)
        if "r" in df.columns:
            out["relative_humidity"] = df["r"]

        return out

    def _process_pressure_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract temperature at each pressure level and pivot to wide format."""
        if "pressure_level" not in df.columns and "level" not in df.columns:
            log.warning("[era5] No pressure level dimension found in DataFrame.")
            return pd.DataFrame()

        level_col = "pressure_level" if "pressure_level" in df.columns else "level"
        target_levels = {925: "temp_925hpa", 850: "temp_850hpa", 700: "temp_700hpa"}

        out_parts: list[pd.DataFrame] = []

        for level, col_name in target_levels.items():
            subset = df[df[level_col] == level].copy()
            if subset.empty:
                log.warning(f"[era5] No data found for pressure level {level} hPa.")
                continue
            temp_col = next((c for c in ["t", "temperature"] if c in subset.columns), None)
            if temp_col is None:
                continue
            part = pd.DataFrame({
                "timestamp_utc": pd.to_datetime(subset.get("timestamp_utc"), utc=True),
                "latitude": subset.get("latitude"),
                "longitude": subset.get("longitude"),
                col_name: subset[temp_col] - 273.15,  # K → °C
            })
            out_parts.append(part)

        if not out_parts:
            return pd.DataFrame()

        # Merge all levels on time × lat × lon
        result = out_parts[0]
        for other in out_parts[1:]:
            result = result.merge(
                other, on=["timestamp_utc", "latitude", "longitude"], how="outer"
            )
        return result
