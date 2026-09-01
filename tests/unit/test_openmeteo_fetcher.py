"""
tests/unit/test_openmeteo_fetcher.py
=====================================
Unit tests for OpenMeteoFetcher._normalise()

These tests mock the HTTP response so no real network call is made.
They verify that the normalisation logic correctly maps Open-Meteo
JSON output to the master schema.

Run with:
    pytest tests/unit/test_openmeteo_fetcher.py -v
"""

import math
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.schema.master_schema import COLUMN_NAMES


# ---------------------------------------------------------------------------
# Fixture: a realistic Open-Meteo API response for one station
# ---------------------------------------------------------------------------

SAMPLE_OPENMETEO_RESPONSE = {
    "_station_id":   "DEL_ITO",
    "_station_name": "ITO",
    "_latitude":     28.6289,
    "_longitude":    77.2412,
    "latitude":      28.625,
    "longitude":     77.25,
    "timezone":      "UTC",
    "hourly": {
        "time": [
            "2023-10-15T00:00",
            "2023-10-15T01:00",
            "2023-10-15T02:00",
        ],
        "temperature_2m":          [28.1, 27.5, 26.9],
        "relative_humidity_2m":    [65,   68,   71],
        "wind_speed_10m":          [2.3,  1.8,  1.2],
        "wind_direction_10m":      [315,  310,  320],
        "surface_pressure":        [995,  994,  994],
        "precipitation":           [0.0,  0.0,  0.1],
        "shortwave_radiation":     [0.0,  0.0,  0.0],
        "boundary_layer_height":   [180,  150,  140],
        "temperature_925hPa":      [26.3, 25.8, 25.1],
        "temperature_850hPa":      [22.1, 21.5, 20.9],
        "temperature_700hPa":      [14.5, 14.2, 13.8],
    }
}


class TestOpenMeteoFetcherNormalise:
    """
    Tests for the _normalise() method only.
    No network calls — we call _normalise() directly with sample data.
    """

    @pytest.fixture
    def fetcher(self):
        """Return an OpenMeteoFetcher instance with env vars mocked."""
        # No API key is needed for Open-Meteo, but the fetcher loads config
        # so we need the config files to be findable.
        from src.ingestion.openmeteo_fetcher import OpenMeteoFetcher
        return OpenMeteoFetcher()

    def test_normalise_produces_dataframe(self, fetcher):
        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE])
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_correct_row_count(self, fetcher):
        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE])
        assert len(df) == 3   # 3 hourly rows

    def test_station_id_populated(self, fetcher):
        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE])
        assert (df["station_id"] == "DEL_ITO").all()

    def test_temperature_column_populated(self, fetcher):
        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE])
        assert "temperature" in df.columns
        assert df["temperature"].iloc[0] == 28.1

    def test_pbl_height_column_populated(self, fetcher):
        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE])
        assert "pbl_height" in df.columns
        assert df["pbl_height"].iloc[0] == 180

    def test_pressure_level_temps_populated(self, fetcher):
        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE])
        assert "temp_925hpa" in df.columns
        assert "temp_850hpa" in df.columns
        assert "temp_700hpa" in df.columns
        assert df["temp_925hpa"].iloc[0] == 26.3
        assert df["temp_850hpa"].iloc[0] == 22.1
        assert df["temp_700hpa"].iloc[0] == 14.5

    def test_no_pollutant_columns_populated(self, fetcher):
        """Open-Meteo weather fetcher must NOT populate air quality columns."""
        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE])
        aq_cols = ["pm25", "pm10", "o3", "no2", "so2", "co"]
        for col in aq_cols:
            if col in df.columns:
                assert df[col].isna().all(), (
                    f"Column '{col}' should be all NaN for Open-Meteo weather data"
                )

    def test_data_source_set_correctly(self, fetcher):
        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE])
        assert (df["data_source"] == "openmeteo").all()

    def test_no_extra_columns_beyond_schema(self, fetcher):
        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE])
        extra = [c for c in df.columns if c not in COLUMN_NAMES]
        assert extra == [], f"Unexpected columns in output: {extra}"

    def test_empty_input_returns_empty_dataframe(self, fetcher):
        df = fetcher._normalise([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_multiple_stations_stacked_correctly(self, fetcher):
        station2 = dict(SAMPLE_OPENMETEO_RESPONSE)
        station2 = {k: v for k, v in station2.items()}
        station2["_station_id"] = "DEL_ROHINI"
        station2["_station_name"] = "Rohini"
        station2["_latitude"] = 28.7495
        station2["_longitude"] = 77.0748

        df = fetcher._normalise([SAMPLE_OPENMETEO_RESPONSE, station2])
        assert len(df) == 6   # 3 hours × 2 stations
        assert set(df["station_id"].unique()) == {"DEL_ITO", "DEL_ROHINI"}


class TestOpenMeteoFetcherHttpError:
    """Verify that HTTP errors are raised correctly (mocked)."""

    @patch("src.ingestion.openmeteo_fetcher.requests.get")
    def test_non_200_response_raises(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        from src.ingestion.openmeteo_fetcher import OpenMeteoFetcher
        fetcher = OpenMeteoFetcher()

        with pytest.raises(RuntimeError, match="HTTP 500"):
            fetcher._query_station(28.6289, 77.2412, "realtime")

    @patch("src.ingestion.openmeteo_fetcher.requests.get")
    def test_api_error_field_raises(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": True,
            "reason": "Parameter 'nonexistent' is not a valid hourly variable.",
        }
        mock_get.return_value = mock_response

        from src.ingestion.openmeteo_fetcher import OpenMeteoFetcher
        fetcher = OpenMeteoFetcher()

        with pytest.raises(RuntimeError, match="API error"):
            fetcher._query_station(28.6289, 77.2412, "realtime")
