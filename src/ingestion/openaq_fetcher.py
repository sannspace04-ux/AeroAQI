"""
src/ingestion/openaq_fetcher.py
================================
Fetches ground-level air quality observations from the OpenAQ v3 API.

What this fetcher provides
--------------------------
  pm25, pm10, o3, no2, so2, co
  station_id, station_name, latitude, longitude, timestamp_utc

What it does NOT provide (filled as NaN)
-----------------------------------------
  All weather columns, atmospheric profile columns, fire columns.

API reference (v3 — current as of 2024)
-----------------------------------------
  https://docs.openaq.org

  The /v3/measurements?locations_id=N flat endpoint was REMOVED.
  The correct v3 flow is:

    Step 1: GET /v3/locations/{location_id}/sensors
            → returns a list of sensor objects, each with an integer id
              and a parameter description (pm25, pm10, no2 …)

    Step 2: GET /v3/sensors/{sensor_id}/hours
              ?datetime_from=YYYY-MM-DDTHH:MM:SSZ
              &datetime_to=YYYY-MM-DDTHH:MM:SSZ
              &limit=1000&page=1
            → returns hourly averaged measurements for that sensor

  Authentication: X-API-Key header (OPENAQ_API_KEY in .env)

Response shapes
---------------
  /v3/locations/{id}/sensors  — one result per sensor:
  {
    "id": 23534,
    "name": "pm25 µg/m³",
    "parameter": { "id": 2, "name": "pm25", "units": "µg/m³", "displayName": "PM2.5" },
    "datetimeFirst": { "utc": "2016-11-09T19:00:00Z", ... },
    "datetimeLast":  { "utc": "2024-12-13T14:30:00Z", ... },
    ...
  }

  /v3/sensors/{id}/hours  — one result per hour:
  {
    "value": 87.3,
    "parameter": { "id": 2, "name": "pm25", "units": "µg/m³", ... },
    "period": {
      "datetimeFrom": { "utc": "2024-09-01T10:00:00Z", ... },
      "datetimeTo":   { "utc": "2024-09-01T11:00:00Z", ... }
    },
    "coordinates": { "latitude": 28.6469, "longitude": 77.3152 },
    "coverage": { ... }
  }

Station ID mapping
------------------
  OpenAQ location IDs (e.g. 8118) are mapped to the canonical AeroAQI
  station_id (e.g. "DEL_ANAND_VIHAR") using the openaq_id field in
  config/stations.yaml.  This ensures the fetcher's output joins
  correctly with all other tables.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from src.ingestion.base_fetcher import BaseFetcher
from src.schema.master_schema import empty_master_dataframe
from src.utils.config_loader import get_env, load_stations
from src.utils.logger import get_logger

log = get_logger(__name__)

# OpenAQ v3 parameter names → master schema column names
_PARAM_MAP: dict[str, str] = {
    "pm25":  "pm25",
    "pm2.5": "pm25",
    "pm10":  "pm10",
    "o3":    "o3",
    "no2":   "no2",
    "so2":   "so2",
    "co":    "co",
}


def _build_location_map() -> dict[int, dict]:
    """
    Build a mapping:  openaq_location_id (int) → station metadata dict.

    Uses the openaq_id field in config/stations.yaml so that parsed
    records carry the canonical station_id (e.g. "DEL_ANAND_VIHAR")
    rather than "OPENAQ_8118".

    Returns an empty dict if stations cannot be loaded.
    """
    try:
        stations = load_stations()
        return {
            int(s["openaq_id"]): s
            for s in stations
            if s.get("openaq_id") is not None
        }
    except Exception as exc:
        log.warning(f"[openaq] Could not build location→station map: {exc}")
        return {}


class OpenAQFetcher(BaseFetcher):
    """
    Fetches hourly air quality measurements for Delhi NCR stations
    from the OpenAQ v3 REST API using the sensor-based endpoint flow.

    Step 1: discover sensor IDs for each configured location
    Step 2: fetch hourly measurements for each sensor

    Supports two modes:
      realtime   — fetches the last N hours (default: 48 h lookback)
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
        self._location_map: dict[int, dict] = _build_location_map()

    # ------------------------------------------------------------------
    # BaseFetcher interface
    # ------------------------------------------------------------------

    def _fetch_raw(self, **kwargs) -> list[dict]:
        """
        Fetch all hourly measurement records from OpenAQ v3 for all
        configured station locations.

        Flow:
          1. For each location_id, GET /v3/locations/{id}/sensors to
             discover which sensor IDs (and parameters) are available.
          2. For each sensor whose parameter is in _PARAM_MAP, GET
             /v3/sensors/{sensor_id}/hours for the date window.
          3. Attach location metadata to each record so _normalise can
             build the master schema without extra lookups.

        Returns
        -------
        list[dict]  — flat list of measurement records; each dict
                      carries both sensor/measurement fields and injected
                      station metadata.
        """
        # Pop 'mode' so it isn't passed twice to _resolve_date_range.
        mode = kwargs.pop("mode", "realtime")
        date_from, date_to = self._resolve_date_range(mode, **kwargs)

        location_ids: list[int] = self.config.get("location_ids", [])
        if not location_ids:
            raise ValueError(
                "No location_ids configured in data_sources.yaml "
                "→ openaq → location_ids."
            )

        log.info(
            f"[openaq] Fetching {mode} data | "
            f"{date_from.isoformat()} → {date_to.isoformat()} | "
            f"{len(location_ids)} locations"
        )

        all_records: list[dict] = []

        for location_id in location_ids:
            try:
                # Step 1: discover sensors for this location
                sensors = self._fetch_sensors(location_id)
                if not sensors:
                    log.info(
                        f"[openaq] location_id={location_id}: "
                        f"no sensors found — skipping."
                    )
                    continue

                # Station metadata for this location (from stations.yaml)
                station_meta = self._location_map.get(int(location_id))

                # Step 2: fetch hourly data per sensor
                for sensor in sensors:
                    sensor_id   = sensor.get("id")
                    param_block = sensor.get("parameter", {})
                    param_name  = (param_block.get("name") or "").lower().strip()

                    # Only fetch parameters we care about
                    if param_name not in _PARAM_MAP:
                        continue

                    records = self._fetch_sensor_hours(
                        sensor_id=sensor_id,
                        param_name=param_name,
                        param_units=param_block.get("units", ""),
                        date_from=date_from,
                        date_to=date_to,
                        location_id=location_id,
                        station_meta=station_meta,
                    )
                    all_records.extend(records)

                log.debug(
                    f"[openaq] location_id={location_id}: "
                    f"total so far {len(all_records)} records"
                )

            except PermissionError:
                raise  # propagate auth errors immediately
            except requests.HTTPError as exc:
                status = (
                    exc.response.status_code
                    if exc.response is not None else "?"
                )
                log.warning(
                    f"[openaq] HTTP {status} for location_id={location_id} "
                    f"— skipping. Error: {exc}"
                )
            except Exception as exc:
                log.warning(
                    f"[openaq] location_id={location_id}: "
                    f"{type(exc).__name__}: {exc} — skipping."
                )

        log.info(f"[openaq] Total raw records fetched: {len(all_records)}")
        return all_records

    def _normalise(self, raw_data: list[dict], **kwargs) -> pd.DataFrame:
        """
        Convert flat measurement record list to master-schema DataFrame.

        Each record in raw_data was built by _fetch_sensor_hours and
        already carries station metadata.  This method just pivots
        multi-pollutant records for the same (timestamp, station) into
        a single wide row.

        Record structure (from _fetch_sensor_hours):
        {
          "timestamp_utc": "2024-09-01T10:00:00Z",
          "station_id":    "DEL_ANAND_VIHAR",
          "station_name":  "Anand Vihar",
          "latitude":      28.6469,
          "longitude":     77.3152,
          "data_source":   "openaq",
          "pm25":          87.3          # only the col for this sensor
        }
        """
        if not raw_data:
            log.warning("[openaq] No raw records to normalise.")
            return empty_master_dataframe()

        # Build a row list, grouping by (timestamp_utc, station_id)
        # so all pollutants for the same hour land in one row.
        # Key: (timestamp_utc, station_id)  Value: merged dict
        grouped: dict[tuple, dict] = {}

        skipped = 0
        for rec in raw_data:
            ts  = rec.get("timestamp_utc")
            sid = rec.get("station_id")
            if not ts or not sid:
                skipped += 1
                continue

            key = (ts, sid)
            if key not in grouped:
                grouped[key] = {
                    "timestamp_utc": ts,
                    "station_id":    sid,
                    "station_name":  rec.get("station_name", ""),
                    "latitude":      rec.get("latitude"),
                    "longitude":     rec.get("longitude"),
                    "data_source":   "openaq",
                }

            # Merge pollutant columns — keep first non-None value per key
            for col in _PARAM_MAP.values():
                if col in rec and rec[col] is not None:
                    grouped[key].setdefault(col, rec[col])

        if skipped:
            log.warning(f"[openaq] {skipped} records dropped (missing ts/station_id).")

        rows = list(grouped.values())
        if not rows:
            log.warning("[openaq] No valid rows after normalisation.")
            return empty_master_dataframe()

        df_raw = pd.DataFrame(rows)
        df_out = empty_master_dataframe()
        df_out = pd.concat([df_out, df_raw], ignore_index=True)
        df_out["data_source"] = "openaq"

        log.info(
            f"[openaq] Normalised {len(df_out)} station-hour rows "
            f"from {len(raw_data)} raw sensor records."
        )
        return df_out

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_date_range(
        self, mode: str, **kwargs
    ) -> tuple[datetime, datetime]:
        """Calculate the from/to datetime window for the API query."""
        now_utc = datetime.now(timezone.utc)

        if mode == "realtime":
            lookback = int(self.config.get("realtime_lookback_hours", 48))
            return now_utc - timedelta(hours=lookback), now_utc

        if mode == "historical":
            start_str = kwargs.get("start_date", self.config.get("historical_start"))
            end_str   = kwargs.get("end_date",   self.config.get("historical_end"))
            if not start_str or not end_str:
                raise ValueError(
                    "historical mode requires start_date and end_date "
                    "(kwargs or data_sources.yaml)"
                )
            date_from = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
            date_to   = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)
            return date_from, date_to

        raise ValueError(f"Unknown mode '{mode}'. Use 'realtime' or 'historical'.")

    def _get_json(self, url: str, params: list[tuple] | None = None) -> dict:
        """
        Execute a GET request and return the parsed JSON.

        Raises
        ------
        PermissionError   on HTTP 401
        RuntimeError      on HTTP 429 (rate-limited)
        requests.HTTPError on other non-2xx responses
        """
        headers = {
            "X-API-Key": self._api_key,
            "Accept": "application/json",
        }
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=self._timeout,
        )
        if response.status_code == 401:
            raise PermissionError(
                "OpenAQ API returned HTTP 401 Unauthorized. "
                "Check OPENAQ_API_KEY in your .env file."
            )
        if response.status_code == 429:
            raise RuntimeError(
                "OpenAQ API returned HTTP 429 Too Many Requests. "
                "You have exceeded the rate limit — wait and retry."
            )
        response.raise_for_status()
        return response.json()

    def _fetch_sensors(self, location_id: int) -> list[dict]:
        """
        GET /v3/locations/{location_id}/sensors

        Returns the list of sensor dicts for this location, or [] on
        a 404 (location ID not in OpenAQ) so the loop can continue.
        """
        url = f"{self._base_url}/locations/{location_id}/sensors"
        try:
            data = self._get_json(url)
            sensors = data.get("results", [])
            log.debug(
                f"[openaq] location_id={location_id}: "
                f"{len(sensors)} sensor(s) discovered."
            )
            return sensors
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                log.warning(
                    f"[openaq] location_id={location_id} not found in OpenAQ "
                    f"(HTTP 404). The location ID may have changed — "
                    f"verify at https://explore.openaq.org."
                )
                return []
            raise

    def _fetch_sensor_hours(
        self,
        sensor_id: int,
        param_name: str,
        param_units: str,
        date_from: datetime,
        date_to: datetime,
        location_id: int,
        station_meta: dict | None,
    ) -> list[dict]:
        """
        GET /v3/sensors/{sensor_id}/hours
            ?datetime_from=...&datetime_to=...&limit=...&page=...

        Paginates automatically.  Returns a list of flat measurement
        dicts ready for _normalise().
        """
        url = f"{self._base_url}/sensors/{sensor_id}/hours"
        col_name = _PARAM_MAP.get(param_name)
        if col_name is None:
            return []

        # Resolve canonical station identity from stations.yaml
        if station_meta:
            canonical_id   = station_meta["station_id"]
            canonical_name = station_meta.get("name", "")
            canonical_lat  = station_meta.get("latitude")
            canonical_lon  = station_meta.get("longitude")
        else:
            canonical_id   = f"OPENAQ_{location_id}"
            canonical_name = ""
            canonical_lat  = None
            canonical_lon  = None

        # Warn on unexpected units (keep value, do not drop)
        expected_units = {
            "pm25": "µg/m³", "pm10": "µg/m³", "o3": "µg/m³",
            "no2":  "µg/m³", "so2":  "µg/m³", "co": "mg/m³",
        }
        exp = expected_units.get(col_name, "")
        if exp and param_units and param_units != exp:
            log.warning(
                f"[openaq] sensor_id={sensor_id} param={param_name}: "
                f"unexpected units '{param_units}' (expected '{exp}'). "
                f"Value kept as-is — verify unit conversion."
            )

        all_records: list[dict] = []
        page = 1

        while True:
            params: list[tuple] = [
                ("datetime_from", date_from.strftime("%Y-%m-%dT%H:%M:%SZ")),
                ("datetime_to",   date_to.strftime("%Y-%m-%dT%H:%M:%SZ")),
                ("limit",         self._page_size),
                ("page",          page),
            ]

            try:
                data = self._get_json(url, params=params)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    log.warning(
                        f"[openaq] sensor_id={sensor_id} not found (HTTP 404). "
                        f"Skipping."
                    )
                    break
                raise

            results = data.get("results", [])
            if not results:
                break

            for r in results:
                # Extract the timestamp from the period.datetimeFrom field
                period = r.get("period", {})
                dt_block = period.get("datetimeFrom", {})
                ts_str = dt_block.get("utc") if dt_block else None
                if not ts_str:
                    continue

                # Extract lat/lon from coordinates (mobile monitoring)
                # For stationary monitors coordinates is null, use station_meta
                coords = r.get("coordinates") or {}
                lat = coords.get("latitude") or canonical_lat
                lon = coords.get("longitude") or canonical_lon

                # Extract measurement value
                value = r.get("value")
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue

                if value < 0:
                    log.warning(
                        f"[openaq] sensor_id={sensor_id}: negative {param_name} "
                        f"value {value} — set to NaN."
                    )
                    value = float("nan")

                all_records.append({
                    "timestamp_utc": ts_str,
                    "station_id":    canonical_id,
                    "station_name":  canonical_name,
                    "latitude":      lat,
                    "longitude":     lon,
                    "data_source":   "openaq",
                    col_name:        value,
                })

            # Pagination: stop when page is shorter than page_size,
            # or when meta.found tells us we have everything.
            meta = data.get("meta", {})
            found_raw = meta.get("found", None)

            # OpenAQ v3 sometimes returns found as ">1000" string
            if isinstance(found_raw, str) and found_raw.startswith(">"):
                found = None   # can't determine exact count
            else:
                try:
                    found = int(found_raw) if found_raw is not None else None
                except (TypeError, ValueError):
                    found = None

            if found is not None and found > 0:
                if len(all_records) >= found:
                    break
            else:
                # No reliable found count — stop if last page was short
                if len(results) < self._page_size:
                    break

            page += 1

        log.debug(
            f"[openaq] sensor_id={sensor_id} ({param_name}): "
            f"{len(all_records)} hourly records fetched."
        )
        return all_records
