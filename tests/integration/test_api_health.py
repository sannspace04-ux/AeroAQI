"""
tests/integration/test_api_health.py
======================================
Integration tests for GET /health and GET /health/status.

These tests use the TestClient with an in-memory DB (via conftest.py).
No real API keys or external services are needed.

Run with:
    pytest tests/integration/test_api_health.py -v
"""

import pytest


class TestHealthEndpoint:

    def test_get_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_status_is_ok(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"

    def test_health_has_version(self, client):
        body = client.get("/health").json()
        assert "version" in body
        assert isinstance(body["version"], str)
        assert len(body["version"]) > 0

    def test_health_has_database_field(self, client):
        body = client.get("/health").json()
        assert "database" in body
        assert body["database"] == "connected"

    def test_health_has_observation_count(self, client):
        body = client.get("/health").json()
        assert "observations_count" in body
        # Seeded 6 observation rows in conftest
        assert body["observations_count"] >= 0
        assert isinstance(body["observations_count"], int)

    def test_health_has_fire_detections_count(self, client):
        body = client.get("/health").json()
        assert "fire_detections_count" in body
        assert isinstance(body["fire_detections_count"], int)
        assert body["fire_detections_count"] >= 0

    def test_health_response_schema_complete(self, client):
        body = client.get("/health").json()
        required_keys = {
            "status", "version", "database",
            "observations_count", "fire_detections_count",
        }
        for key in required_keys:
            assert key in body, f"Missing key in /health response: {key}"

    def test_health_content_type_is_json(self, client):
        resp = client.get("/health")
        assert "application/json" in resp.headers["content-type"]


class TestStatusEndpoint:

    def test_get_status_returns_200(self, client):
        resp = client.get("/health/status")
        assert resp.status_code == 200

    def test_status_returns_ok(self, client):
        body = client.get("/health/status").json()
        assert body["status"] == "ok"

    def test_status_database_connected(self, client):
        body = client.get("/health/status").json()
        assert body["database"] == "connected"

    def test_status_observation_count_matches_seeded_data(self, client):
        body = client.get("/health/status").json()
        # conftest seeds 6 observation rows
        assert body["observations_count"] >= 6

    def test_status_fire_count_matches_seeded_data(self, client):
        body = client.get("/health/status").json()
        # conftest seeds 3 fire detections
        assert body["fire_detections_count"] >= 3

    def test_status_and_health_return_same_structure(self, client):
        h = client.get("/health").json()
        s = client.get("/health/status").json()
        assert set(h.keys()) == set(s.keys())
