"""
src/schema/master_schema.py
===========================
Defines the single, canonical "master observation" schema for AeroAQI.

Every data source produces its own raw format (JSON, CSV, NetCDF …).
After fetching and basic cleaning, data from all sources is mapped onto
this schema before being stored or joined.

Design rules
------------
1.  One row = one hourly observation at one (station OR grid-point) location.
2.  The join key is (timestamp_utc, station_id).
3.  Columns that a source CANNOT provide are left as NaN / None — never
    filled with zero.
4.  Three column categories are documented here:
      OBSERVED   – comes directly from a data source.
      DERIVED    – computed from other columns (done in feature engineering).
      DEFERRED   – planned but not yet sourced; placeholder only.

Source-to-column mapping
------------------------
    Source          Columns populated
    ----------      -----------------------------------------------
    OpenAQ          pm25, pm10, o3, no2, so2, co, aqi_raw
    Open-Meteo      temperature, relative_humidity, wind_speed,
                    wind_direction, surface_pressure, precipitation,
                    solar_radiation, pbl_height,
                    temp_925hpa, temp_850hpa, temp_700hpa
    ERA5            Same weather columns as Open-Meteo (historical only)
    NASA FIRMS      fire_lat, fire_lon, fire_frp, fire_confidence
                    (raw fire points — aggregated to fire_count_300km,
                     fire_count_500km, total_frp_300km in the pipeline)
    GADM            Static geographic reference — not added to this table.
    ----------      -----------------------------------------------
    DERIVED later:  inversion_flag, inversion_strength, wind_transport_idx,
                    mixing_volume_idx, aqi_computed
    DEFERRED:       fire_count_300km, fire_count_500km, total_frp_300km
                    (spatial join not yet implemented)
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Column metadata record
# ---------------------------------------------------------------------------

@dataclass
class ColumnSpec:
    """Metadata for a single column in the master schema."""
    name: str
    dtype: str          # pandas dtype string, e.g. "Float64", "string", "datetime64[ns, UTC]"
    unit: str           # physical unit or empty string
    source: str         # which fetcher populates this
    category: str       # OBSERVED | DERIVED | DEFERRED
    nullable: bool      # False only for join-key columns
    valid_min: Optional[float] = None   # physical lower bound (None = no check)
    valid_max: Optional[float] = None   # physical upper bound (None = no check)
    description: str = ""


# ---------------------------------------------------------------------------
# The full master schema
# ---------------------------------------------------------------------------

MASTER_SCHEMA: list[ColumnSpec] = [

    # ── Join keys ──────────────────────────────────────────────────────────
    ColumnSpec("timestamp_utc",   "datetime64[ns, UTC]", "",    "all",       "OBSERVED", nullable=False,
               description="UTC timestamp of the observation, hourly-truncated"),
    ColumnSpec("station_id",      "string",              "",    "openaq",    "OBSERVED", nullable=False,
               description="Unique station identifier (CPCB / OpenAQ location ID)"),
    ColumnSpec("station_name",    "string",              "",    "openaq",    "OBSERVED", nullable=True,
               description="Human-readable station name, e.g. 'Anand Vihar'"),
    ColumnSpec("latitude",        "Float64",             "°N",  "openaq",    "OBSERVED", nullable=False,
               valid_min=23.0, valid_max=32.0,
               description="Station latitude (WGS-84, decimal degrees)"),
    ColumnSpec("longitude",       "Float64",             "°E",  "openaq",    "OBSERVED", nullable=False,
               valid_min=73.0, valid_max=80.0,
               description="Station longitude (WGS-84, decimal degrees)"),
    ColumnSpec("data_source",     "string",              "",    "all",       "OBSERVED", nullable=False,
               description="Name of the fetcher that produced this row"),

    # ── Air quality — OBSERVED (OpenAQ / CPCB) ────────────────────────────
    ColumnSpec("pm25",            "Float64", "µg/m³",  "openaq",    "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=2000.0,
               description="PM2.5 mass concentration"),
    ColumnSpec("pm10",            "Float64", "µg/m³",  "openaq",    "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=3000.0,
               description="PM10 mass concentration"),
    ColumnSpec("o3",              "Float64", "µg/m³",  "openaq",    "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=600.0,
               description="Ozone concentration"),
    ColumnSpec("no2",             "Float64", "µg/m³",  "openaq",    "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=3000.0,
               description="Nitrogen dioxide concentration"),
    ColumnSpec("so2",             "Float64", "µg/m³",  "openaq",    "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=2000.0,
               description="Sulphur dioxide concentration"),
    ColumnSpec("co",              "Float64", "mg/m³",  "openaq",    "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=100.0,
               description="Carbon monoxide concentration"),
    ColumnSpec("aqi_raw",         "Float64", "",       "openaq",    "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=500.0,
               description="AQI as reported directly by the data source (not recomputed)"),

    # ── Weather — OBSERVED (Open-Meteo / ERA5) ────────────────────────────
    ColumnSpec("temperature",     "Float64", "°C",     "openmeteo", "OBSERVED", nullable=True,
               valid_min=-10.0, valid_max=55.0,
               description="Air temperature at 2 m above ground"),
    ColumnSpec("relative_humidity","Float64","% ",     "openmeteo", "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=100.0,
               description="Relative humidity at 2 m"),
    ColumnSpec("wind_speed",      "Float64", "m/s",    "openmeteo", "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=80.0,
               description="Wind speed at 10 m above ground"),
    ColumnSpec("wind_direction",  "Float64", "°",      "openmeteo", "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=360.0,
               description="Wind direction at 10 m (meteorological convention, 0 = from N)"),
    ColumnSpec("surface_pressure","Float64", "hPa",    "openmeteo", "OBSERVED", nullable=True,
               valid_min=850.0, valid_max=1060.0,
               description="Mean sea-level pressure"),
    ColumnSpec("precipitation",   "Float64", "mm/hr",  "openmeteo", "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=300.0,
               description="Hourly precipitation amount"),
    ColumnSpec("solar_radiation", "Float64", "W/m²",   "openmeteo", "OBSERVED", nullable=True,
               valid_min=0.0, valid_max=1400.0,
               description="Downward shortwave solar radiation at surface"),
    ColumnSpec("pbl_height",      "Float64", "m",      "openmeteo", "OBSERVED", nullable=True,
               valid_min=10.0, valid_max=5000.0,
               description="Planetary Boundary Layer height from ECMWF model"),

    # ── Atmospheric profile — OBSERVED (Open-Meteo pressure levels / ERA5) ─
    ColumnSpec("temp_925hpa",     "Float64", "°C",     "openmeteo", "OBSERVED", nullable=True,
               valid_min=-30.0, valid_max=50.0,
               description="Air temperature at 925 hPa pressure level (~750 m)"),
    ColumnSpec("temp_850hpa",     "Float64", "°C",     "openmeteo", "OBSERVED", nullable=True,
               valid_min=-30.0, valid_max=45.0,
               description="Air temperature at 850 hPa pressure level (~1500 m)"),
    ColumnSpec("temp_700hpa",     "Float64", "°C",     "openmeteo", "OBSERVED", nullable=True,
               valid_min=-40.0, valid_max=35.0,
               description="Air temperature at 700 hPa pressure level (~3000 m)"),

    # ── Fire — aggregated from FIRMS (DEFERRED: spatial join not yet done) ─
    ColumnSpec("fire_count_300km","Float64", "count",  "firms",     "DEFERRED", nullable=True,
               valid_min=0.0,
               description="Number of active fire detections within 300 km of station "
                            "[populated by pipeline spatial join, not directly by fetcher]"),
    ColumnSpec("fire_count_500km","Float64", "count",  "firms",     "DEFERRED", nullable=True,
               valid_min=0.0,
               description="Number of active fire detections within 500 km of station"),
    ColumnSpec("total_frp_300km", "Float64", "MW",     "firms",     "DEFERRED", nullable=True,
               valid_min=0.0,
               description="Total Fire Radiative Power within 300 km of station (MW)"),

    # ── Derived features (computed in feature engineering, Phase 4) ────────
    ColumnSpec("inversion_flag",       "boolean",  "",    "derived", "DERIVED", nullable=True,
               description="True when temp_850hpa > temp at surface + threshold "
                            "(indicates temperature inversion trapping pollution)"),
    ColumnSpec("inversion_strength",   "Float64",  "°C", "derived", "DERIVED", nullable=True,
               description="temp_850hpa − temperature (positive = inversion present)"),
    ColumnSpec("wind_transport_idx",   "Float64",  "",   "derived", "DERIVED", nullable=True,
               description="Composite score: fire FRP × NW wind alignment "
                            "(high = smoke likely transported toward Delhi)"),
    ColumnSpec("mixing_volume_idx",    "Float64",  "",   "derived", "DERIVED", nullable=True,
               description="pbl_height × wind_speed — proxy for atmospheric ventilation"),
    ColumnSpec("aqi_computed",         "Float64",  "",   "derived", "DERIVED", nullable=True,
               valid_min=0.0, valid_max=500.0,
               description="AQI computed from CPCB formula using pm25 and pm10 "
                            "(replaces aqi_raw when aqi_raw is absent)"),
]


# ---------------------------------------------------------------------------
# Helper: ordered column name list
# ---------------------------------------------------------------------------

COLUMN_NAMES: list[str] = [c.name for c in MASTER_SCHEMA]

# Quick lookup: name → ColumnSpec
SCHEMA_LOOKUP: dict[str, ColumnSpec] = {c.name: c for c in MASTER_SCHEMA}

# Columns that every row MUST have (non-nullable join keys)
REQUIRED_COLUMNS: list[str] = [c.name for c in MASTER_SCHEMA if not c.nullable]


# ---------------------------------------------------------------------------
# Helper: build an empty DataFrame with correct dtypes
# ---------------------------------------------------------------------------

def empty_master_dataframe() -> pd.DataFrame:
    """
    Return a zero-row DataFrame whose column names and dtypes
    exactly match the master schema.  Use this as the starting
    point inside each fetcher's normalise() method.

    Example
    -------
    >>> df = empty_master_dataframe()
    >>> df.dtypes["pm25"]
    Float64Dtype()
    """
    dtype_map = {c.name: c.dtype for c in MASTER_SCHEMA}
    df = pd.DataFrame(columns=COLUMN_NAMES)
    for col, dtype in dtype_map.items():
        try:
            df[col] = df[col].astype(dtype)
        except TypeError:
            # boolean and some nullable types need special handling on empty frames
            pass
    return df


# ---------------------------------------------------------------------------
# Helper: print a human-readable schema summary (useful during development)
# ---------------------------------------------------------------------------

def print_schema_summary() -> None:
    """Print a formatted table of all schema columns to stdout."""
    header = f"{'Column':<26} {'DType':<26} {'Unit':<8} {'Category':<10} {'Source':<12} {'Nullable'}"
    print(header)
    print("-" * len(header))
    for c in MASTER_SCHEMA:
        print(
            f"{c.name:<26} {c.dtype:<26} {c.unit:<8} "
            f"{c.category:<10} {c.source:<12} {str(c.nullable)}"
        )


if __name__ == "__main__":
    print_schema_summary()
