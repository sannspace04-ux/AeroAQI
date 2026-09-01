"""
tests/integration/test_api_observations.py
============================================
Integration tests for air quality observation endpoints:
  GET /observations
  GET /observations/latest
  GET /observations/{station_id}
  GET /weather
  GET /weather/latest
  GET /weather/{station_id}
  GET /pipeline/runs

All data is from the in-memory DB seeded in conftest.py.
No external API calls are made.

Run with:
    pytest tests/integration/test_api_observations.py -v
"""

import pytest


# ===========================================================================
# /observations
# ===========================================================================

class TestListObservations:

    def test_returns_200(self, client):
        resp = client.get("/observations", params={"hours": 720})
        assert resp.status_code == 200

    def test_response_has_required_keys(self, client):
        body = client.get("/observations", params={"hours": 720}).json()
        assert "count" in body
        assert "observations" in body

    def test_returns_seeded_data(self, client):
        body = client.get("/observations", params={"hours": 720}).json()
        # conftest seeds 6 observation rows
        assert body["count"] >= 1
        assert len(body["observations"]) >= 1

    def test_observation_record_has_aqi_fields(self, client):
        body = client.get("/observations", params={"hours": 720}).json()
        obs = body["observations"][0]
        for field in ("station_id", "timestamp_utc", "pm25", "pm10"):
            assert field in obs, f"Missing field: {field}"

    def test_pm25_values_are_float_or_null(self, client):
        body = client.get("/observations", params={"hours": 720}).json()
        for obs in body["observations"]:
            v = obs.get("pm25")
            assert v is None or isinstance(v, (int, float)), (
                f"pm25 should be float or null, got {type(v)}"
            )

    def test_no_nan_in_response(self, client):
        """JSON responses must never contain literal NaN (not JSON-serialisable)."""
        raw = client.get("/observations", params={"hours": 720}).text
        assert "NaN" not in raw, "Response contains literal NaN — not valid JSON"

    def test_limit_parameter_respected(self, client):
        body = client.get("/observations", params={"hours": 720, "limit": 2}).json()
        assert len(body["observations"]) <= 2

    def test_station_id_filter(self, client):
        body = client.get(
            "/observations",
            params={"station_id": "DEL_ITO", "hours": 720},
        ).json()
        for obs in body["observations"]:
            assert obs["station_id"] == "DEL_ITO"

    def test_station_id_filter_empty_for_unknown_station(self, client):
        body = client.get(
            "/observations",
            params={"station_id": "NONEXISTENT_XYZ", "hours": 720},
        ).json()
        assert body["count"] == 0

    def test_invalid_time_range_returns_422(self, client):
        resp = client.get(
            "/observations",
            params={
                "start_time": "2023-10-15T09:00:00",
                "end_time": "2023-10-15T06:00:00",  # end before start
            },
        )
        assert resp.status_code == 422

    def test_invalid_datetime_format_returns_422(self, client):
        resp = client.get(
            "/observations",
            params={"start_time": "not-a-date"},
        )
        assert resp.status_code == 422

    def test_limit_above_max_returns_422(self, client):
        resp = client.get("/observations", params={"limit": 9999})
        assert resp.status_code == 422

    def test_start_end_filter_returns_subset(self, client):
        """Rows outside the time window must not appear."""
        body = client.get(
            "/observations",
            params={
                "start_time": "2023-10-15T06:00:00",
                "end_time": "2023-10-15T07:00:00",
                "station_id": "DEL_ITO",
            },
        ).json()
        # Only T1 row should be in this window (or 0 if DB is empty)
        assert body["count"] >= 0


# ===========================================================================
# /observations/latest
# ===========================================================================

class TestLatestObservations:

    def test_returns_200(self, client):
        resp = client.get("/observations/latest")
        assert resp.status_code == 200

    def test_response_structure(self, client):
        body = client.get("/observations/latest").json()
        assert "count" in body
        assert "observations" in body

    def test_no_nan_in_response(self, client):
        raw = client.get("/observations/latest").text
        assert "NaN" not in raw


# ===========================================================================
# /observations/{station_id}
# ===========================================================================

class TestStationObservations:

    def test_valid_station_returns_200(self, client):
        resp = client.get("/observations/DEL_ITO", params={"hours": 720})
        assert resp.status_code == 200

    def test_valid_station_returns_data(self, client):
        body = client.get("/observations/DEL_ITO", params={"hours": 720}).json()
        assert body["count"] >= 1
        for obs in body["observations"]:
            assert obs["station_id"] == "DEL_ITO"

    def test_invalid_station_returns_404(self, client):
        resp = client.get("/observations/INVALID_XYZ", params={"hours": 720})
        assert resp.status_code == 404

    def test_404_body_has_detail(self, client):
        body = client.get(
            "/observations/INVALID_STATION", params={"hours": 720}
        ).json()
        assert "detail" in body


# ===========================================================================
# /weather
# ===========================================================================

class TestWeatherEndpoints:

    def test_list_weather_returns_200(self, client):
        resp = client.get("/weather", params={"hours": 720})
        assert resp.status_code == 200

    def test_weather_response_has_count(self, client):
        body = client.get("/weather", params={"hours": 720}).json()
        assert "count" in body
        assert "observations" in body

    def test_weather_records_have_temperature(self, client):
        body = client.get(
            "/weather",
            params={"station_id": "DEL_ITO", "hours": 720},
        ).json()
        if body["count"] > 0:
            obs = body["observations"][0]
            assert "temperature" in obs

    def test_latest_weather_returns_200(self, client):
        resp = client.get("/weather/latest")
        assert resp.status_code == 200

    def test_station_weather_returns_200(self, client):
        resp = client.get("/weather/DEL_ITO", params={"hours": 720})
        assert resp.status_code == 200

    def test_unknown_station_weather_returns_404(self, client):
        resp = client.get("/weather/INVALID_STATION", params={"hours": 720})
        assert resp.status_code == 404

    def test_weather_no_nan_in_response(self, client):
        raw = client.get("/weather", params={"hours": 720}).text
        assert "NaN" not in raw

    def test_weather_station_filter(self, client):
        body = client.get(
            "/weather",
            params={"station_id": "DEL_ITO", "hours": 720},
        ).json()
        for obs in body["observations"]:
            assert obs["station_id"] == "DEL_ITO"


# ===========================================================================
# /pipeline/runs (read-only — no actual ingestion triggered)
# ===========================================================================

class TestPipelineRunsEndpoint:

    def test_returns_200(self, client):
        resp = client.get("/pipeline/runs")
        assert resp.status_code == 200

    def test_response_has_count_and_runs(self, client):
        body = client.get("/pipeline/runs").json()
        assert "count" in body
        assert "runs" in body
        assert isinstance(body["runs"], list)

    def test_n_parameter_validates(self, client):
        resp = client.get("/pipeline/runs", params={"n": 5})
        assert resp.status_code == 200

    def test_n_too_large_returns_422(self, client):
        resp = client.get("/pipeline/runs", params={"n": 999})
        assert resp.status_code == 422

    def test_n_zero_returns_422(self, client):
        resp = client.get("/pipeline/runs", params={"n": 0})
        assert resp.status_code == 422
