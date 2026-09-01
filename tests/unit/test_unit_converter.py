"""
tests/unit/test_unit_converter.py
===================================
Unit tests for src/processing/unit_converter.py

All tests are pure in-memory — no network calls, no file I/O.
Synthetic values are clearly labelled and chosen to make manual
verification easy (round numbers, known physical outcomes).

Run with:
    pytest tests/unit/test_unit_converter.py -v
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.processing.unit_converter import (
    compute_cpcb_aqi,
    fahrenheit_to_celsius,
    haversine_km,
    haversine_km_vectorised,
    j_per_m2_to_w_per_m2,
    kelvin_to_celsius,
    m_to_mm,
    nw_wind_alignment,
    pa_to_hpa,
    ppb_to_mgm3,
    ppb_to_ugm3,
    ppm_to_mgm3,
    ppm_to_ugm3,
    uv_to_speed_direction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _s(*vals) -> pd.Series:
    """Build a float Series from scalars."""
    return pd.Series(vals, dtype=float)


def _nan() -> float:
    return float("nan")


# ===========================================================================
# Temperature
# ===========================================================================

class TestKelvinToCelsius:

    def test_freezing_point(self):
        result = kelvin_to_celsius(_s(273.15))
        assert abs(result.iloc[0] - 0.0) < 1e-6

    def test_boiling_point(self):
        result = kelvin_to_celsius(_s(373.15))
        assert abs(result.iloc[0] - 100.0) < 1e-6

    def test_typical_delhi_temp(self):
        # 302 K ≈ 28.85 °C
        result = kelvin_to_celsius(_s(302.0))
        assert abs(result.iloc[0] - 28.85) < 1e-6

    def test_nan_stays_nan(self):
        result = kelvin_to_celsius(_s(_nan()))
        assert math.isnan(result.iloc[0])

    def test_vectorised(self):
        result = kelvin_to_celsius(_s(273.15, 373.15, 300.0))
        assert abs(result.iloc[0] - 0.0) < 1e-6
        assert abs(result.iloc[1] - 100.0) < 1e-6
        assert abs(result.iloc[2] - 26.85) < 1e-6


class TestFahrenheitToCelsius:

    def test_freezing(self):
        result = fahrenheit_to_celsius(_s(32.0))
        assert abs(result.iloc[0] - 0.0) < 1e-6

    def test_boiling(self):
        result = fahrenheit_to_celsius(_s(212.0))
        assert abs(result.iloc[0] - 100.0) < 1e-6

    def test_body_temp(self):
        # 98.6 °F = 37.0 °C
        result = fahrenheit_to_celsius(_s(98.6))
        assert abs(result.iloc[0] - 37.0) < 0.01


# ===========================================================================
# Pressure
# ===========================================================================

class TestPaToHpa:

    def test_standard_atmosphere(self):
        # 101325 Pa = 1013.25 hPa
        result = pa_to_hpa(_s(101325.0))
        assert abs(result.iloc[0] - 1013.25) < 1e-6

    def test_typical_surface_pressure(self):
        # 99500 Pa = 995.0 hPa
        result = pa_to_hpa(_s(99500.0))
        assert abs(result.iloc[0] - 995.0) < 1e-6

    def test_nan_stays_nan(self):
        result = pa_to_hpa(_s(_nan()))
        assert math.isnan(result.iloc[0])


# ===========================================================================
# Gas concentration conversions
# ===========================================================================

class TestPpbToUgm3:

    def test_no2_at_25c(self):
        # 1 ppb NO2 at 25 °C = 46.006 / 24.45 ≈ 1.882 µg/m³
        result = ppb_to_ugm3(_s(1.0), "no2", temp_c=25.0)
        expected = 46.006 / 24.45
        assert abs(result.iloc[0] - expected) < 0.01

    def test_o3_at_25c(self):
        # 1 ppb O3 at 25 °C = 47.998 / 24.45 ≈ 1.963 µg/m³
        result = ppb_to_ugm3(_s(1.0), "o3", temp_c=25.0)
        expected = 47.998 / 24.45
        assert abs(result.iloc[0] - expected) < 0.01

    def test_so2_at_25c(self):
        result = ppb_to_ugm3(_s(1.0), "so2", temp_c=25.0)
        expected = 64.066 / 24.45
        assert abs(result.iloc[0] - expected) < 0.01

    def test_nan_stays_nan(self):
        result = ppb_to_ugm3(_s(_nan()), "no2")
        assert math.isnan(result.iloc[0])

    def test_zero_input_gives_zero(self):
        result = ppb_to_ugm3(_s(0.0), "no2")
        assert result.iloc[0] == 0.0

    def test_unknown_species_raises(self):
        with pytest.raises(ValueError, match="Unknown species"):
            ppb_to_ugm3(_s(1.0), "methane")

    def test_case_insensitive_species(self):
        r1 = ppb_to_ugm3(_s(10.0), "NO2")
        r2 = ppb_to_ugm3(_s(10.0), "no2")
        assert abs(r1.iloc[0] - r2.iloc[0]) < 1e-9

    def test_temperature_effect(self):
        # Higher temperature → larger molar volume → lower µg/m³
        at_25 = ppb_to_ugm3(_s(100.0), "no2", temp_c=25.0).iloc[0]
        at_40 = ppb_to_ugm3(_s(100.0), "no2", temp_c=40.0).iloc[0]
        assert at_25 > at_40


class TestPpmToUgm3:

    def test_equals_1000x_ppb(self):
        ppb_result = ppb_to_ugm3(_s(1000.0), "no2")
        ppm_result = ppm_to_ugm3(_s(1.0), "no2")
        assert abs(ppb_result.iloc[0] - ppm_result.iloc[0]) < 1e-6


class TestPpbToMgm3:

    def test_co_unit_conversion(self):
        # 1000 ppb CO → µg/m³ ÷ 1000 → mg/m³
        ugm3 = ppb_to_ugm3(_s(1000.0), "co").iloc[0]
        mgm3 = ppb_to_mgm3(_s(1000.0), "co").iloc[0]
        assert abs(mgm3 - ugm3 / 1000.0) < 1e-9


# ===========================================================================
# Radiation and precipitation
# ===========================================================================

class TestJPerM2ToWPerM2:

    def test_1_hour_accumulation(self):
        # 3600 J/m² over 1 h = 1 W/m²
        result = j_per_m2_to_w_per_m2(_s(3600.0), seconds=3600.0)
        assert abs(result.iloc[0] - 1.0) < 1e-9

    def test_typical_noon_solar(self):
        # ~3_000_000 J/m² over 1 h ≈ 833 W/m²
        result = j_per_m2_to_w_per_m2(_s(3_000_000.0))
        assert abs(result.iloc[0] - 833.33) < 1.0

    def test_negative_clipped_to_zero(self):
        # Negative values (ERA5 numerical artefact) must be clipped to 0
        result = j_per_m2_to_w_per_m2(_s(-100.0))
        assert result.iloc[0] == 0.0

    def test_nan_stays_nan(self):
        result = j_per_m2_to_w_per_m2(_s(_nan()))
        assert math.isnan(result.iloc[0])


class TestMToMm:

    def test_1_metre_is_1000_mm(self):
        result = m_to_mm(_s(1.0))
        assert abs(result.iloc[0] - 1000.0) < 1e-9

    def test_typical_hourly_rainfall(self):
        # 0.002 m/hr = 2 mm/hr
        result = m_to_mm(_s(0.002))
        assert abs(result.iloc[0] - 2.0) < 1e-9

    def test_negative_clipped_to_zero(self):
        result = m_to_mm(_s(-0.001))
        assert result.iloc[0] == 0.0

    def test_nan_stays_nan(self):
        result = m_to_mm(_s(_nan()))
        assert math.isnan(result.iloc[0])


# ===========================================================================
# Wind
# ===========================================================================

class TestUvToSpeedDirection:

    def test_northward_wind_from_south(self):
        # V = +10 (northward), U = 0 → wind FROM south → direction = 180°
        speed, direction = uv_to_speed_direction(_s(0.0), _s(10.0))
        assert abs(speed.iloc[0] - 10.0) < 1e-6
        assert abs(direction.iloc[0] - 180.0) < 1e-6

    def test_eastward_wind_from_west(self):
        # U = +10 (eastward), V = 0 → wind FROM west → direction = 270°
        speed, direction = uv_to_speed_direction(_s(10.0), _s(0.0))
        assert abs(speed.iloc[0] - 10.0) < 1e-6
        assert abs(direction.iloc[0] - 270.0) < 1e-6

    def test_nw_wind_from_se(self):
        # Wind FROM northwest (blowing toward southeast):
        # U = +1 (eastward component), V = -1 (southward component)
        # atan2(-1, +1) = -45° → (270 - (-45)) % 360 = 315° FROM NW
        speed, direction = uv_to_speed_direction(_s(1.0), _s(-1.0))
        assert abs(speed.iloc[0] - math.sqrt(2)) < 1e-6
        assert abs(direction.iloc[0] - 315.0) < 0.01

    def test_calm_wind_zero_speed(self):
        speed, direction = uv_to_speed_direction(_s(0.0), _s(0.0))
        assert speed.iloc[0] == 0.0

    def test_speed_always_non_negative(self):
        speed, _ = uv_to_speed_direction(_s(-5.0, 3.0, -2.0), _s(2.0, -4.0, 1.0))
        assert (speed >= 0).all()


# ===========================================================================
# Haversine distance
# ===========================================================================

class TestHaversineKm:

    def test_same_point_is_zero(self):
        d = haversine_km(28.62, 77.22, 28.62, 77.22)
        assert d == 0.0

    def test_delhi_to_amritsar_approx_430km(self):
        # Delhi (28.62°N, 77.22°E) to Amritsar (31.63°N, 74.87°E)
        d = haversine_km(28.62, 77.22, 31.63, 74.87)
        assert 400 < d < 450, f"Expected ~430 km, got {d:.1f}"

    def test_delhi_to_chandigarh_approx_250km(self):
        d = haversine_km(28.62, 77.22, 30.74, 76.79)
        assert 230 < d < 270, f"Expected ~250 km, got {d:.1f}"

    def test_antipodal_is_half_circumference(self):
        # Two antipodal points should be ~20015 km apart
        d = haversine_km(0, 0, 0, 180)
        assert abs(d - 20015.09) < 5.0

    def test_commutative(self):
        d1 = haversine_km(28.62, 77.22, 30.74, 76.79)
        d2 = haversine_km(30.74, 76.79, 28.62, 77.22)
        assert abs(d1 - d2) < 1e-9


class TestHaversineKmVectorised:

    def test_matches_scalar_version(self):
        lats = pd.Series([30.74, 31.63, 28.62])
        lons = pd.Series([76.79, 74.87, 77.22])
        ref_lat, ref_lon = 28.62, 77.22

        vectorised = haversine_km_vectorised(ref_lat, ref_lon, lats, lons)
        scalars = [haversine_km(ref_lat, ref_lon, lat, lon)
                   for lat, lon in zip(lats, lons)]

        for v, s in zip(vectorised, scalars):
            assert abs(v - s) < 1e-6

    def test_same_point_gives_zero(self):
        lats = pd.Series([28.62])
        lons = pd.Series([77.22])
        result = haversine_km_vectorised(28.62, 77.22, lats, lons)
        assert result.iloc[0] < 1e-6

    def test_preserves_index(self):
        lats = pd.Series([30.74, 31.63], index=[10, 20])
        lons = pd.Series([76.79, 74.87], index=[10, 20])
        result = haversine_km_vectorised(28.62, 77.22, lats, lons)
        assert list(result.index) == [10, 20]


# ===========================================================================
# NW wind alignment
# ===========================================================================

class TestNwWindAlignment:

    def test_perfect_nw_gives_one(self):
        # Wind from exactly 315° → alignment = 1.0
        result = nw_wind_alignment(_s(315.0))
        assert abs(result.iloc[0] - 1.0) < 1e-9

    def test_opposite_se_gives_zero(self):
        # Wind from 135° (SE, opposite of NW) → (1 + cos(180°)) / 2 = 0
        result = nw_wind_alignment(_s(135.0))
        assert abs(result.iloc[0] - 0.0) < 1e-9

    def test_north_wind_is_half(self):
        # 0° is 315° away → (1 + cos(-315°)) / 2 = (1 + cos(45°)) / 2 ≈ 0.854
        result = nw_wind_alignment(_s(0.0))
        expected = (1 + math.cos(math.radians(0 - 315))) / 2
        assert abs(result.iloc[0] - expected) < 1e-9

    def test_result_always_in_0_1(self):
        directions = _s(0, 45, 90, 135, 180, 225, 270, 315, 360)
        result = nw_wind_alignment(directions)
        assert (result >= 0.0).all()
        assert (result <= 1.0).all()

    def test_nan_propagates(self):
        result = nw_wind_alignment(_s(_nan()))
        assert math.isnan(result.iloc[0])


# ===========================================================================
# CPCB AQI computation
# ===========================================================================

class TestComputeCpcbAqi:

    def test_zero_pm_gives_zero_aqi(self):
        result = compute_cpcb_aqi(_s(0.0), _s(0.0))
        assert result.iloc[0] == 0.0

    def test_good_category_pm25_30(self):
        # PM2.5 = 30 µg/m³ → sub-index = 50 (top of Good category)
        result = compute_cpcb_aqi(_s(30.0), _s(0.0))
        assert abs(result.iloc[0] - 50.0) < 1e-3

    def test_moderate_category_pm25_45(self):
        # PM2.5 = 45 µg/m³ is in [30, 60] → sub-index in (50, 100]
        result = compute_cpcb_aqi(_s(45.0), _s(0.0))
        assert 50 < result.iloc[0] <= 100

    def test_pm10_drives_aqi_when_higher(self):
        # PM10 = 200 µg/m³ (sub-index ~110) > PM2.5 = 20 µg/m³ (sub-index ~33)
        result = compute_cpcb_aqi(_s(20.0), _s(200.0))
        # Should be dominated by PM10 sub-index
        pm25_only = compute_cpcb_aqi(_s(20.0), _s(0.0)).iloc[0]
        assert result.iloc[0] > pm25_only

    def test_both_nan_gives_nan(self):
        result = compute_cpcb_aqi(_s(_nan()), _s(_nan()))
        assert math.isnan(result.iloc[0])

    def test_one_nan_uses_other(self):
        # Only PM10 available
        result_pm10_only = compute_cpcb_aqi(_s(_nan()), _s(100.0))
        assert not math.isnan(result_pm10_only.iloc[0])
        # Only PM2.5 available
        result_pm25_only = compute_cpcb_aqi(_s(30.0), _s(_nan()))
        assert not math.isnan(result_pm25_only.iloc[0])

    def test_severe_pm25_gives_aqi_above_300(self):
        # PM2.5 = 200 µg/m³ → should be in Severe range (AQI 301–400)
        result = compute_cpcb_aqi(_s(200.0), _s(0.0))
        assert result.iloc[0] > 300

    def test_result_never_negative(self):
        result = compute_cpcb_aqi(_s(0.0, 10.0, 60.0, 150.0),
                                  _s(0.0, 50.0, 100.0, 300.0))
        assert (result >= 0).all()

    def test_vectorised_multiple_rows(self):
        pm25 = _s(10.0, 45.0, 90.0, 200.0)
        pm10 = _s(30.0, 80.0, 200.0, 400.0)
        result = compute_cpcb_aqi(pm25, pm10)
        assert len(result) == 4
        # AQI should be monotonically increasing with concentrations here
        assert result.iloc[0] < result.iloc[1] < result.iloc[2]
