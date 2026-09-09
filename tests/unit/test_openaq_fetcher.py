"""
tests/unit/test_openaq_fetcher.py
==================================
Unit tests for the rewritten OpenAQFetcher (v3 sensor-based API).

The correct OpenAQ v3 flow (as of 2024):
  Step 1  GET /v3/locations/{location_id}/sensors
  Step 2  GET /v3/sensors/{sensor_id}/hours?datetime_from=...&datetime_to=...

All HTTP calls are mocked — no real network access.

Test classes
------------
TestResolveDateRange          _resolve_date_range() for realtime / historical
TestGetJson                   _get_json() HTTP error handling
TestFetchSensors              _fetch_sensors() — location → sensor discovery
TestFetchSensorHours          _fetch_sensor_hours() — sensor → hourly data
TestNormalise                 _normalise() — multi-sensor pivot to wide rows
TestFetchRawIntegration       _fetch_raw() end-to-end with mocked HTTP layer
TestBaseFetcherContractChange BaseFetcher.run() now returns DataFrame, not None
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest
import requests

# ---------------------------------------------------------------------------
# Fixture — creates an OpenAQFetcher without touching the real API key
# ---------------------------------------------------------------------------

@pytest.fixture
def fetcher():
    with patch.dict("os.environ", {"OPENAQ_API_KEY": "TEST_KEY_FAKE"}):
        from src.ingestion.openaq_fetcher import OpenAQFetcher
        f = OpenAQFetcher()
        # Override location_map so tests don't depend on stations.yaml loading
        f._location_map = {
            8118: {
                "station_id": "DEL_ANAND_VIHAR",
                "name": "Anand Vihar",
                "latitude": 28.6469,
                "longitude": 77.3152,
            },
            8119: {
                "station_id": "DEL_ITO",
                "name": "ITO",
                "latitude": 28.6289,
                "longitude": 77.2412,
            },
        }
        return f


# ---------------------------------------------------------------------------
# Helpers for building realistic API mock responses
# ---------------------------------------------------------------------------

def _sensor_response(sensors: list[dict]) -> dict:
    return {"meta": {"name": "openaq-api", "found": len(sensors)}, "results": sensors}


def _hours_response(results: list[dict], found: int | None = None) -> dict:
    meta = {"name": "openaq-api", "page": 1, "limit": 1000}
    if found is not None:
        meta["found"] = found
    return {"meta": meta, "results": results}


def _sensor(sensor_id: int, param_name: str, units: str = "µg/m³") -> dict:
    return {
        "id": sensor_id,
        "name": f"{param_name} {units}",
        "parameter": {"id": 2, "name": param_name, "units": units, "displayName": param_name},
        "datetimeFirst": {"utc": "2023-01-01T00:00:00Z"},
        "datetimeLast": {"utc": "2024-12-13T14:30:00Z"},
    }


def _hour_result(
    ts_utc: str,
    value: float,
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    coords = {"latitude": lat, "longitude": lon} if lat else None
    return {
        "value": value,
        "period": {
            "datetimeFrom": {"utc": ts_utc, "local": ts_utc},
            "datetimeTo": {"utc": ts_utc, "local": ts_utc},
        },
        "coordinates": coords,
        "summary": None,
        "coverage": {"expectedCount": 1, "observedCount": 1, "percentComplete": 100.0},
    }


# ============================================================================
# 1. _resolve_date_range
# ============================================================================

class TestResolveDateRange:

    def test_realtime_returns_range_equal_to_lookback(self, fetcher):
        d_from, d_to = fetcher._resolve_date_range("realtime")
        diff_hours = (d_to - d_from).total_seconds() / 3600
        # Default lookback is 48 h
        assert 47.9 < diff_hours < 48.1

    def test_realtime_to_is_approximately_now(self, fetcher):
        _, d_to = fetcher._resolve_date_range("realtime")
        delta = abs((datetime.now(timezone.utc) - d_to).total_seconds())
        assert delta < 5  # within 5 seconds

    def test_historical_parses_start_and_end(self, fetcher):
        d_from, d_to = fetcher._resolve_date_range(
            "historical", start_date="2023-10-01", end_date="2023-10-31"
        )
        assert d_from.year == 2023 and d_from.month == 10 and d_from.day == 1
        assert d_to.year == 2023 and d_to.month == 10 and d_to.day == 31

    def test_historical_missing_dates_raises(self, fetcher):
        with pytest.raises(ValueError, match="start_date and end_date"):
            fetcher._resolve_date_range("historical")

    def test_unknown_mode_raises(self, fetcher):
        with pytest.raises(ValueError, match="Unknown mode"):
            fetcher._resolve_date_range("garbage")


# ============================================================================
# 2. _get_json — HTTP error handling
# ============================================================================

class TestGetJson:

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_401_raises_permission_error(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp
        with pytest.raises(PermissionError, match="401"):
            fetcher._get_json("https://api.openaq.org/v3/locations/8118/sensors")

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_429_raises_runtime_error(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp
        with pytest.raises(RuntimeError, match="429"):
            fetcher._get_json("https://api.openaq.org/v3/locations/8118/sensors")

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_404_raises_http_error(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=mock_resp
        )
        mock_get.return_value = mock_resp
        with pytest.raises(requests.HTTPError):
            fetcher._get_json("https://api.openaq.org/v3/locations/9999/sensors")

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_200_returns_parsed_json(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"meta": {}, "results": [{"id": 1}]}
        mock_get.return_value = mock_resp
        result = fetcher._get_json("https://api.openaq.org/v3/locations/8118/sensors")
        assert result["results"] == [{"id": 1}]

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_api_key_sent_in_header(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"meta": {}, "results": []}
        mock_get.return_value = mock_resp
        fetcher._get_json("https://api.openaq.org/v3/locations/8118/sensors")
        headers = mock_get.call_args[1]["headers"]
        assert headers["X-API-Key"] == "TEST_KEY_FAKE"


# ============================================================================
# 3. _fetch_sensors — Step 1 of the v3 flow
# ============================================================================

class TestFetchSensors:

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_returns_sensor_list(self, mock_get, fetcher):
        sensors = [_sensor(23534, "pm25"), _sensor(23535, "pm10")]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _sensor_response(sensors)
        mock_get.return_value = mock_resp

        result = fetcher._fetch_sensors(8118)
        assert len(result) == 2
        assert result[0]["id"] == 23534
        assert result[1]["id"] == 23535

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_404_returns_empty_list_not_raises(self, mock_get, fetcher):
        """A 404 on /locations/{id}/sensors means the location ID changed —
        should return [] and log a warning, not crash the pipeline."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        http_exc = requests.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_exc
        mock_get.return_value = mock_resp

        result = fetcher._fetch_sensors(9999)
        assert result == []

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_empty_results_returns_empty_list(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"meta": {}, "results": []}
        mock_get.return_value = mock_resp

        result = fetcher._fetch_sensors(8118)
        assert result == []

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_correct_url_called(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"meta": {}, "results": []}
        mock_get.return_value = mock_resp

        fetcher._fetch_sensors(8118)
        called_url = mock_get.call_args[0][0]
        assert called_url.endswith("/locations/8118/sensors")

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_non_404_http_error_propagates(self, mock_get, fetcher):
        """5xx errors should propagate so the pipeline records a real failure."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        http_exc = requests.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_exc
        mock_get.return_value = mock_resp

        with pytest.raises(requests.HTTPError):
            fetcher._fetch_sensors(8118)


# ============================================================================
# 4. _fetch_sensor_hours — Step 2 of the v3 flow
# ============================================================================

class TestFetchSensorHours:

    _NOW = datetime(2024, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    _FROM = _NOW - timedelta(hours=48)

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_returns_flat_records(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _hours_response([
            _hour_result("2024-09-01T10:00:00Z", 87.3),
            _hour_result("2024-09-01T11:00:00Z", 92.1),
        ], found=2)
        mock_get.return_value = mock_resp

        records = fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        assert len(records) == 2
        assert records[0]["pm25"] == 87.3
        assert records[1]["pm25"] == 92.1

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_station_id_mapped_to_canonical(self, mock_get, fetcher):
        """sensor data for location 8118 → station_id 'DEL_ANAND_VIHAR'"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _hours_response([
            _hour_result("2024-09-01T10:00:00Z", 87.3),
        ], found=1)
        mock_get.return_value = mock_resp

        records = fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        assert records[0]["station_id"] == "DEL_ANAND_VIHAR"

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_unknown_location_uses_fallback_id(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _hours_response([
            _hour_result("2024-09-01T10:00:00Z", 55.0),
        ], found=1)
        mock_get.return_value = mock_resp

        records = fetcher._fetch_sensor_hours(
            sensor_id=99999,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=9999,   # not in location_map
            station_meta=None,
        )

        assert records[0]["station_id"] == "OPENAQ_9999"

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_negative_value_set_to_nan(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _hours_response([
            _hour_result("2024-09-01T10:00:00Z", -5.0),
        ], found=1)
        mock_get.return_value = mock_resp

        records = fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        assert len(records) == 1
        assert math.isnan(records[0]["pm25"])

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_missing_timestamp_row_skipped(self, mock_get, fetcher):
        """A result with no period.datetimeFrom.utc must be silently dropped."""
        bad_result = {
            "value": 80.0,
            "period": {"datetimeFrom": {}, "datetimeTo": {}},
            "coordinates": None,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _hours_response([bad_result], found=1)
        mock_get.return_value = mock_resp

        records = fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        assert records == []

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_unknown_param_returns_empty(self, mock_get, fetcher):
        """Parameters not in _PARAM_MAP are ignored without an HTTP call."""
        records = fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="unknown_gas",  # not in _PARAM_MAP
            param_units="ppb",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        assert records == []
        mock_get.assert_not_called()

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_pagination_stops_when_found_exhausted(self, mock_get, fetcher):
        """When meta.found is reached, no further pages are requested."""
        page1 = _hours_response(
            [_hour_result(f"2024-09-01T{i:02d}:00:00Z", float(i)) for i in range(3)],
            found=3,
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = page1
        mock_get.return_value = mock_resp

        records = fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        assert len(records) == 3
        assert mock_get.call_count == 1  # only one page needed

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_pagination_stops_on_short_page(self, mock_get, fetcher):
        """Without meta.found, stop when last page has fewer rows than limit."""
        # 3 results < page_size (1000) → stop after page 1
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _hours_response(
            [_hour_result(f"2024-09-01T{i:02d}:00:00Z", 80.0) for i in range(3)],
            found=None,  # no found field
        )
        mock_get.return_value = mock_resp

        records = fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        assert mock_get.call_count == 1
        assert len(records) == 3

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_found_gt_string_handled_gracefully(self, mock_get, fetcher):
        """meta.found='>1000' (string) must not crash pagination logic."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Return a short page (< page_size) so loop exits
        mock_resp.json.return_value = {
            "meta": {"found": ">1000"},
            "results": [_hour_result("2024-09-01T10:00:00Z", 80.0)],
        }
        mock_get.return_value = mock_resp

        records = fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )
        # Short page (1 < 1000) → stop after page 1
        assert mock_get.call_count == 1
        assert len(records) == 1

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_404_on_sensor_returns_empty(self, mock_get, fetcher):
        """A 404 on /sensors/{id}/hours logs a warning and returns []."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=mock_resp
        )
        mock_get.return_value = mock_resp

        records = fetcher._fetch_sensor_hours(
            sensor_id=99999,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        assert records == []

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_correct_datetime_params_sent(self, mock_get, fetcher):
        """datetime_from and datetime_to must be in the query params."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _hours_response([], found=0)
        mock_get.return_value = mock_resp

        date_from = datetime(2024, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
        date_to   = datetime(2024, 9, 3, 0, 0, 0, tzinfo=timezone.utc)

        fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="pm25",
            param_units="µg/m³",
            date_from=date_from,
            date_to=date_to,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        params = mock_get.call_args[1]["params"]
        param_dict = dict(params)
        assert param_dict["datetime_from"] == "2024-09-01T00:00:00Z"
        assert param_dict["datetime_to"]   == "2024-09-03T00:00:00Z"

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_correct_url_called_for_sensor_hours(self, mock_get, fetcher):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _hours_response([], found=0)
        mock_get.return_value = mock_resp

        fetcher._fetch_sensor_hours(
            sensor_id=23534,
            param_name="pm25",
            param_units="µg/m³",
            date_from=self._FROM,
            date_to=self._NOW,
            location_id=8118,
            station_meta=fetcher._location_map[8118],
        )

        called_url = mock_get.call_args[0][0]
        assert called_url.endswith("/sensors/23534/hours")


# ============================================================================
# 5. _normalise — multi-sensor pivot to wide rows
# ============================================================================

class TestNormalise:

    def _make_records(self) -> list[dict]:
        """Two sensors (pm25, pm10) at the same station and hour."""
        return [
            {
                "timestamp_utc": "2024-09-01T10:00:00Z",
                "station_id": "DEL_ANAND_VIHAR",
                "station_name": "Anand Vihar",
                "latitude": 28.6469,
                "longitude": 77.3152,
                "data_source": "openaq",
                "pm25": 87.3,
            },
            {
                "timestamp_utc": "2024-09-01T10:00:00Z",
                "station_id": "DEL_ANAND_VIHAR",
                "station_name": "Anand Vihar",
                "latitude": 28.6469,
                "longitude": 77.3152,
                "data_source": "openaq",
                "pm10": 142.0,
            },
        ]

    def test_returns_dataframe(self, fetcher):
        df = fetcher._normalise(self._make_records())
        assert isinstance(df, pd.DataFrame)

    def test_two_sensors_same_hour_merged_to_one_row(self, fetcher):
        """pm25 and pm10 records for the same (timestamp, station) → 1 row."""
        df = fetcher._normalise(self._make_records())
        assert len(df) == 1

    def test_pm25_and_pm10_both_populated(self, fetcher):
        df = fetcher._normalise(self._make_records())
        assert df["pm25"].iloc[0] == pytest.approx(87.3)
        assert df["pm10"].iloc[0] == pytest.approx(142.0)

    def test_station_id_preserved(self, fetcher):
        df = fetcher._normalise(self._make_records())
        assert df["station_id"].iloc[0] == "DEL_ANAND_VIHAR"

    def test_data_source_is_openaq(self, fetcher):
        df = fetcher._normalise(self._make_records())
        assert (df["data_source"] == "openaq").all()

    def test_different_hours_produce_separate_rows(self, fetcher):
        records = [
            {"timestamp_utc": "2024-09-01T10:00:00Z", "station_id": "DEL_ITO",
             "station_name": "ITO", "latitude": 28.6, "longitude": 77.2,
             "data_source": "openaq", "pm25": 80.0},
            {"timestamp_utc": "2024-09-01T11:00:00Z", "station_id": "DEL_ITO",
             "station_name": "ITO", "latitude": 28.6, "longitude": 77.2,
             "data_source": "openaq", "pm25": 85.0},
        ]
        df = fetcher._normalise(records)
        assert len(df) == 2

    def test_different_stations_same_hour_separate_rows(self, fetcher):
        records = [
            {"timestamp_utc": "2024-09-01T10:00:00Z", "station_id": "DEL_ITO",
             "station_name": "ITO", "latitude": 28.6, "longitude": 77.2,
             "data_source": "openaq", "pm25": 80.0},
            {"timestamp_utc": "2024-09-01T10:00:00Z", "station_id": "DEL_ANAND_VIHAR",
             "station_name": "Anand Vihar", "latitude": 28.64, "longitude": 77.31,
             "data_source": "openaq", "pm25": 95.0},
        ]
        df = fetcher._normalise(records)
        assert len(df) == 2

    def test_empty_input_returns_empty_dataframe(self, fetcher):
        df = fetcher._normalise([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_records_missing_station_id_dropped(self, fetcher):
        records = [
            {"timestamp_utc": "2024-09-01T10:00:00Z",
             # no station_id
             "data_source": "openaq", "pm25": 80.0},
        ]
        df = fetcher._normalise(records)
        assert df.empty

    def test_records_missing_timestamp_dropped(self, fetcher):
        records = [
            {"station_id": "DEL_ITO",
             # no timestamp_utc
             "data_source": "openaq", "pm25": 80.0},
        ]
        df = fetcher._normalise(records)
        assert df.empty

    def test_first_value_wins_when_same_pollutant_appears_twice(self, fetcher):
        """If two records have the same (ts, station, pollutant), keep the first."""
        records = [
            {"timestamp_utc": "2024-09-01T10:00:00Z", "station_id": "DEL_ITO",
             "station_name": "ITO", "latitude": 28.6, "longitude": 77.2,
             "data_source": "openaq", "pm25": 80.0},
            {"timestamp_utc": "2024-09-01T10:00:00Z", "station_id": "DEL_ITO",
             "station_name": "ITO", "latitude": 28.6, "longitude": 77.2,
             "data_source": "openaq", "pm25": 999.0},  # should be ignored
        ]
        df = fetcher._normalise(records)
        assert len(df) == 1
        assert df["pm25"].iloc[0] == pytest.approx(80.0)


# ============================================================================
# 6. _fetch_raw end-to-end integration (mocked HTTP)
# ============================================================================

class TestFetchRawIntegration:
    """
    Verify that _fetch_raw correctly orchestrates:
      sensor discovery → hourly fetch → record accumulation
    No real HTTP calls.
    """

    def _setup_mock(self, mock_get, location_id: int, sensors: list[dict],
                    hours_by_sensor: dict) -> None:
        """
        Configure mock_get to return:
          - sensor list for  /locations/{location_id}/sensors
          - hourly data for  /sensors/{sensor_id}/hours
        """
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status.return_value = None
            if f"/locations/{location_id}/sensors" in url:
                resp.json.return_value = _sensor_response(sensors)
            else:
                for sid, results in hours_by_sensor.items():
                    if f"/sensors/{sid}/hours" in url:
                        resp.json.return_value = _hours_response(results, found=len(results))
                        break
                else:
                    resp.json.return_value = _hours_response([])
            return resp

        mock_get.side_effect = side_effect

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_returns_list_of_records(self, mock_get, fetcher):
        fetcher.config["location_ids"] = [8118]
        self._setup_mock(
            mock_get,
            location_id=8118,
            sensors=[_sensor(23534, "pm25")],
            hours_by_sensor={23534: [_hour_result("2024-09-01T10:00:00Z", 87.3)]},
        )
        records = fetcher._fetch_raw(mode="realtime")
        assert isinstance(records, list)
        assert len(records) == 1

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_multiple_sensors_at_one_location(self, mock_get, fetcher):
        fetcher.config["location_ids"] = [8118]
        self._setup_mock(
            mock_get,
            location_id=8118,
            sensors=[_sensor(23534, "pm25"), _sensor(23535, "pm10")],
            hours_by_sensor={
                23534: [_hour_result("2024-09-01T10:00:00Z", 87.3)],
                23535: [_hour_result("2024-09-01T10:00:00Z", 142.0)],
            },
        )
        records = fetcher._fetch_raw(mode="realtime")
        params = {r["station_id"]: r for r in records}
        # Both pm25 and pm10 records exist (they'll be merged in _normalise)
        assert any("pm25" in r for r in records)
        assert any("pm10" in r for r in records)

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_mode_is_not_passed_twice_to_resolve(self, mock_get, fetcher):
        """
        Regression: mode must be popped from kwargs before calling
        _resolve_date_range(mode, **kwargs) to avoid TypeError.
        """
        fetcher.config["location_ids"] = [8118]
        self._setup_mock(
            mock_get,
            location_id=8118,
            sensors=[_sensor(23534, "pm25")],
            hours_by_sensor={23534: []},
        )
        # This must not raise TypeError: got multiple values for argument 'mode'
        records = fetcher._fetch_raw(mode="realtime")
        assert isinstance(records, list)

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_404_location_skipped_gracefully(self, mock_get, fetcher):
        """A 404 on a location's sensors endpoint must not abort other locations."""
        fetcher.config["location_ids"] = [9999, 8118]

        def side_effect(url, **kwargs):
            resp = MagicMock()
            if "/locations/9999/sensors" in url:
                resp.status_code = 404
                resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
            elif "/locations/8118/sensors" in url:
                resp.status_code = 200
                resp.json.return_value = _sensor_response([_sensor(23534, "pm25")])
                resp.raise_for_status.return_value = None
            elif "/sensors/23534/hours" in url:
                resp.status_code = 200
                resp.json.return_value = _hours_response(
                    [_hour_result("2024-09-01T10:00:00Z", 87.3)], found=1
                )
                resp.raise_for_status.return_value = None
            else:
                resp.status_code = 200
                resp.json.return_value = _hours_response([])
                resp.raise_for_status.return_value = None
            return resp

        mock_get.side_effect = side_effect
        records = fetcher._fetch_raw(mode="realtime")
        # Location 8118 should still produce data
        assert any(r.get("station_id") == "DEL_ANAND_VIHAR" for r in records)

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_401_propagates_immediately(self, mock_get, fetcher):
        """Auth errors must stop all processing immediately."""
        fetcher.config["location_ids"] = [8118]
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        with pytest.raises(PermissionError, match="401"):
            fetcher._fetch_raw(mode="realtime")

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_returns_empty_list_when_no_sensors(self, mock_get, fetcher):
        """Location with no sensors → empty record list (not an error)."""
        fetcher.config["location_ids"] = [8118]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _sensor_response([])  # no sensors
        mock_get.return_value = mock_resp

        records = fetcher._fetch_raw(mode="realtime")
        assert records == []

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_sensors_with_irrelevant_params_skipped(self, mock_get, fetcher):
        """Sensors for parameters not in _PARAM_MAP are ignored."""
        fetcher.config["location_ids"] = [8118]
        irrelevant_sensor = _sensor(99001, "temperature")  # not in _PARAM_MAP

        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status.return_value = None
            if "/locations/8118/sensors" in url:
                resp.json.return_value = _sensor_response([irrelevant_sensor])
            else:
                resp.json.return_value = _hours_response([])
            return resp

        mock_get.side_effect = side_effect
        records = fetcher._fetch_raw(mode="realtime")
        # Temperature sensor should be skipped — no hours request made
        urls_called = [str(c[0][0]) for c in mock_get.call_args_list]
        assert not any("/sensors/99001/hours" in u for u in urls_called)
        assert records == []


# ============================================================================
# 7. BaseFetcher contract: run() always returns DataFrame, never None
# ============================================================================

class TestBaseFetcherContractChange:
    """
    Verifies that BaseFetcher.run() now always returns a pd.DataFrame
    (possibly empty) and never None — fixing the AttributeError: 'NoneType'
    has no attribute 'head' bug.
    """

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_run_returns_dataframe_on_empty_api_response(self, mock_get, fetcher):
        """If the API returns sensors but zero hours → empty df, not None."""
        fetcher.config["location_ids"] = [8118]

        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status.return_value = None
            if "/locations/8118/sensors" in url:
                resp.json.return_value = _sensor_response([_sensor(23534, "pm25")])
            else:
                resp.json.return_value = _hours_response([], found=0)
            return resp

        mock_get.side_effect = side_effect

        result = fetcher.run(mode="realtime")

        assert result is not None, "run() must never return None"
        assert isinstance(result, pd.DataFrame), (
            f"Expected pd.DataFrame, got {type(result)}"
        )

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_run_empty_df_safe_to_call_head_on(self, mock_get, fetcher):
        """Callers that call df.head() must not get AttributeError."""
        fetcher.config["location_ids"] = [8118]

        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status.return_value = None
            resp.json.return_value = (
                _sensor_response([_sensor(23534, "pm25")])
                if "/sensors" not in url
                else _hours_response([], found=0)
            )
            return resp

        mock_get.side_effect = side_effect

        result = fetcher.run(mode="realtime")
        # This must not raise AttributeError
        head = result.head()
        assert isinstance(head, pd.DataFrame)

    @patch("src.ingestion.openaq_fetcher.requests.get")
    def test_run_returns_nonempty_df_when_data_available(self, mock_get, fetcher):
        """When data is returned by the API, run() returns a non-empty DataFrame."""
        fetcher.config["location_ids"] = [8118]

        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status.return_value = None
            if "/locations/8118/sensors" in url:
                resp.json.return_value = _sensor_response([_sensor(23534, "pm25")])
            else:
                resp.json.return_value = _hours_response(
                    [_hour_result("2024-09-01T10:00:00Z", 87.3)], found=1
                )
            return resp

        mock_get.side_effect = side_effect

        result = fetcher.run(mode="realtime")
        assert not result.empty
        assert "pm25" in result.columns

    @patch.object(
        __import__("src.ingestion.openaq_fetcher", fromlist=["OpenAQFetcher"]).OpenAQFetcher,
        "_fetch_raw",
        side_effect=RuntimeError("Simulated network failure"),
    )
    def test_run_propagates_fetch_exception(self, mock_fetch_raw, fetcher):
        """
        When _fetch_raw raises (e.g. network error), BaseFetcher.run()
        should re-raise after exhausting retries so the pipeline records
        the real error message.
        """
        # Override retry config so the test doesn't wait 35 s of backoff
        fetcher.config["retry_attempts"] = 1
        fetcher.config["retry_backoff_sec"] = 0

        with pytest.raises(RuntimeError, match="Simulated network failure"):
            fetcher.run(mode="realtime")
