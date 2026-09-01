"""
tests/integration/test_api_stations.py
========================================
Integration tests for GET /stations and GET /stations/{station_id}.

Station data comes from config/stations.yaml (no DB dependency).
All 15 stations are expected to be present and active.

Run with:
    pytest tests/integration/test_api_stations.py -v
"""

import pytest


class TestListStations:

    def test_returns_200(self, client):
        resp = client.get("/stations")
        assert resp.status_code == 200

    def test_returns_all_15_stations(self, client):
        body = client.get("/stations").json()
        assert body["count"] == 15
        assert len(body["stations"]) == 15

    def test_response_has_count_and_stations_keys(self, client):
        body = client.get("/stations").json()
        assert "count" in body
        assert "stations" in body

    def test_each_station_has_required_fields(self, client):
        body = client.get("/stations").json()
        required = {"station_id", "name", "city", "state", "latitude", "longitude",
                    "agency", "zone", "active"}
        for s in body["stations"]:
            for field in required:
                assert field in s, f"Station missing field '{field}': {s}"

    def test_coordinates_in_valid_range(self, client):
        body = client.get("/stations").json()
        for s in body["stations"]:
            assert 23.0 <= s["latitude"] <= 32.0, f"Lat out of range: {s}"
            assert 73.0 <= s["longitude"] <= 80.0, f"Lon out of range: {s}"

    def test_all_stations_are_active(self, client):
        body = client.get("/stations").json()
        for s in body["stations"]:
            assert s["active"] is True

    def test_stations_include_delhi_ncr_cities(self, client):
        body = client.get("/stations").json()
        cities = {s["city"] for s in body["stations"]}
        expected_cities = {"Delhi", "Noida", "Gurugram", "Faridabad", "Ghaziabad"}
        assert expected_cities.issubset(cities)

    def test_station_ids_are_strings(self, client):
        body = client.get("/stations").json()
        for s in body["stations"]:
            assert isinstance(s["station_id"], str)
            assert len(s["station_id"]) > 0

    def test_agencies_are_known_values(self, client):
        body = client.get("/stations").json()
        known = {"DPCC", "UPPCB", "HSPCB"}
        for s in body["stations"]:
            assert s["agency"] in known, f"Unknown agency: {s['agency']}"

    def test_response_content_type(self, client):
        resp = client.get("/stations")
        assert "application/json" in resp.headers["content-type"]


class TestGetSingleStation:

    def test_valid_station_returns_200(self, client):
        resp = client.get("/stations/DEL_ITO")
        assert resp.status_code == 200

    def test_valid_station_returns_correct_data(self, client):
        body = client.get("/stations/DEL_ITO").json()
        assert body["station_id"] == "DEL_ITO"
        assert body["name"] == "ITO"
        assert body["city"] == "Delhi"
        assert body["agency"] == "DPCC"

    def test_valid_station_has_coordinates(self, client):
        body = client.get("/stations/DEL_ITO").json()
        assert abs(body["latitude"] - 28.6289) < 0.001
        assert abs(body["longitude"] - 77.2412) < 0.001

    def test_noida_station(self, client):
        body = client.get("/stations/NOI_SECTOR62").json()
        assert body["station_id"] == "NOI_SECTOR62"
        assert body["city"] == "Noida"
        assert body["state"] == "Uttar Pradesh"

    def test_faridabad_station(self, client):
        body = client.get("/stations/FBD_SECTOR16A").json()
        assert body["station_id"] == "FBD_SECTOR16A"
        assert body["agency"] == "HSPCB"

    def test_unknown_station_returns_404(self, client):
        resp = client.get("/stations/INVALID_STATION_XYZ")
        assert resp.status_code == 404

    def test_404_response_has_detail(self, client):
        body = client.get("/stations/DOES_NOT_EXIST").json()
        assert "detail" in body
        assert "DOES_NOT_EXIST" in body["detail"]

    def test_all_15_stations_are_individually_accessible(self, client):
        """Each station listed by /stations should be fetchable by /stations/{id}."""
        stations_list = client.get("/stations").json()["stations"]
        for s in stations_list:
            resp = client.get(f"/stations/{s['station_id']}")
            assert resp.status_code == 200, (
                f"Station {s['station_id']} returned {resp.status_code}"
            )
