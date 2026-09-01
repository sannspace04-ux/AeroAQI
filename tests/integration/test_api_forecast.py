"""
tests/integration/test_api_forecast.py
=========================================
Integration tests for the Phase 6 forecast endpoints:
  GET /forecast/{station_id}
  GET /forecast/{station_id}/explain

Strategy
--------
- Uses the same StaticPool in-memory DB fixture from conftest.py.
- Two test scenarios:
    1. No forecasts in DB → API returns empty response with model_trained=False.
    2. Seeded forecasts in DB → API returns the forecast rows correctly.
- No trained model or API keys are required.
- No real ML inference happens; forecast rows are seeded directly into the DB.

All seeded data is SYNTHETIC/DEMO — not real observations.

Run with:
    pytest tests/integration/test_api_forecast.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db
from src.api.main import create_app
from src.storage.db_client import DBClient, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# ---------------------------------------------------------------------------
# Fixtures — separate DB seeded with forecast rows
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _make_forecast_rows(
    station_id: str = "DEL_ITO",
    generated_at=None,
    n_hours: int = 72,
) -> list[dict]:
    """Build synthetic forecast rows for testing."""
    if generated_at is None:
        generated_at = _NOW - timedelta(minutes=5)
    rows = []
    for h in range(1, n_hours + 1):
        rows.append({
            "generated_at": generated_at,
            "station_id": station_id,
            "forecast_hour": h,
            "target_utc": generated_at + timedelta(hours=h),
            "pm25": 80.0 + h * 0.5,
            "pm10": 120.0 + h * 0.3,
            "o3": 45.0,
            "no2": 35.0,
            "aqi_computed": 100.0 + h * 0.2,
            "aqi_category": "Moderate" if h <= 24 else "Poor",
            "top_features": json.dumps([
                {"rank": 1, "name": "pbl_height", "label": "Boundary layer height",
                 "shap_value": 12.5, "contribution_pct": 38.0},
                {"rank": 2, "name": "wind_transport_idx", "label": "NW wind transport",
                 "shap_value": 8.3, "contribution_pct": 25.0},
                {"rank": 3, "name": "is_stubble_season", "label": "Stubble season",
                 "shap_value": 5.1, "contribution_pct": 15.0},
            ]),
            "explanation_text": (
                "PM2.5 forecast driven by: Boundary layer height (38%), "
                "NW wind transport (25%), Stubble season (15%)."
            ),
            "model_version": "xgb_test_v1",
        })
    return rows


@pytest.fixture(scope="module")
def db_with_forecasts() -> DBClient:
    """In-memory DB pre-seeded with forecast rows."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    db = DBClient.__new__(DBClient)
    db._engine = engine
    db._Session = sessionmaker(bind=engine)

    rows = (
        _make_forecast_rows("DEL_ITO", n_hours=72)
        + _make_forecast_rows("DEL_ANAND_VIHAR", n_hours=72)
    )
    db.write_forecasts(pd.DataFrame(rows))
    return db


@pytest.fixture(scope="module")
def client_with_forecasts(db_with_forecasts: DBClient) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_with_forecasts
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="module")
def db_empty() -> DBClient:
    """In-memory DB with no forecast rows (only tables created)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = DBClient.__new__(DBClient)
    db._engine = engine
    db._Session = sessionmaker(bind=engine)
    return db


@pytest.fixture(scope="module")
def client_no_model(db_empty: DBClient) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_empty
    return TestClient(app, raise_server_exceptions=True)


# ===========================================================================
# Tests — no model (empty forecasts table)
# ===========================================================================

class TestForecastNoModel:
    """When no forecasts have been generated, endpoints return graceful empty responses."""

    def test_forecast_returns_200(self, client_no_model):
        resp = client_no_model.get("/forecast/DEL_ITO")
        assert resp.status_code == 200

    def test_forecast_model_trained_false_when_empty(self, client_no_model):
        body = client_no_model.get("/forecast/DEL_ITO").json()
        assert body["model_trained"] is False

    def test_forecast_empty_hourly_list(self, client_no_model):
        body = client_no_model.get("/forecast/DEL_ITO").json()
        assert body["count"] == 0
        assert body["hourly"] == []

    def test_forecast_has_informational_message(self, client_no_model):
        body = client_no_model.get("/forecast/DEL_ITO").json()
        assert "message" in body
        assert body["message"] is not None
        assert len(body["message"]) > 0

    def test_forecast_unknown_station_returns_404(self, client_no_model):
        resp = client_no_model.get("/forecast/INVALID_XYZ")
        assert resp.status_code == 404

    def test_forecast_404_has_detail(self, client_no_model):
        body = client_no_model.get("/forecast/NONEXISTENT").json()
        assert "detail" in body

    def test_explain_returns_200_when_no_model(self, client_no_model):
        resp = client_no_model.get("/forecast/DEL_ITO/explain")
        assert resp.status_code == 200

    def test_explain_shap_available_false_when_no_model(self, client_no_model):
        body = client_no_model.get("/forecast/DEL_ITO/explain").json()
        assert body["shap_available"] is False

    def test_explain_empty_top_features_when_no_model(self, client_no_model):
        body = client_no_model.get("/forecast/DEL_ITO/explain").json()
        assert body["top_features"] == []

    def test_explain_unknown_station_returns_404(self, client_no_model):
        resp = client_no_model.get("/forecast/INVALID_XYZ/explain")
        assert resp.status_code == 404

    def test_explain_invalid_target_returns_422(self, client_no_model):
        resp = client_no_model.get(
            "/forecast/DEL_ITO/explain",
            params={"target": "invalid_pollutant"},
        )
        assert resp.status_code == 422


# ===========================================================================
# Tests — with seeded forecasts
# ===========================================================================

class TestForecastWithData:

    def test_forecast_returns_200(self, client_with_forecasts):
        resp = client_with_forecasts.get("/forecast/DEL_ITO")
        assert resp.status_code == 200

    def test_forecast_model_trained_true(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO").json()
        assert body["model_trained"] is True

    def test_forecast_returns_72_hours(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO").json()
        assert body["count"] == 72
        assert len(body["hourly"]) == 72

    def test_forecast_hours_parameter_respected(self, client_with_forecasts):
        body = client_with_forecasts.get(
            "/forecast/DEL_ITO", params={"hours": 24}
        ).json()
        assert body["count"] == 24
        assert len(body["hourly"]) == 24

    def test_forecast_hour_field_is_1_to_72(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO").json()
        hours = [h["forecast_hour"] for h in body["hourly"]]
        assert hours == list(range(1, 73))

    def test_forecast_pm25_is_float_not_nan(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO").json()
        raw = client_with_forecasts.get("/forecast/DEL_ITO").text
        assert "NaN" not in raw
        for hour in body["hourly"]:
            pm25 = hour.get("pm25")
            assert pm25 is None or isinstance(pm25, (int, float))

    def test_forecast_aqi_category_valid(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO").json()
        valid = {"Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"}
        for hour in body["hourly"]:
            cat = hour.get("aqi_category")
            if cat is not None:
                assert cat in valid, f"Unexpected AQI category: {cat}"

    def test_forecast_has_station_id(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO").json()
        assert body["station_id"] == "DEL_ITO"

    def test_forecast_has_generated_at(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO").json()
        assert body.get("generated_at") is not None

    def test_forecast_has_model_version(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO").json()
        assert body.get("model_version") == "xgb_test_v1"

    def test_no_nan_in_response(self, client_with_forecasts):
        raw = client_with_forecasts.get("/forecast/DEL_ITO").text
        assert "NaN" not in raw

    def test_forecast_for_multiple_stations(self, client_with_forecasts):
        for sid in ["DEL_ITO", "DEL_ANAND_VIHAR"]:
            body = client_with_forecasts.get(f"/forecast/{sid}").json()
            assert body["model_trained"] is True
            assert body["count"] > 0

    def test_forecast_unknown_station_returns_404(self, client_with_forecasts):
        resp = client_with_forecasts.get("/forecast/UNKNOWN_STATION")
        assert resp.status_code == 404

    def test_forecast_hours_must_be_1_to_72(self, client_with_forecasts):
        resp = client_with_forecasts.get(
            "/forecast/DEL_ITO", params={"hours": 0}
        )
        assert resp.status_code == 422

        resp = client_with_forecasts.get(
            "/forecast/DEL_ITO", params={"hours": 100}
        )
        assert resp.status_code == 422


# ===========================================================================
# Explanation endpoint tests — with seeded data
# ===========================================================================

class TestExplanationWithData:

    def test_explain_returns_200(self, client_with_forecasts):
        resp = client_with_forecasts.get("/forecast/DEL_ITO/explain")
        assert resp.status_code == 200

    def test_explain_shap_available_true(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO/explain").json()
        assert body["shap_available"] is True

    def test_explain_top_features_non_empty(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO/explain").json()
        assert len(body["top_features"]) >= 1

    def test_explain_top_features_have_required_fields(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO/explain").json()
        for f in body["top_features"]:
            assert "name" in f
            assert "label" in f
            assert "shap_value" in f
            assert "contribution_pct" in f

    def test_explain_text_is_non_empty(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO/explain").json()
        assert isinstance(body["explanation_text"], str)
        assert len(body["explanation_text"]) > 0

    def test_explain_inversion_detected_is_bool(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO/explain").json()
        assert isinstance(body["inversion_detected"], bool)

    def test_explain_station_id_correct(self, client_with_forecasts):
        body = client_with_forecasts.get("/forecast/DEL_ITO/explain").json()
        assert body["station_id"] == "DEL_ITO"

    def test_explain_target_pm10(self, client_with_forecasts):
        resp = client_with_forecasts.get(
            "/forecast/DEL_ITO/explain", params={"target": "pm10"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["target"] == "pm10"

    def test_explain_unknown_station_404(self, client_with_forecasts):
        resp = client_with_forecasts.get("/forecast/UNKNOWN_XYZ/explain")
        assert resp.status_code == 404

    def test_explain_invalid_target_422(self, client_with_forecasts):
        resp = client_with_forecasts.get(
            "/forecast/DEL_ITO/explain",
            params={"target": "methane"},
        )
        assert resp.status_code == 422

    def test_no_nan_in_explain_response(self, client_with_forecasts):
        raw = client_with_forecasts.get("/forecast/DEL_ITO/explain").text
        assert "NaN" not in raw
