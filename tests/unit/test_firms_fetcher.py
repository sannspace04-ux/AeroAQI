"""
tests/unit/test_firms_fetcher.py
=================================
Unit tests for FIRMSFetcher._normalise() and confidence filtering.

No network calls — we call _normalise() directly with sample CSV strings.

Run with:
    pytest tests/unit/test_firms_fetcher.py -v
"""

import math
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Sample FIRMS VIIRS CSV (as returned by the real API)
# ---------------------------------------------------------------------------

SAMPLE_FIRMS_CSV = """\
latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
30.1234,75.5678,320.5,0.42,0.38,2023-10-15,0130,N,VIIRS,nominal,2.0NRT,290.1,15.2,D
30.5678,75.1234,335.2,0.39,0.35,2023-10-15,0130,N,VIIRS,high,2.0NRT,295.3,22.7,D
29.8765,74.9876,310.1,0.44,0.40,2023-10-15,0730,N,VIIRS,low,2.0NRT,285.6,8.1,N
31.1111,76.2222,325.8,0.41,0.37,2023-10-15,1300,N,VIIRS,nominal,2.0NRT,292.4,18.5,D
"""

SAMPLE_FIRMS_CSV_NEGATIVE_FRP = """\
latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
30.1234,75.5678,320.5,0.42,0.38,2023-10-15,0130,N,VIIRS,nominal,2.0NRT,290.1,-5.0,D
"""

SAMPLE_FIRMS_CSV_BAD_TIMESTAMPS = """\
latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
30.1234,75.5678,320.5,0.42,0.38,bad_date,9999,N,VIIRS,nominal,2.0NRT,290.1,15.2,D
30.5678,75.1234,335.2,0.39,0.35,2023-10-15,0130,N,VIIRS,high,2.0NRT,295.3,22.7,D
"""


class TestFIRMSFetcherNormalise:

    @pytest.fixture
    def fetcher(self):
        """Create a FIRMSFetcher with the FIRMS_MAP_KEY mocked."""
        with patch.dict("os.environ", {"FIRMS_MAP_KEY": "FAKE_TEST_KEY"}):
            from src.ingestion.firms_fetcher import FIRMSFetcher
            return FIRMSFetcher()

    def test_normalise_returns_dataframe(self, fetcher):
        df = fetcher._normalise(SAMPLE_FIRMS_CSV)
        assert isinstance(df, pd.DataFrame)

    def test_low_confidence_rows_filtered_out(self, fetcher):
        """Default min_confidence is 'nominal' — low confidence should be excluded."""
        df = fetcher._normalise(SAMPLE_FIRMS_CSV)
        if "confidence" in df.columns:
            assert "low" not in df["confidence"].str.lower().tolist()

    def test_nominal_and_high_confidence_kept(self, fetcher):
        df = fetcher._normalise(SAMPLE_FIRMS_CSV)
        if "confidence" in df.columns:
            allowed = {"nominal", "high"}
            for val in df["confidence"].str.lower():
                assert val in allowed, f"Unexpected confidence value: {val}"

    def test_correct_row_count_after_filter(self, fetcher):
        # 4 rows in CSV: nominal, high, low, nominal
        # low filtered → 3 rows remain
        df = fetcher._normalise(SAMPLE_FIRMS_CSV)
        assert len(df) == 3

    def test_timestamp_built_from_acq_date_and_time(self, fetcher):
        df = fetcher._normalise(SAMPLE_FIRMS_CSV)
        assert "timestamp_utc" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp_utc"])
        # First row: 2023-10-15 01:30 UTC
        ts = df["timestamp_utc"].iloc[0]
        assert ts.year == 2023
        assert ts.month == 10
        assert ts.day == 15
        assert ts.hour == 1
        assert ts.minute == 30

    def test_negative_frp_becomes_nan_not_zero(self, fetcher):
        df = fetcher._normalise(SAMPLE_FIRMS_CSV_NEGATIVE_FRP)
        if len(df) > 0 and "frp" in df.columns:
            assert math.isnan(df["frp"].iloc[0])
            assert df["frp"].iloc[0] != 0.0

    def test_rows_with_bad_timestamps_dropped(self, fetcher):
        df = fetcher._normalise(SAMPLE_FIRMS_CSV_BAD_TIMESTAMPS)
        # Only the second row (valid timestamp) should remain
        assert len(df) == 1

    def test_empty_csv_returns_empty_dataframe(self, fetcher):
        df = fetcher._normalise("")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_data_source_set_to_firms(self, fetcher):
        df = fetcher._normalise(SAMPLE_FIRMS_CSV)
        if not df.empty:
            assert (df["data_source"] == "firms").all()

    def test_latitude_longitude_numeric(self, fetcher):
        df = fetcher._normalise(SAMPLE_FIRMS_CSV)
        assert pd.api.types.is_float_dtype(df["latitude"])
        assert pd.api.types.is_float_dtype(df["longitude"])

    def test_html_response_raises_value_error(self, fetcher):
        html_response = "<!DOCTYPE html><html><body>Error 401</body></html>"
        with pytest.raises(ValueError, match="HTML"):
            fetcher._normalise(html_response)


class TestFIRMSFetcherHTTPErrors:

    @patch("src.ingestion.firms_fetcher.requests.get")
    def test_401_raises_permission_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"FIRMS_MAP_KEY": "FAKE_KEY"}):
            from src.ingestion.firms_fetcher import FIRMSFetcher
            fetcher = FIRMSFetcher()

        with pytest.raises(PermissionError, match="401"):
            fetcher._fetch_raw(mode="realtime")

    @patch("src.ingestion.firms_fetcher.requests.get")
    def test_400_raises_value_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"FIRMS_MAP_KEY": "FAKE_KEY"}):
            from src.ingestion.firms_fetcher import FIRMSFetcher
            fetcher = FIRMSFetcher()

        with pytest.raises(ValueError, match="400"):
            fetcher._fetch_raw(mode="realtime")
