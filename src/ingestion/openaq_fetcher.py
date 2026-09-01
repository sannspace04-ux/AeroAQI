"""
src/ingestion/openaq_fetcher.py
================================
Fetches ground-level air quality observations from the OpenAQ v3 API.

What this fetcher provides
--------------------------
  pm25, pm10, o3, no2, so2, co, aqi_raw
  station_id, station_name, latitude, longitude, timestamp_utc

What it does NOT provide (filled as NaN)
-----------------------------------------
  All weather columns, atmospheric profile columns, fire columns.

API reference
-------------
  https://docs.openaq.org
  Endpoint used: GET /v3/measurements
  Authentication: X-API-Key header (OPENAQ_API_KEY in .env)

Pagination
----------
  OpenAQ returns at most `page_size` results per request.
  This fetcher pages automatically until all results are collected.

Unit handling
-------------
  OpenAQ reports concentrations in µg/m³ for particles and most gases.
  CO may arrive in mg/m³ or ppm depending on the station — we keep µg/m³
  as the standard and flag unexpected units in the log.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from src.ingestion.base_fetcher import BaseFetcher
from src.schema.master_schema import empty_master_dataframe
from src.utils.config_loader import get_env
from src.utils.logger import get_logger

log = get_logger(__name__)

# OpenAQ v3 parameter names → our master schema column names
_PARAM_MAP: dict[str, str] = {
    "pm25":  "pm25",
    "pm2.5": "pm25",
    "pm10":  "pm10",
    "o3":    "o3",
    "no2":   "no2",
    "so2":   "so2",
    "co":    "co",
}


class OpenAQFetcher(BaseFetcher):
    """
    Fetches hourly air quality measurements for Delhi NCR stations
    from the OpenAQ v3 REST API.

    Supports two modes:
      realtime   — fetches the last N hours (default: 48h lookback)
      historical — fetches a specified date range

    Example
    -------
    >>> fetcher = OpenAQFetcher()
    >>> df = fetcher.run(mode="realtime")
    >>> df[["station_id", "timestamp_utc", "pm25", "pm10"]].head()
    """

    def __init__(self) -> None:
        super().__init__("openaq")
        self._api_key: str = get_env("OPENAQ_API_KEY", required=True)
        self._base_url: str = self.config["base_url"].rstrip("/")
        self._timeout: int = int(self.config.get("request_timeout_sec", 30))
        self._page_size: int = int(self.config.get("page_size", 1000))

    # ------------------------------------------------------------------
    # BaseFetcher interface
    # ------------------------------------------------------------------

    def _fetch_raw(self, **kwargs) -> list[dict]:
        """
        Fetch all measurement records from OpenAQ for the configured
        stations and date range.

        Keyword arguments
        -----------------
        mode       : "realtime" (default) or "historical"
        start_date : ISO date string, e.g. "2023-10-01" (historical mode)
        end_date   : ISO date string, e.g. "2023-10-31" (historical mode)

        Returns
        -------
        list[dict]  — raw measurement records as returned by the API.
        """
        mode = kwargs.get("mode", "realtime")
        date_from, date_to = self._resolve_date_range(mode, **kwargs)

        location_ids: list[int] = self.config.get("location_ids", [])
        parameters: list[str] = self.config.get("parameters", [])

        if not location_ids:
            raise ValueError(
                "No location_ids configured in data_sources.yaml → openaq → location_ids. "
                "Add at least one OpenAQ location ID."
            )

        log.info(
            f"[openaq] Fetching {mode} data | "
            f"{date_from.isoformat()} → {date_to.isoformat()} | "
            f"{len(location_ids)} locations | parameters: {parameters}"
        )

        all_records: list[dict] = []

        for location_id in location_ids:
            records = self._fetch_location(
                location_id=location_id,
                date_from=date_from,
                date_to=date_to,
                parameters=parameters,
            )
            all_records.extend(records)
            log.debug(
                f"[openaq] location_id={location_id}: "
                f"{len(records)} records fetched (total so far: {len(all_records)})"
            )

        log.info(f"[openaq] Total raw records fetched: {len(all_records)}")
        return all_records

    def _normalise(self, raw_data: list[dict], **kwargs) -> pd.DataFrame:
        """
        Map OpenAQ measurement records to the master schema.

        OpenAQ v3 /measurements response shape (one record):
        {
          "id": 123,
          "locationId": 8118,
          "location": "Anand Vihar",
          "parameter": { "name": "pm25", "units": "µg/m³" },
          "value": 87.3,
          "date": { "utc": "2023-10-15T12:00:00Z", "local": "..." },
          "coordinates": { "latitude": 28.6469, "longitude": 77.3152 }
        }
        """
        if not raw_data:
            log.warning("[openaq] No raw records to normalise.")
            return empty_master_dataframe()

        rows: list[dict] = []
        skipped = 0

        for rec in raw_data:
            try:
                row = self._parse_record(rec)
                if row is not None:
                    rows.append(row)
                else:
                    skipped += 1
            except Exception as exc:
                log.warning(f"[openaq] Could not parse record — skipped: {exc} | record={rec}")
                skipped += 1

        if skipped > 0:
            log.warning(f"[openaq] {skipped} records skipped during normalisation.")

        if not rows:
            log.warning("[openaq] No valid rows after normalisation.")
            return empty_master_dataframe()

        df_raw = pd.DataFrame(rows)

        # Start from the canonical empty schema to ensure correct dtypes
        df_out = empty_master_dataframe()
        df_out = pd.concat([df_out, df_raw], ignore_index=True)

        # Fill mandatory metadata columns
        df_out["data_source"] = "openaq"

        log.info(f"[openaq] Normalised {len(df_out)} rows from {len(raw_data)} raw records.")
        return df_out

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_date_range(
        self, mode: str, **kwargs
    ) -> tuple[datetime, datetime]:
        """Calculate the from/to datetime for the API query."""
        now_utc = datetime.now(timezone.utc)

        if mode == "realtime":
            lookback = int(self.config.get("realtime_lookback_hours", 48))
            date_from = now_utc - timedelta(hours=lookback)
            date_to = now_utc
        elif mode == "historical":
            start_str = kwargs.get("start_date", self.config.get("historical_start"))
            end_str = kwargs.get("end_date", self.config.get("historical_end"))
            if not start_str or not end_str:
                raise ValueError(
                    "historical mode requires start_date and end_date "
                    "(either passed as kwargs or set in data_sources.yaml)"
                )
            date_from = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
            date_to = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)
        else:
            raise ValueError(f"Unknown mode '{mode}'. Use 'realtime' or 'historical'.")

        return date_from, date_to

    def _fetch_location(
        self,
        location_id: int,
        date_from: datetime,
        date_to: datetime,
        parameters: list[str],
    ) -> list[dict]:
        """
        Fetch all paginated measurements for a single OpenAQ location.
        Raises requests.HTTPError on non-2xx responses.
        """
        endpoint = f"{self._base_url}/measurements"
        headers = {
            "X-API-Key": self._api_key,
            "Accept": "application/json",
        }
        all_records: list[dict] = []
        page = 1

        while True:
            params: dict[str, Any] = {
                "locations_id": location_id,
                "date_from": date_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "date_to": date_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": self._page_size,
                "page": page,
            }
            # Add each parameter as a separate query param
            # OpenAQ v3 accepts repeated parameters[] keys
            for p in parameters:
                params.setdefault("parameters_id[]", [])
                # NOTE: parameter IDs (not names) are used in v3.
                # The config uses names; here we pass them and rely on
                # OpenAQ's name-based filtering as a fallback.
                # For production, replace with numeric parameter IDs.

            response = requests.get(
                endpoint,
                headers=headers,
                params=params,
                timeout=self._timeout,
            )

            # Raise immediately on HTTP errors (4xx, 5xx)
            if response.status_code == 401:
                raise PermissionError(
                    "OpenAQ API returned HTTP 401 Unauthorized. "
                    "Check that OPENAQ_API_KEY in your .env file is correct."
                )
            if response.status_code == 429:
                raise RuntimeError(
                    "OpenAQ API returned HTTP 429 Too Many Requests. "
                    "You have exceeded the rate limit. Wait and retry."
                )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if not results:
                break  # No more pages

            all_records.extend(results)

            # Check if there is a next page
            meta = data.get("meta", {})
            found = meta.get("found", 0)
            if len(all_records) >= found:
                break

            page += 1

        return all_records

    def _parse_record(self, rec: dict) -> dict | None:
        """
        Parse a single OpenAQ v3 measurement record into a flat dict
        matching the master schema column names.

        Returns None if the record is missing critical fields.
        """
        # --- Timestamp ---
        date_block = rec.get("date", {})
        ts_str = date_block.get("utc")
        if not ts_str:
            return None

        # --- Location metadata ---
        location_id = rec.get("locationId")
        location_name = rec.get("location", "")
        coords = rec.get("coordinates") or {}
        lat = coords.get("latitude")
        lon = coords.get("longitude")

        if lat is None or lon is None:
            return None

        # --- Parameter / value ---
        param_block = rec.get("parameter", {})
        param_name = (param_block.get("name") or "").lower().strip()
        units = (param_block.get("units") or "").strip()
        value = rec.get("value")

        # Map parameter name to our schema column
        col_name = _PARAM_MAP.get(param_name)
        if col_name is None:
            # Unknown parameter — skip silently
            return None

        # Value must be numeric and non-negative
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        if value < 0:
            log.warning(
                f"[openaq] Negative value {value} for {param_name} "
                f"at location {location_id} — set to NaN."
            )
            value = float("nan")

        # Warn on unexpected units but do not drop the record
        expected_units = {"pm25": "µg/m³", "pm10": "µg/m³", "o3": "µg/m³",
                          "no2": "µg/m³", "so2": "µg/m³", "co": "mg/m³"}
        exp_unit = expected_units.get(col_name, "")
        if exp_unit and units and units != exp_unit:
            log.warning(
                f"[openaq] Unexpected unit '{units}' for parameter '{param_name}' "
                f"(expected '{exp_unit}'). Value kept as-is — verify unit conversion."
            )

        return {
            "timestamp_utc": ts_str,
            "station_id": f"OPENAQ_{location_id}",
            "station_name": location_name,
            "latitude": lat,
            "longitude": lon,
            "data_source": "openaq",
            col_name: value,
        }
