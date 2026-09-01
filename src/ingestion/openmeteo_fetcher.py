"""
src/ingestion/openmeteo_fetcher.py
===================================
Fetches weather forecast + atmospheric profile data from the Open-Meteo API.

What this fetcher provides
--------------------------
  temperature, relative_humidity, wind_speed, wind_direction,
  surface_pressure, precipitation, solar_radiation,
  pbl_height (boundary layer height from ECMWF model),
  temp_925hpa, temp_850hpa, temp_700hpa  (for inversion detection)

What it does NOT provide (filled as NaN)
-----------------------------------------
  All air quality columns (pm25, pm10, etc.), fire columns.

API reference
-------------
  https://open-meteo.com/en/docs
  No API key required for non-commercial use.

One row per (station, hour)
---------------------------
  Open-Meteo is a grid model; we query it once per station location
  using the station's lat/lon so the output is already point-matched.
  Each station gets its own set of hourly weather rows.

Historical mode
---------------
  Uses the ERA5-backed archive endpoint:
  https://archive-api.open-meteo.com/v1/archive
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from src.ingestion.base_fetcher import BaseFetcher
from src.schema.master_schema import empty_master_dataframe
from src.utils.config_loader import load_stations
from src.utils.logger import get_logger

log = get_logger(__name__)

# Open-Meteo variable names → master schema column names
_SURFACE_VAR_MAP: dict[str, str] = {
    "temperature_2m":          "temperature",
    "relative_humidity_2m":    "relative_humidity",
    "wind_speed_10m":          "wind_speed",
    "wind_direction_10m":      "wind_direction",
    "surface_pressure":        "surface_pressure",
    "precipitation":           "precipitation",
    "shortwave_radiation":     "solar_radiation",
    "boundary_layer_height":   "pbl_height",
}

# Pressure level temperature variable names Open-Meteo uses
# We request temperature at 925, 850, 700 hPa
_PLEVEL_COLS: dict[str, str] = {
    "temperature_925hPa": "temp_925hpa",
    "temperature_850hPa": "temp_850hpa",
    "temperature_700hPa": "temp_700hpa",
}


class OpenMeteoFetcher(BaseFetcher):
    """
    Fetches hourly weather + atmospheric profile data from Open-Meteo
    for each Delhi NCR monitoring station.

    Each station in stations.yaml is queried independently so that
    weather data is co-located with the air quality observations.

    Example
    -------
    >>> fetcher = OpenMeteoFetcher()
    >>> df = fetcher.run(mode="realtime")
    >>> df[["station_id", "timestamp_utc", "temperature", "pbl_height"]].head()
    """

    def __init__(self) -> None:
        super().__init__("openmeteo")
        self._stations: list[dict] = load_stations()
        self._timeout: int = int(self.config.get("request_timeout_sec", 30))

    # ------------------------------------------------------------------
    # BaseFetcher interface
    # ------------------------------------------------------------------

    def _fetch_raw(self, **kwargs) -> list[dict]:
        """
        Query Open-Meteo for every active station.

        Returns
        -------
        list[dict]  — one dict per station, containing the full
                      Open-Meteo JSON response plus injected station metadata.
        """
        mode = kwargs.get("mode", "realtime")
        active_stations = [s for s in self._stations if s.get("active", True)]

        log.info(
            f"[openmeteo] Fetching {mode} weather for "
            f"{len(active_stations)} stations …"
        )

        all_responses: list[dict] = []

        for station in active_stations:
            station_id = station["station_id"]
            lat = station["latitude"]
            lon = station["longitude"]

            try:
                response_json = self._query_station(lat, lon, mode, **kwargs)
                # Attach station metadata so _normalise can use it
                response_json["_station_id"] = station_id
                response_json["_station_name"] = station["name"]
                response_json["_latitude"] = lat
                response_json["_longitude"] = lon
                all_responses.append(response_json)
                log.debug(f"[openmeteo] Fetched station {station_id}")
            except Exception as exc:
                # One failing station should not abort all others
                log.error(
                    f"[openmeteo] Failed to fetch station {station_id} "
                    f"({lat}, {lon}): {exc}"
                )

        log.info(
            f"[openmeteo] Raw fetch complete — "
            f"{len(all_responses)}/{len(active_stations)} stations succeeded."
        )
        return all_responses

    def _normalise(self, raw_data: list[dict], **kwargs) -> pd.DataFrame:
        """
        Convert per-station Open-Meteo JSON responses into a single
        DataFrame matching the master schema.
        """
        if not raw_data:
            log.warning("[openmeteo] No raw data to normalise.")
            return empty_master_dataframe()

        all_dfs: list[pd.DataFrame] = []

        for station_response in raw_data:
            df_station = self._parse_station_response(station_response)
            if df_station is not None and not df_station.empty:
                all_dfs.append(df_station)

        if not all_dfs:
            log.warning("[openmeteo] All station parses returned empty DataFrames.")
            return empty_master_dataframe()

        df_out = pd.concat(all_dfs, ignore_index=True)
        df_out["data_source"] = "openmeteo"

        log.info(f"[openmeteo] Normalised {len(df_out)} rows across {len(all_dfs)} stations.")
        return df_out

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _query_station(self, lat: float, lon: float, mode: str, **kwargs) -> dict:
        """
        Build and execute one Open-Meteo HTTP request for a single location.
        Returns the parsed JSON response dict.
        """
        if mode == "realtime":
            base_url = self.config["base_url"]
            forecast_hours = int(self.config.get("forecast_hours", 72))
            params = self._build_forecast_params(lat, lon, forecast_hours)
        elif mode == "historical":
            base_url = self.config["historical_base_url"]
            start_date = kwargs.get("start_date", self.config.get("historical_start"))
            end_date = kwargs.get("end_date")
            if not end_date:
                # Default to yesterday (ERA5 has ~5 day latency)
                end_date = (datetime.now(timezone.utc) - timedelta(days=6)).strftime("%Y-%m-%d")
            params = self._build_historical_params(lat, lon, start_date, end_date)
        else:
            raise ValueError(f"Unknown mode '{mode}'. Use 'realtime' or 'historical'.")

        response = requests.get(base_url, params=params, timeout=self._timeout)

        if response.status_code != 200:
            raise RuntimeError(
                f"Open-Meteo returned HTTP {response.status_code}: {response.text[:200]}"
            )

        data = response.json()

        # Open-Meteo returns an error field when request is invalid
        if "error" in data and data["error"]:
            raise RuntimeError(
                f"Open-Meteo API error: {data.get('reason', data)}"
            )

        return data

    def _build_forecast_params(
        self, lat: float, lon: float, forecast_hours: int
    ) -> dict:
        """Build query parameters for the forecast endpoint."""
        hourly_vars = list(self.config.get("hourly_variables", []))
        pressure_vars = [
            f"temperature_{lvl}hPa"
            for lvl in self.config.get("pressure_levels", [925, 850, 700])
        ]
        return {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(hourly_vars + pressure_vars),
            "forecast_hours": forecast_hours,
            "timezone": "UTC",
            "timeformat": "iso8601",
        }

    def _build_historical_params(
        self, lat: float, lon: float, start_date: str, end_date: str
    ) -> dict:
        """Build query parameters for the historical archive endpoint."""
        hourly_vars = list(self.config.get("hourly_variables", []))
        pressure_vars = [
            f"temperature_{lvl}hPa"
            for lvl in self.config.get("pressure_levels", [925, 850, 700])
        ]
        return {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(hourly_vars + pressure_vars),
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "UTC",
            "timeformat": "iso8601",
        }

    def _parse_station_response(self, resp: dict) -> pd.DataFrame | None:
        """
        Convert a single-station Open-Meteo JSON response to a DataFrame.

        Open-Meteo hourly response shape:
        {
          "latitude": 28.6469,
          "longitude": 77.3152,
          "hourly": {
            "time":                   ["2023-10-15T00:00", ...],
            "temperature_2m":         [28.1, 27.9, ...],
            "relative_humidity_2m":   [65, 67, ...],
            ...
            "temperature_925hPa":     [26.3, ...],
            "temperature_850hPa":     [22.1, ...],
            "temperature_700hPa":     [14.5, ...]
          }
        }
        """
        station_id = resp.get("_station_id", "UNKNOWN")
        hourly = resp.get("hourly")

        if not hourly or "time" not in hourly:
            log.warning(
                f"[openmeteo] Station {station_id} response missing 'hourly' block."
            )
            return None

        # Build a flat DataFrame from the hourly dict
        df = pd.DataFrame(hourly)

        if df.empty or "time" not in df.columns:
            return None

        # Rename Open-Meteo variable names to master schema names
        rename_map = {**_SURFACE_VAR_MAP, **_PLEVEL_COLS}
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        # Rename 'time' → 'timestamp_utc'
        df = df.rename(columns={"time": "timestamp_utc"})

        # Inject station metadata
        df["station_id"] = resp["_station_id"]
        df["station_name"] = resp["_station_name"]
        df["latitude"] = resp["_latitude"]
        df["longitude"] = resp["_longitude"]

        # Start from canonical schema to ensure all columns exist
        base = empty_master_dataframe()
        df_out = pd.concat([base, df], ignore_index=True)

        # Drop columns not in our schema (Open-Meteo may return extras)
        from src.schema.master_schema import COLUMN_NAMES
        extra_cols = [c for c in df_out.columns if c not in COLUMN_NAMES]
        if extra_cols:
            df_out = df_out.drop(columns=extra_cols)

        return df_out
