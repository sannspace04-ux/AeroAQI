"""
tests/integration/test_api_fire.py
=====================================
Integration tests for fire / hotspot endpoints:
  GET /fire/detections
  GET /fire/risk
  GET /fire/risk/{station_id}

All data comes from conftest.py's in-memory DB (3 seeded fire detections).

Run with:
    pytest tests/integration/test_api_fire.py -v
"""

import pytest


# ===========================================================================
# GET /fire/detections
# ===========================================================================

class TestFireDetections:

    def test_returns_200(self, client):
        resp = client.get("/fire/detections", params={"hours": 720})
        assert resp.status_code == 200

    def test_response_has_required_keys(self, client):
        body = client.get("/fire/detections", params={"hours": 720}).json()
        assert "count" in body
        assert "detections" in body

    def test_returns_seeded_fire_data(self, client):
        body = client.get("/fire/detections", params={"hours": 720}).json()
        # conftest seeds 3 fire detection rows
        assert body["count"] >= 3
        assert len(body["detections"]) >= 3

    def test_detection_record_has_coordinates(self, client):
        body = client.get("/fire/detections", params={"hours": 720}).json()
        if body["count"] > 0:
            det = body["detections"][0]
            assert "latitude" in det
            assert "longitude" in det
            assert det["latitude"] is not None
            assert det["longitude"] is not None

    def test_detection_record_has_frp(self, client):
        body = client.get("/fire/detections", params={"hours": 720}).json()
        if body["count"] > 0:
            det = body["detections"][0]
            assert "frp" in det

    def test_detection_record_has_confidence(self, client):
        body = client.get("/fire/detections", params={"hours": 720}).json()
        if body["count"] > 0:
            det = body["detections"][0]
            assert "confidence" in det

    def test_no_nan_in_response(self, client):
        raw = client.get("/fire/detections", params={"hours": 720}).text
        assert "NaN" not in raw

    def test_limit_parameter_respected(self, client):
        body = client.get(
            "/fire/detections",
            params={"hours": 720, "limit": 1},
        ).json()
        assert len(body["detections"]) <= 1

    def test_confidence_filter_nominal(self, client):
        body = client.get(
            "/fire/detections",
            params={"hours": 720, "min_confidence": "nominal"},
        ).json()
        for det in body["detections"]:
            conf = det.get("confidence", "").lower()
            assert conf in ("nominal", "high"), (
                f"Unexpected confidence '{conf}' after nominal filter"
            )

    def test_confidence_filter_high(self, client):
        body = client.get(
            "/fire/detections",
            params={"hours": 720, "min_confidence": "high"},
        ).json()
        # Seeded data has 1 high-confidence row
        for det in body["detections"]:
            assert det.get("confidence", "").lower() == "high"

    def test_invalid_confidence_filter_returns_422(self, client):
        resp = client.get(
            "/fire/detections",
            params={"min_confidence": "extreme"},
        )
        assert resp.status_code == 422

    def test_coordinates_in_source_region(self, client):
        """All seeded fires should be in the Punjab/Haryana bounding box."""
        body = client.get("/fire/detections", params={"hours": 720}).json()
        for det in body["detections"]:
            if det["latitude"] is not None:
                assert 27.0 <= det["latitude"] <= 34.0, (
                    f"Fire lat {det['latitude']} outside expected region"
                )

    def test_has_start_end_time_in_response(self, client):
        body = client.get("/fire/detections", params={"hours": 720}).json()
        assert "start_time" in body
        assert "end_time" in body

    def test_empty_window_returns_zero_count(self, client):
        """A tiny future time window should return no detections."""
        body = client.get(
            "/fire/detections",
            params={
                "start_time": "2099-01-01T00:00:00",
                "end_time":   "2099-01-01T01:00:00",
            },
        ).json()
        assert body["count"] == 0
        assert body["detections"] == []


# ===========================================================================
# GET /fire/risk
# ===========================================================================

class TestFireRisk:

    def test_returns_200(self, client):
        resp = client.get("/fire/risk", params={"hours": 720})
        assert resp.status_code == 200

    def test_response_has_required_keys(self, client):
        body = client.get("/fire/risk", params={"hours": 720}).json()
        assert "count" in body
        assert "records" in body

    def test_records_have_station_id(self, client):
        body = client.get("/fire/risk", params={"hours": 720}).json()
        for rec in body["records"]:
            assert "station_id" in rec

    def test_risk_score_null_when_not_computed(self, client):
        """fire_transport_risk is None when fire data hasn't been aggregated yet."""
        body = client.get(
            "/fire/risk",
            params={"station_id": "DEL_ITO", "hours": 720},
        ).json()
        if body["count"] > 0:
            # Either null (no fire aggregation run) or a valid [0,1] float
            for rec in body["records"]:
                risk = rec.get("fire_transport_risk")
                assert risk is None or (0.0 <= risk <= 1.0), (
                    f"fire_transport_risk out of range: {risk}"
                )

    def test_no_nan_in_response(self, client):
        raw = client.get("/fire/risk", params={"hours": 720}).text
        assert "NaN" not in raw

    def test_station_filter(self, client):
        body = client.get(
            "/fire/risk",
            params={"station_id": "DEL_ITO", "hours": 720},
        ).json()
        for rec in body["records"]:
            assert rec["station_id"] == "DEL_ITO"


# ===========================================================================
# GET /fire/risk/{station_id}
# ===========================================================================

class TestFireRiskByStation:

    def test_valid_station_returns_200(self, client):
        resp = client.get("/fire/risk/DEL_ITO", params={"hours": 720})
        assert resp.status_code == 200

    def test_data_belongs_to_station(self, client):
        body = client.get("/fire/risk/DEL_ITO", params={"hours": 720}).json()
        for rec in body["records"]:
            assert rec["station_id"] == "DEL_ITO"

    def test_unknown_station_returns_404(self, client):
        resp = client.get("/fire/risk/INVALID_XYZ", params={"hours": 720})
        assert resp.status_code == 404

    def test_404_has_detail(self, client):
        body = client.get("/fire/risk/BAD_STATION", params={"hours": 720}).json()
        assert "detail" in body

    def test_limit_parameter_respected(self, client):
        body = client.get(
            "/fire/risk/DEL_ITO",
            params={"hours": 720, "limit": 1},
        ).json()
        assert len(body["records"]) <= 1
