"""
src/api/schemas.py
==================
Pydantic response models for all AeroAQI API endpoints.

Design rules
------------
- Every field that may be missing from the DB is Optional with a None default.
- Timestamps are returned as ISO 8601 strings (UTC) so JSON clients don't
  need to parse datetime objects.
- All numeric pollution / weather values use float | None — never default to 0.
- Field descriptions are included so the auto-generated OpenAPI docs are
  self-explanatory.
- A thin `from_db_row()` class-method is provided on models that are built
  from a pandas DataFrame row so routers stay clean.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class _Base(BaseModel):
    model_config = ConfigDict(
        # Allow extra fields from DB rows to be silently ignored
        extra="ignore",
        # Coerce numeric strings to float where needed
        coerce_numbers_to_str=False,
    )


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------

class HealthResponse(_Base):
    status: str = Field(..., description="'ok' when the API is running")
    version: str = Field(..., description="Application version string")
    database: str = Field(..., description="'connected' or an error message")
    observations_count: int = Field(..., description="Total rows in observations table")
    fire_detections_count: int = Field(..., description="Total rows in fire_detections table")
    last_ingestion_run: Optional[str] = Field(
        None, description="ISO timestamp of the most recent ingestion run (UTC)"
    )
    last_ingestion_status: Optional[str] = Field(
        None, description="Status of the most recent ingestion run"
    )


# ---------------------------------------------------------------------------
# Station
# ---------------------------------------------------------------------------

class StationResponse(_Base):
    station_id: str = Field(..., description="Unique internal station ID")
    name: str = Field(..., description="Official station name")
    city: str = Field(..., description="City within Delhi NCR")
    state: str = Field(..., description="Indian state")
    latitude: float = Field(..., description="Decimal degrees N (WGS-84)")
    longitude: float = Field(..., description="Decimal degrees E (WGS-84)")
    agency: str = Field(..., description="Operating agency (DPCC / UPPCB / HSPCB)")
    zone: str = Field(..., description="Directional zone within NCR")
    active: bool = Field(..., description="Whether the station is currently operational")
    openaq_id: Optional[int] = Field(None, description="OpenAQ v3 location ID")


class StationsListResponse(_Base):
    count: int
    stations: list[StationResponse]


# ---------------------------------------------------------------------------
# Air Quality Observation
# ---------------------------------------------------------------------------

class AQIObservation(_Base):
    timestamp_utc: Optional[str] = Field(None, description="UTC timestamp (ISO 8601)")
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    data_source: Optional[str] = None

    # Pollutants
    pm25: Optional[float] = Field(None, description="PM2.5 concentration (µg/m³)")
    pm10: Optional[float] = Field(None, description="PM10 concentration (µg/m³)")
    o3: Optional[float] = Field(None, description="Ozone (µg/m³)")
    no2: Optional[float] = Field(None, description="NO₂ (µg/m³)")
    so2: Optional[float] = Field(None, description="SO₂ (µg/m³)")
    co: Optional[float] = Field(None, description="CO (mg/m³)")
    aqi_raw: Optional[float] = Field(None, description="AQI reported by source")
    aqi_computed: Optional[float] = Field(
        None, description="AQI computed from CPCB sub-index formula"
    )

    @classmethod
    def from_db_row(cls, row: dict) -> "AQIObservation":
        ts = row.get("timestamp_utc")
        if ts is not None and hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        return cls(
            timestamp_utc=str(ts) if ts is not None else None,
            **{k: (None if _is_nan(v) else v) for k, v in row.items()
               if k != "timestamp_utc"},
        )


class ObservationsResponse(_Base):
    count: int
    station_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    observations: list[AQIObservation]


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

class WeatherObservation(_Base):
    timestamp_utc: Optional[str] = None
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    temperature: Optional[float] = Field(None, description="Air temperature at 2 m (°C)")
    relative_humidity: Optional[float] = Field(None, description="Relative humidity (%)")
    wind_speed: Optional[float] = Field(None, description="Wind speed at 10 m (m/s)")
    wind_direction: Optional[float] = Field(None, description="Wind direction (°, meteorological)")
    surface_pressure: Optional[float] = Field(None, description="Surface pressure (hPa)")
    precipitation: Optional[float] = Field(None, description="Hourly precipitation (mm/hr)")
    solar_radiation: Optional[float] = Field(None, description="Shortwave radiation (W/m²)")
    pbl_height: Optional[float] = Field(None, description="Planetary Boundary Layer height (m)")

    # Atmospheric profile
    temp_925hpa: Optional[float] = Field(None, description="Temperature at 925 hPa (~750 m) (°C)")
    temp_850hpa: Optional[float] = Field(None, description="Temperature at 850 hPa (~1500 m) (°C)")
    temp_700hpa: Optional[float] = Field(None, description="Temperature at 700 hPa (~3000 m) (°C)")

    # Derived atmospheric
    inversion_flag: Optional[bool] = Field(
        None, description="True when a temperature inversion is detected"
    )
    inversion_strength: Optional[float] = Field(
        None, description="Inversion strength: temp_850hpa − surface temp (°C)"
    )
    temperature_profile: Optional[dict] = Field(
        None, description="Vertical temperature profile {pressure_hPa: temp_C}"
    )
    mixing_volume_idx: Optional[float] = Field(
        None, description="PBL height × wind speed — ventilation proxy (m²/s)"
    )

    @classmethod
    def from_db_row(cls, row: dict) -> "WeatherObservation":
        ts = row.get("timestamp_utc")
        if ts is not None and hasattr(ts, "isoformat"):
            ts = ts.isoformat()

        # Parse temperature_profile JSON string → dict
        tp = row.get("temperature_profile")
        if isinstance(tp, str):
            try:
                tp = json.loads(tp)
            except Exception:
                tp = None

        inv_flag = row.get("inversion_flag")
        if inv_flag is not None and not isinstance(inv_flag, bool):
            inv_flag = bool(inv_flag)

        return cls(
            timestamp_utc=str(ts) if ts is not None else None,
            station_id=row.get("station_id"),
            station_name=row.get("station_name"),
            latitude=_clean(row.get("latitude")),
            longitude=_clean(row.get("longitude")),
            temperature=_clean(row.get("temperature")),
            relative_humidity=_clean(row.get("relative_humidity")),
            wind_speed=_clean(row.get("wind_speed")),
            wind_direction=_clean(row.get("wind_direction")),
            surface_pressure=_clean(row.get("surface_pressure")),
            precipitation=_clean(row.get("precipitation")),
            solar_radiation=_clean(row.get("solar_radiation")),
            pbl_height=_clean(row.get("pbl_height")),
            temp_925hpa=_clean(row.get("temp_925hpa")),
            temp_850hpa=_clean(row.get("temp_850hpa")),
            temp_700hpa=_clean(row.get("temp_700hpa")),
            inversion_flag=inv_flag,
            inversion_strength=_clean(row.get("inversion_strength")),
            temperature_profile=tp,
            mixing_volume_idx=_clean(row.get("mixing_volume_idx")),
        )


class WeatherResponse(_Base):
    count: int
    station_id: Optional[str] = None
    observations: list[WeatherObservation]


# ---------------------------------------------------------------------------
# Fire / Hotspot
# ---------------------------------------------------------------------------

class FireDetectionRecord(_Base):
    timestamp_utc: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    frp: Optional[float] = Field(None, description="Fire Radiative Power (MW)")
    confidence: Optional[str] = Field(None, description="Detection confidence: low/nominal/high")
    satellite: Optional[str] = None
    bright_ti4: Optional[float] = Field(None, description="Brightness temperature (K)")
    daynight: Optional[str] = Field(None, description="'D' (day) or 'N' (night)")

    @classmethod
    def from_db_row(cls, row: dict) -> "FireDetectionRecord":
        ts = row.get("timestamp_utc")
        if ts is not None and hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        return cls(
            timestamp_utc=str(ts) if ts is not None else None,
            latitude=_clean(row.get("latitude")),
            longitude=_clean(row.get("longitude")),
            frp=_clean(row.get("frp")),
            confidence=row.get("confidence"),
            satellite=row.get("satellite"),
            bright_ti4=_clean(row.get("bright_ti4")),
            daynight=row.get("daynight"),
        )


class FireRiskRecord(_Base):
    timestamp_utc: Optional[str] = None
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    fire_count_300km: Optional[float] = Field(
        None, description="Number of active fires within 300 km"
    )
    fire_count_500km: Optional[float] = Field(
        None, description="Number of active fires within 500 km"
    )
    total_frp_300km: Optional[float] = Field(
        None, description="Total Fire Radiative Power within 300 km (MW)"
    )
    fire_distance_km: Optional[float] = Field(
        None, description="Distance to nearest active fire (km)"
    )
    fire_nearest_frp: Optional[float] = Field(
        None, description="FRP of nearest active fire (MW)"
    )
    fire_transport_risk: Optional[float] = Field(
        None, description="Composite fire transport risk score [0-1]"
    )
    wind_transport_idx: Optional[float] = Field(
        None, description="NW wind alignment score [0-1]"
    )

    @classmethod
    def from_db_row(cls, row: dict) -> "FireRiskRecord":
        ts = row.get("timestamp_utc")
        if ts is not None and hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        return cls(
            timestamp_utc=str(ts) if ts is not None else None,
            station_id=row.get("station_id"),
            station_name=row.get("station_name"),
            fire_count_300km=_clean(row.get("fire_count_300km")),
            fire_count_500km=_clean(row.get("fire_count_500km")),
            total_frp_300km=_clean(row.get("total_frp_300km")),
            fire_distance_km=_clean(row.get("fire_distance_km")),
            fire_nearest_frp=_clean(row.get("fire_nearest_frp")),
            fire_transport_risk=_clean(row.get("fire_transport_risk")),
            wind_transport_idx=_clean(row.get("wind_transport_idx")),
        )


class FireDetectionsResponse(_Base):
    count: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    detections: list[FireDetectionRecord]


class FireRiskResponse(_Base):
    count: int
    station_id: Optional[str] = None
    records: list[FireRiskRecord]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class PipelineRunRequest(BaseModel):
    mode: str = Field(
        "realtime",
        description="'realtime' (default) or 'historical'",
    )
    start_date: Optional[str] = Field(
        None, description="ISO date 'YYYY-MM-DD' — required for historical mode"
    )
    end_date: Optional[str] = Field(
        None, description="ISO date 'YYYY-MM-DD' — required for historical mode"
    )
    skip_sources: list[str] = Field(
        default_factory=list,
        description="Source names to skip: openaq, openmeteo, era5, firms, gadm",
    )
    skip_processing: bool = Field(
        False,
        description="If True, skip Phase 4 feature engineering after ingestion",
    )


class PipelineSourceResult(BaseModel):
    source_name: str
    status: str
    rows_written: int = 0
    duration_sec: float = 0.0
    error_message: Optional[str] = None


class PipelineRunResponse(BaseModel):
    run_id: str = Field(..., description="Unique run identifier (timestamp-based)")
    mode: str
    status: str = Field(..., description="'completed' or 'failed'")
    total_duration_sec: float
    results: list[PipelineSourceResult]


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    detail: str
    status_code: int


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _is_nan(v: Any) -> bool:
    """Return True if v is a float NaN."""
    try:
        import math
        return isinstance(v, float) and math.isnan(v)
    except Exception:
        return False


def _clean(v: Any) -> Optional[float]:
    """Return None for NaN/None, otherwise return v as-is."""
    if v is None or _is_nan(v):
        return None
    return v


# ---------------------------------------------------------------------------
# Forecast (Phase 6)
# ---------------------------------------------------------------------------

class ForecastHour(_Base):
    """One row in a 72-hour forecast: predictions for a single future hour."""
    station_id:    Optional[str]   = None
    forecast_hour: int             = Field(..., description="1–72 hours ahead")
    target_utc:    Optional[str]   = Field(None, description="ISO 8601 UTC timestamp being forecast")
    pm25:          Optional[float] = Field(None, description="Predicted PM2.5 (µg/m³)")
    pm10:          Optional[float] = Field(None, description="Predicted PM10 (µg/m³)")
    o3:            Optional[float] = Field(None, description="Predicted O₃ (µg/m³)")
    no2:           Optional[float] = Field(None, description="Predicted NO₂ (µg/m³)")
    aqi_computed:  Optional[float] = Field(None, description="Predicted AQI (CPCB scale)")
    aqi_category:  Optional[str]   = Field(None, description="CPCB AQI category label")

    @classmethod
    def from_db_row(cls, row: dict) -> "ForecastHour":
        ts = row.get("target_utc")
        if ts is not None and hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        return cls(
            station_id=row.get("station_id"),
            forecast_hour=int(row.get("forecast_hour", 0)),
            target_utc=str(ts) if ts is not None else None,
            pm25=_clean(row.get("pm25")),
            pm10=_clean(row.get("pm10")),
            o3=_clean(row.get("o3")),
            no2=_clean(row.get("no2")),
            aqi_computed=_clean(row.get("aqi_computed")),
            aqi_category=row.get("aqi_category"),
        )


class ForecastResponse(_Base):
    """72-hour AQI forecast for one monitoring station."""
    station_id:    str
    generated_at:  Optional[str]       = Field(None, description="ISO 8601 UTC time this forecast was generated")
    model_version: Optional[str]       = None
    model_trained: bool                = Field(False, description="False when no model has been trained yet")
    count:         int                 = 0
    hourly:        list[ForecastHour]  = Field(default_factory=list)
    message:       Optional[str]       = Field(None, description="Informational message when model is not available")


class ExplanationFeature(_Base):
    """One feature's contribution to a forecast."""
    rank:             int
    name:             str   = Field(..., description="Internal feature column name")
    label:            str   = Field(..., description="Human-readable feature label")
    shap_value:       float = Field(..., description="Mean absolute SHAP value")
    contribution_pct: float = Field(..., description="Percentage of total SHAP importance")


class ForecastExplanationResponse(_Base):
    """SHAP explanation for the most recent forecast at one station."""
    station_id:         str
    target:             str   = Field(..., description="Target pollutant, e.g. 'pm25'")
    horizon_hours:      int   = Field(..., description="Number of forecast hours explained")
    top_features:       list[ExplanationFeature] = Field(default_factory=list)
    explanation_text:   str   = ""
    inversion_detected: bool  = False
    shap_available:     bool  = False
    message:            Optional[str] = None
