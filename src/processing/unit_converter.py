"""
src/processing/unit_converter.py
==================================
Unit conversion utilities for AeroAQI.

All measurements in the master dataset use a single canonical unit per
variable (defined in master_schema.py).  This module converts values from
the units that data sources report into those canonical units.

Canonical units
---------------
  pm25, pm10, o3, no2, so2  →  µg/m³
  co                        →  mg/m³
  temperature               →  °C
  surface_pressure          →  hPa
  wind_speed                →  m/s
  solar_radiation           →  W/m²
  precipitation             →  mm/hr

Design rules
------------
- Every function operates on a pandas Series (or scalar) and returns the
  same type.
- No function ever silently replaces invalid inputs with zero.
  NaN inputs remain NaN in the output.
- Conversion factors are documented with their source.
- Functions are pure (no side-effects) for easy unit testing.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Temperature
# ---------------------------------------------------------------------------

def kelvin_to_celsius(values: pd.Series) -> pd.Series:
    """
    Convert Kelvin → Celsius.
    ERA5 reports temperatures in Kelvin.

    K − 273.15 = °C

    Parameters
    ----------
    values : pd.Series  —  temperature values in Kelvin (K)

    Returns
    -------
    pd.Series  —  temperature in degrees Celsius (°C)
    """
    return values - 273.15


def fahrenheit_to_celsius(values: pd.Series) -> pd.Series:
    """
    Convert Fahrenheit → Celsius.

    (°F − 32) × 5/9 = °C
    """
    return (values - 32.0) * (5.0 / 9.0)


# ---------------------------------------------------------------------------
# Pressure
# ---------------------------------------------------------------------------

def pa_to_hpa(values: pd.Series) -> pd.Series:
    """
    Convert Pascals → hectopascals (millibars).
    ERA5 surface_pressure is in Pa; master schema uses hPa.

    1 hPa = 100 Pa
    """
    return values / 100.0


# ---------------------------------------------------------------------------
# Concentration — ppb / ppm to µg/m³
# ---------------------------------------------------------------------------

# Molecular weights (g/mol) used in ppb → µg/m³ conversions.
# At standard conditions (25 °C, 1 atm): 1 ppb = MW/24.45 µg/m³
# Reference: US EPA / WHO guidance on unit conversions.
_MW = {
    "o3":   47.998,
    "no2":  46.006,
    "so2":  64.066,
    "co":   28.010,
    "no":   30.006,
    "nox":  46.006,   # treated as NO2 equivalent
}

_MOLAR_VOLUME_25C = 24.45   # L/mol at 25 °C, 1 atm


def ppb_to_ugm3(values: pd.Series, species: str, temp_c: float = 25.0) -> pd.Series:
    """
    Convert gas concentration from ppb (parts-per-billion by volume)
    to µg/m³.

    Formula:  µg/m³ = ppb × MW / Vm
    where Vm = molar volume at the given temperature (litres/mol).

    Molar volume at temperature T (°C):
        Vm = 22.414 × (T + 273.15) / 273.15  litres/mol

    Parameters
    ----------
    values  : pd.Series  —  concentration in ppb
    species : str        —  one of: o3, no2, so2, co, no, nox
    temp_c  : float      —  air temperature in °C (default 25 °C)

    Returns
    -------
    pd.Series  —  concentration in µg/m³

    Raises
    ------
    ValueError if species is not recognised.
    """
    species = species.lower().strip()
    if species not in _MW:
        raise ValueError(
            f"Unknown species '{species}' for ppb → µg/m³ conversion. "
            f"Supported: {list(_MW.keys())}"
        )
    mw = _MW[species]
    vm = 22.414 * (temp_c + 273.15) / 273.15   # actual molar volume
    factor = mw / vm
    return values * factor


def ppm_to_ugm3(values: pd.Series, species: str, temp_c: float = 25.0) -> pd.Series:
    """
    Convert gas concentration from ppm (parts-per-million by volume)
    to µg/m³.

    1 ppm = 1000 ppb
    """
    return ppb_to_ugm3(values * 1000.0, species, temp_c)


def ppm_to_mgm3(values: pd.Series, species: str, temp_c: float = 25.0) -> pd.Series:
    """
    Convert CO from ppm to mg/m³.
    CO master-schema unit is mg/m³.

    µg/m³ ÷ 1000 = mg/m³
    """
    ugm3 = ppm_to_ugm3(values, species, temp_c)
    return ugm3 / 1000.0


def ppb_to_mgm3(values: pd.Series, species: str, temp_c: float = 25.0) -> pd.Series:
    """
    Convert CO from ppb to mg/m³ (CO master-schema unit).
    """
    ugm3 = ppb_to_ugm3(values, species, temp_c)
    return ugm3 / 1000.0


# ---------------------------------------------------------------------------
# Radiation / Energy
# ---------------------------------------------------------------------------

def j_per_m2_to_w_per_m2(values: pd.Series, seconds: float = 3600.0) -> pd.Series:
    """
    Convert accumulated solar radiation from J/m² to W/m² (average flux).

    ERA5 reports surface_solar_radiation_downwards as a joule accumulation
    over the output time step.  Dividing by the step duration (in seconds)
    gives the average flux in W/m².

    Default assumes a 1-hour accumulation period (3600 s).

    Parameters
    ----------
    values  : pd.Series  —  accumulated radiation in J/m²
    seconds : float      —  accumulation period in seconds (default 3600)

    Returns
    -------
    pd.Series  —  average radiation flux in W/m²
    """
    result = values / seconds
    # Radiation cannot be negative; ERA5 sometimes has tiny negative
    # values due to numerical artefacts.
    return result.clip(lower=0.0)


# ---------------------------------------------------------------------------
# Precipitation
# ---------------------------------------------------------------------------

def m_to_mm(values: pd.Series) -> pd.Series:
    """
    Convert precipitation from metres to millimetres.
    ERA5 reports total_precipitation in metres per hour.
    Master schema uses mm/hr.

    1 m = 1000 mm
    """
    result = values * 1000.0
    # Precipitation cannot be negative
    return result.clip(lower=0.0)


# ---------------------------------------------------------------------------
# Wind
# ---------------------------------------------------------------------------

def uv_to_speed_direction(
    u: pd.Series, v: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """
    Convert U (eastward) and V (northward) wind components to
    speed (m/s) and meteorological direction (degrees).

    Meteorological convention:
        Direction = angle the wind is coming FROM (0° = from North).
        270° − atan2(v, u)  (mod 360)

    Parameters
    ----------
    u : pd.Series  — eastward wind component (m/s)
    v : pd.Series  — northward wind component (m/s)

    Returns
    -------
    (speed, direction)  — both pd.Series
    """
    speed = np.sqrt(u ** 2 + v ** 2)
    # atan2(v, u) gives the mathematical angle; subtract from 270 for met convention
    direction = (270.0 - np.degrees(np.arctan2(v, u))) % 360.0
    return speed, direction


# ---------------------------------------------------------------------------
# AQI helper — CPCB sub-index breakpoints
# ---------------------------------------------------------------------------

# CPCB (India) National AQI breakpoints, as per CPCB document 2014.
# Source: Central Pollution Control Board, "National Air Quality Index", 2014.
# Format: [(C_lo, C_hi, I_lo, I_hi), ...] — concentration → AQI sub-index.
_CPCB_PM25_BREAKPOINTS = [
    (0.0,   30.0,   0,   50),
    (30.0,  60.0,  51,  100),
    (60.0,  90.0, 101,  200),
    (90.0, 120.0, 201,  300),
    (120.0, 250.0, 301, 400),
    (250.0, 500.0, 401, 500),
]

_CPCB_PM10_BREAKPOINTS = [
    (0.0,    50.0,   0,   50),
    (50.0,  100.0,  51,  100),
    (100.0, 250.0, 101,  200),
    (250.0, 350.0, 201,  300),
    (350.0, 430.0, 301,  400),
    (430.0, 600.0, 401,  500),
]


def _cpcb_subindex(concentration: float, breakpoints: list) -> float:
    """
    Compute a CPCB AQI sub-index for a single concentration value.

    Returns NaN if the concentration is NaN or outside all breakpoints.
    """
    if concentration is None or (isinstance(concentration, float) and math.isnan(concentration)):
        return float("nan")
    for c_lo, c_hi, i_lo, i_hi in breakpoints:
        if c_lo <= concentration <= c_hi:
            # Linear interpolation within the breakpoint range
            return i_lo + (concentration - c_lo) * (i_hi - i_lo) / (c_hi - c_lo)
    return float("nan")


def compute_cpcb_aqi(pm25: pd.Series, pm10: pd.Series) -> pd.Series:
    """
    Compute CPCB AQI from PM2.5 and PM10 concentrations.

    The CPCB method:
        1. Compute sub-index for each available pollutant.
        2. AQI = max(sub-indices)  for the available pollutants.
        3. If both PM2.5 and PM10 are NaN, the result is NaN.

    Parameters
    ----------
    pm25 : pd.Series  — PM2.5 concentration in µg/m³
    pm10 : pd.Series  — PM10 concentration in µg/m³

    Returns
    -------
    pd.Series  — computed AQI values (float), NaN where both inputs are NaN.
    """
    pm25_subidx = pm25.apply(
        lambda x: _cpcb_subindex(x, _CPCB_PM25_BREAKPOINTS)
    )
    pm10_subidx = pm10.apply(
        lambda x: _cpcb_subindex(x, _CPCB_PM10_BREAKPOINTS)
    )

    # Take the higher sub-index; if one is NaN use the other; both NaN → NaN
    combined = pd.concat([pm25_subidx, pm10_subidx], axis=1)
    return combined.max(axis=1, skipna=True).where(
        pm25.notna() | pm10.notna(), other=float("nan")
    )


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

_EARTH_RADIUS_KM = 6371.0


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Compute the great-circle distance between two points on Earth.

    Parameters
    ----------
    lat1, lon1 : decimal degrees — first point
    lat2, lon2 : decimal degrees — second point

    Returns
    -------
    float  — distance in kilometres

    Uses the haversine formula which is accurate for small and large
    distances alike (errors < 0.5% for most applications).
    """
    r = _EARTH_RADIUS_KM
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def haversine_km_vectorised(
    lat1: float, lon1: float,
    lat2: pd.Series, lon2: pd.Series,
) -> pd.Series:
    """
    Vectorised haversine: distance from one fixed point to many points.

    Parameters
    ----------
    lat1, lon1  : scalar — reference point (e.g. monitoring station)
    lat2, lon2  : pd.Series — array of target points (e.g. fire locations)

    Returns
    -------
    pd.Series  — distances in kilometres (same index as lat2/lon2)
    """
    r = _EARTH_RADIUS_KM
    phi1 = math.radians(lat1)
    phi2 = np.radians(lat2.astype(float))
    dphi = np.radians(lat2.astype(float) - lat1)
    dlambda = np.radians(lon2.astype(float) - lon1)
    a = (
        np.sin(dphi / 2) ** 2
        + math.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    )
    return pd.Series(2 * r * np.arcsin(np.sqrt(a)), index=lat2.index)


# ---------------------------------------------------------------------------
# Wind direction alignment score
# ---------------------------------------------------------------------------

def nw_wind_alignment(wind_direction: pd.Series) -> pd.Series:
    """
    Compute how well the current wind direction aligns with the
    north-west (NW) flow that transports Punjab/Haryana stubble smoke
    toward Delhi NCR.

    The "ideal" transport wind direction is 315° (NW — wind blowing FROM
    the northwest, i.e. source regions Punjab/Haryana toward Delhi).

    Score formula:
        alignment = (1 + cos(wind_direction − 315°)) / 2

    Returns a value in [0, 1]:
        1.0 = wind exactly from NW   (maximum transport risk)
        0.5 = wind perpendicular to NW axis
        0.0 = wind from SE           (minimum transport risk — blowing away)

    Parameters
    ----------
    wind_direction : pd.Series  —  wind direction in degrees (met convention,
                                   0° = from North, 90° = from East)

    Returns
    -------
    pd.Series  —  alignment scores in [0, 1], NaN where direction is NaN.
    """
    _IDEAL_DIR = 315.0   # NW (degrees)
    diff_rad = np.radians(wind_direction.astype(float) - _IDEAL_DIR)
    return (1.0 + np.cos(diff_rad)) / 2.0
