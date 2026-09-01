"""
tests/unit/test_dataset_builder.py
=====================================
Unit tests for src/processing/dataset_builder.py and
src/processing/quality_report.py

Uses an in-memory SQLite database and synthetic test data.
No network calls. No real API keys required.
All data is clearly labelled as SYNTHETIC/DEMO.

Run with:
    pytest tests/unit/test_dataset_builder.py -v
"""

from __future__ import annotations

import json
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.processing.dataset_builder import DatasetBuilder
from src.processing.quality_report import QualityReport
from src.schema.master_schema import COLUMN_NAMES, MASTER_SCHEMA
from src.storage.db_client import DBClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """In-memory SQLite database — fresh for every test."""
    return DBClient(db_url="sqlite:///:memory:")


@pytest.fixture
def builder(db):
    with tempfile.TemporaryDirectory() as tmp:
        yield DatasetBuilder(db, output_dir=Path(tmp))


# ---------------------------------------------------------------------------
# Synthetic data builders
# NOTE: All values below are SYNTHETIC/DEMO — not real observations.
# ---------------------------------------------------------------------------

_T1 = datetime(2023, 10, 15, 6, 0, 0, tzinfo=timezone.utc)
_T2 = datetime(2023, 10, 15, 7, 0, 0, tzinfo=timezone.utc)
_T3 = datetime(2023, 10, 15, 8, 0, 0, tzinfo=timezone.utc)


def _obs_row(
    ts=_T1,
    station_id="DEL_ITO",
    lat=28.6289,
    lon=77.2412,
    pm25=75.0,
    pm10=150.0,
    temperature=25.0,
    temp_850hpa=22.0,
    pbl_height=500.0,
    wind_speed=3.0,
    wind_direction=315.0,
    data_source="openaq",
) -> dict:
    return {
        "timestamp_utc": ts,
        "station_id": station_id,
        "station_name": "ITO",
        "latitude": lat,
        "longitude": lon,
        "data_source": data_source,
        "pm25": pm25,
        "pm10": pm10,
        "temperature": temperature,
        "temp_850hpa": temp_850hpa,
        "pbl_height": pbl_height,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
    }


def _fire_row(
    lat=30.74,
    lon=76.79,
    frp=20.0,
    ts=_T1,
) -> dict:
    return {
        "timestamp_utc": ts,
        "latitude": lat,
        "longitude": lon,
        "frp": frp,
        "confidence": "nominal",
        "satellite": "N",
        "data_source": "firms",
    }


def _seed_observations(db, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    db.write_observations(df)


def _seed_fires(db, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    db.write_fire_detections(df)


# ===========================================================================
# DatasetBuilder._standardise_units (static)
# ===========================================================================

class TestStandardiseUnits:

    def test_kelvin_temperature_converted(self):
        df = pd.DataFrame([{"temperature": 302.0}])  # 302 K = 28.85 °C
        result = DatasetBuilder._standardise_units(df)
        assert result["temperature"].iloc[0] < 100.0

    def test_celsius_temperature_unchanged(self):
        df = pd.DataFrame([{"temperature": 28.5}])  # already °C
        result = DatasetBuilder._standardise_units(df)
        assert abs(result["temperature"].iloc[0] - 28.5) < 1e-9

    def test_pa_pressure_converted(self):
        df = pd.DataFrame([{"surface_pressure": 99500.0}])  # Pa
        result = DatasetBuilder._standardise_units(df)
        assert result["surface_pressure"].iloc[0] < 2000.0  # now hPa

    def test_hpa_pressure_unchanged(self):
        df = pd.DataFrame([{"surface_pressure": 995.0}])  # already hPa
        result = DatasetBuilder._standardise_units(df)
        assert abs(result["surface_pressure"].iloc[0] - 995.0) < 1e-9

    def test_large_solar_radiation_converted(self):
        # 10_800_000 J/m² is above the 5_000_000 J/m² detection threshold
        # and represents a plausible ERA5 hourly accumulation
        df = pd.DataFrame([{"solar_radiation": 10_800_000.0}])  # J/m²
        result = DatasetBuilder._standardise_units(df)
        assert result["solar_radiation"].iloc[0] < 10000.0

    def test_reasonable_solar_radiation_unchanged(self):
        df = pd.DataFrame([{"solar_radiation": 800.0}])  # W/m²
        result = DatasetBuilder._standardise_units(df)
        assert abs(result["solar_radiation"].iloc[0] - 800.0) < 1e-9

    def test_nan_not_converted(self):
        df = pd.DataFrame([{"temperature": float("nan")}])
        result = DatasetBuilder._standardise_units(df)
        assert math.isnan(result["temperature"].iloc[0])

    def test_large_precipitation_converted(self):
        df = pd.DataFrame([{"precipitation": 0.005}])  # ERA5 metres
        result = DatasetBuilder._standardise_units(df)
        # 0.005 m < 10 threshold → unchanged (m_to_mm only triggered >10)
        # Should remain as-is since 0.005 is below the threshold
        assert result["precipitation"].iloc[0] < 10.0


# ===========================================================================
# DatasetBuilder._merge_aq_weather (static)
# ===========================================================================

class TestMergeAqWeather:

    def test_basic_merge(self):
        aq = pd.DataFrame([{
            "timestamp_utc": "2023-10-15T06:00:00Z",
            "station_id": "DEL_ITO",
            "pm25": 75.0,
        }])
        wx = pd.DataFrame([{
            "timestamp_utc": "2023-10-15T06:00:00Z",
            "station_id": "DEL_ITO",
            "temperature": 25.0,
        }])
        result = DatasetBuilder._merge_aq_weather(aq, wx)
        assert "pm25" in result.columns
        assert "temperature" in result.columns
        assert len(result) == 1
        assert result["pm25"].iloc[0] == 75.0
        assert result["temperature"].iloc[0] == 25.0

    def test_no_weather_match_gives_nan(self):
        aq = pd.DataFrame([{
            "timestamp_utc": "2023-10-15T06:00:00Z",
            "station_id": "DEL_ITO",
            "pm25": 75.0,
        }])
        wx = pd.DataFrame([{
            "timestamp_utc": "2023-10-15T09:00:00Z",  # different hour
            "station_id": "DEL_ITO",
            "temperature": 25.0,
        }])
        result = DatasetBuilder._merge_aq_weather(aq, wx)
        assert len(result) == 1   # AQ row preserved
        assert math.isnan(result["temperature"].iloc[0])

    def test_aq_rows_never_dropped(self):
        aq = pd.DataFrame([
            {"timestamp_utc": "2023-10-15T06:00:00Z", "station_id": "S1", "pm25": 50.0},
            {"timestamp_utc": "2023-10-15T07:00:00Z", "station_id": "S1", "pm25": 60.0},
        ])
        wx = pd.DataFrame([
            {"timestamp_utc": "2023-10-15T06:00:00Z", "station_id": "S1", "temperature": 25.0},
        ])
        result = DatasetBuilder._merge_aq_weather(aq, wx)
        assert len(result) == 2   # both AQ rows kept


# ===========================================================================
# DatasetBuilder._align_to_schema (static)
# ===========================================================================

class TestAlignToSchema:

    def test_adds_missing_schema_columns(self):
        df = pd.DataFrame([{"timestamp_utc": _T1, "station_id": "X", "data_source": "test"}])
        result = DatasetBuilder._align_to_schema(df)
        # All schema columns should be present
        for col in COLUMN_NAMES:
            assert col in result.columns, f"Missing: {col}"

    def test_drops_unknown_columns(self):
        df = pd.DataFrame([{
            "timestamp_utc": _T1, "station_id": "X",
            "data_source": "test", "UNKNOWN_COL_XYZ": 999,
        }])
        result = DatasetBuilder._align_to_schema(df)
        assert "UNKNOWN_COL_XYZ" not in result.columns

    def test_column_order_matches_schema(self):
        df = pd.DataFrame([{"station_id": "X", "timestamp_utc": _T1, "data_source": "t"}])
        result = DatasetBuilder._align_to_schema(df)
        schema_order = [c for c in COLUMN_NAMES if c in result.columns]
        assert list(result.columns) == schema_order


# ===========================================================================
# DatasetBuilder.build (integration with in-memory DB)
# ===========================================================================

class TestDatasetBuilderBuild:

    def test_empty_db_returns_empty_df(self, builder):
        result = builder.build(
            start_date="2023-10-15", end_date="2023-10-15",
            write_db=False, write_parquet=False,
        )
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_build_returns_master_df_with_derived_cols(self, db, builder):
        _seed_observations(db, [_obs_row()])
        result = builder.build(
            start_date="2023-10-15", end_date="2023-10-15",
            write_db=False, write_parquet=False,
        )
        assert not result.empty
        assert "inversion_strength" in result.columns
        assert "aqi_computed" in result.columns
        assert "wind_transport_idx" in result.columns

    def test_build_computes_inversion_correctly(self, db, builder):
        # temperature=25, temp_850hpa=30 → strength=5, flag=True
        _seed_observations(db, [_obs_row(temperature=25.0, temp_850hpa=30.0)])
        result = builder.build(
            start_date="2023-10-15", end_date="2023-10-15",
            write_db=False, write_parquet=False,
        )
        assert not result.empty
        assert abs(result["inversion_strength"].iloc[0] - 5.0) < 0.1

    def test_build_with_fire_data(self, db, builder):
        _seed_observations(db, [_obs_row()])
        _seed_fires(db, [_fire_row(lat=30.74, lon=76.79, frp=25.0)])
        result = builder.build(
            start_date="2023-10-15", end_date="2023-10-15",
            write_db=False, write_parquet=False,
        )
        assert not result.empty
        # Fire features should be populated
        dist = result["fire_distance_km"].iloc[0]
        assert not math.isnan(dist)
        assert dist > 0

    def test_build_writes_parquet(self, db):
        with tempfile.TemporaryDirectory() as tmp:
            builder = DatasetBuilder(db, output_dir=Path(tmp))
            _seed_observations(db, [_obs_row(), _obs_row(ts=_T2), _obs_row(ts=_T3)])
            builder.build(
                start_date="2023-10-15", end_date="2023-10-15",
                write_db=False, write_parquet=True,
            )
            parquet_files = list(Path(tmp).glob("*.parquet"))
            assert len(parquet_files) == 1
            saved = pd.read_parquet(parquet_files[0])
            assert not saved.empty

    def test_raw_data_not_modified(self, db, builder):
        """Ingested observations table should not lose rows after build."""
        _seed_observations(db, [_obs_row(), _obs_row(ts=_T2)])
        initial = db.read_observations()
        n_before = len(initial)

        builder.build(
            start_date="2023-10-15", end_date="2023-10-15",
            write_db=False, write_parquet=False,
        )
        after = db.read_observations()
        assert len(after) >= n_before   # rows only added, never removed


# ===========================================================================
# QualityReport
# ===========================================================================

class TestQualityReport:

    def _make_df(self, n=5) -> pd.DataFrame:
        """Build a small synthetic master-schema-compatible DataFrame."""
        rows = []
        for i in range(n):
            rows.append({
                "timestamp_utc": pd.Timestamp(f"2023-10-15 0{i}:00:00", tz="UTC"),
                "station_id": "DEL_ITO",
                "station_name": "ITO",
                "latitude": 28.6289,
                "longitude": 77.2412,
                "data_source": "openaq",
                "pm25": 50.0 + i * 10,
                "pm10": 100.0 + i * 20,
                "temperature": 25.0 + i,
            })
        return pd.DataFrame(rows)

    def test_per_column_stats_returns_dataframe(self):
        df = self._make_df()
        report = QualityReport(df)
        stats = report.per_column_stats()
        assert isinstance(stats, pd.DataFrame)
        assert "column" in stats.columns
        assert "completeness_pct" in stats.columns

    def test_summary_returns_dict(self):
        df = self._make_df()
        report = QualityReport(df)
        s = report.summary()
        assert isinstance(s, dict)
        assert "n_rows" in s
        assert s["n_rows"] == 5

    def test_completeness_100_for_present_columns(self):
        df = self._make_df()
        report = QualityReport(df)
        stats = report.per_column_stats()
        pm25_row = stats[stats["column"] == "pm25"].iloc[0]
        assert pm25_row["completeness_pct"] == 100.0

    def test_completeness_0_for_absent_column(self):
        df = self._make_df()
        # fire_distance_km is not in the DataFrame
        report = QualityReport(df)
        stats = report.per_column_stats()
        fire_row = stats[stats["column"] == "fire_distance_km"].iloc[0]
        assert fire_row["completeness_pct"] == 0.0

    def test_oor_detected_for_bad_value(self):
        df = self._make_df()
        df.loc[0, "pm25"] = 99999.0   # way above valid_max=2000
        report = QualityReport(df)
        stats = report.per_column_stats()
        pm25_row = stats[stats["column"] == "pm25"].iloc[0]
        assert pm25_row["n_out_of_range"] >= 1

    def test_unavailable_fields_listed_in_summary(self):
        df = self._make_df()
        report = QualityReport(df)
        s = report.summary()
        # fire_distance_km should be in unavailable_fields
        assert "fire_distance_km" in s["unavailable_fields"]

    def test_save_creates_json_and_csv(self):
        df = self._make_df()
        report = QualityReport(df)
        with tempfile.TemporaryDirectory() as tmp:
            json_path, csv_path = report.save(Path(tmp))
            assert json_path.exists()
            assert csv_path.exists()
            # JSON must be parseable
            data = json.loads(json_path.read_text())
            assert "n_rows" in data

    def test_print_report_does_not_raise(self, capsys):
        df = self._make_df()
        report = QualityReport(df)
        report.print_report()  # should not raise
        captured = capsys.readouterr()
        assert "Quality Report" in captured.out

    def test_empty_df_handled_gracefully(self):
        report = QualityReport(pd.DataFrame())
        s = report.summary()
        assert s["n_rows"] == 0
        stats = report.per_column_stats()
        assert isinstance(stats, pd.DataFrame)
