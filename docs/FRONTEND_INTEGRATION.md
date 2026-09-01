# AeroAQI — Frontend Integration Guide

**API version:** 0.6.0  
**Base URL (development):** `http://127.0.0.1:8000`  
**Interactive docs:** `http://127.0.0.1:8000/docs` (Swagger UI)  
**ReDoc:** `http://127.0.0.1:8000/redoc`

---

## 1. Quick Start

```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env — fill in API keys and add your frontend origin to ALLOWED_ORIGINS

# 2. Start the backend
python scripts/run_api.py

# 3. (Optional) Populate with live data
python scripts/run_ingestion.py --mode realtime

# 4. (Optional) Train the forecast model
python scripts/train_model.py
```

---

## 2. Environment Variables (server-side `.env`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENAQ_API_KEY` | For live data | — | OpenAQ v3 API — register free at openaq.org |
| `FIRMS_MAP_KEY` | For live data | — | NASA FIRMS fire data — register free at firms.modaps.eosdis.nasa.gov |
| `CDS_API_KEY` | ERA5 only | — | Copernicus CDS — register free at cds.climate.copernicus.eu |
| `ALLOWED_ORIGINS` | Production | `localhost:3000,5173` | Comma-separated list of frontend origins for CORS |
| `DATABASE_URL` | Optional | `sqlite:///data/db/aeroaqi.db` | SQLAlchemy DB URL |
| `LOG_LEVEL` | Optional | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

**For local development, no API keys are needed.** The server starts and all endpoints return empty arrays gracefully.

---

## 3. CORS

CORS is configured for `http://localhost:3000` and `http://localhost:5173` by default.

To add your deployed frontend:

```bash
# In .env
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,https://your-app.example.com
```

**Allowed headers:** `Content-Type`, `Authorization`, `Accept`, `X-Requested-With`  
**Credentials:** not required — do not send `credentials: 'include'` from the frontend.

---

## 4. Common Response Patterns

### Success

All list endpoints return `count` + a named array:

```json
{
  "count": 3,
  "observations": [...],   // or "stations", "records", "detections", "hourly", "runs"
  "start_time": "2026-09-01T06:00:00+00:00",
  "end_time":   "2026-09-01T10:00:00+00:00"
}
```

### Missing values

Numeric fields that have no measurement are `null`, never `0`:

```json
{ "pm25": null, "pm10": 142.1, "o3": null }
```

### Timestamps

All timestamps in responses are **ISO 8601 UTC strings**:

```
"2026-09-01T08:00:00+00:00"
```

Parse with `new Date(ts)` in JavaScript — browsers handle `+00:00` correctly.

### Errors

| HTTP | Body shape | When |
|---|---|---|
| 404 | `{"detail": "Station 'X' not found. ..."}` | Unknown station ID |
| 422 | `{"detail": [{"loc":..., "msg":..., "type":...}]}` | Invalid query parameter |
| 422 | `{"detail": "start_time must be earlier than end_time."}` | Bad time range |
| 503 | `{"detail": "Database not reachable: ..."}` | DB unavailable (`GET /health/status` only) |
| 500 | `{"detail": "An internal server error occurred.", "status_code": 500}` | Unhandled server error |

---

## 5. All Endpoints

### Health

#### `GET /health`
Liveness probe — always 200 if the server is running.

```http
GET http://127.0.0.1:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "version": "0.6.0",
  "database": "connected",
  "observations_count": 1024,
  "fire_detections_count": 87,
  "last_ingestion_run": "2026-09-01T08:30:00+00:00",
  "last_ingestion_status": "success"
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | `"ok"` | Always `"ok"` — HTTP 200 regardless |
| `database` | string | `"connected"` or an error string |
| `observations_count` | int | Rows in the observations table |
| `last_ingestion_run` | string \| null | ISO 8601 UTC |
| `last_ingestion_status` | string \| null | `success` / `failed` / `skipped` |

#### `GET /health/status`
Readiness probe — returns 503 if DB is unreachable.

---

### Stations

#### `GET /stations`
List all 15 Delhi NCR monitoring stations (from config, always fast).

```http
GET http://127.0.0.1:8000/stations
```

**Response:**
```json
{
  "count": 15,
  "stations": [
    {
      "station_id": "DEL_ITO",
      "name": "ITO",
      "city": "Delhi",
      "state": "Delhi",
      "latitude": 28.6289,
      "longitude": 77.2412,
      "agency": "DPCC",
      "zone": "central",
      "active": true,
      "openaq_id": 8119
    }
  ]
}
```

#### `GET /stations/{station_id}`
Single station by ID. Returns 404 if not found.

```http
GET http://127.0.0.1:8000/stations/DEL_ITO
GET http://127.0.0.1:8000/stations/DEL_ANAND_VIHAR
```

**Valid station IDs:**
`DEL_ANAND_VIHAR`, `DEL_ITO`, `DEL_PUNJABI_BAGH`, `DEL_DWARKA_S8`, `DEL_RK_PURAM`,
`DEL_ROHINI`, `DEL_MUNDKA`, `DEL_OKHLA_PH2`, `DEL_NEHRU_NAGAR`, `DEL_DTU`,
`NOI_SECTOR62`, `NOI_SECTOR1`, `GGN_VIKAS_SADAN`, `FBD_SECTOR16A`, `GZB_VASUNDHARA`

---

### Air Quality Observations

#### `GET /observations`
Hourly AQ readings with optional filters.

```http
GET /observations?hours=24
GET /observations?station_id=DEL_ITO&hours=48
GET /observations?station_id=DEL_ITO&start_time=2026-09-01T00:00:00&end_time=2026-09-01T23:59:59
GET /observations?station_id=DEL_ITO&limit=100
```

**Query parameters:**

| Param | Type | Default | Range | Notes |
|---|---|---|---|---|
| `station_id` | string | all stations | — | e.g. `DEL_ITO` |
| `hours` | int | 24 | 1–720 | Look-back window when `start_time` is omitted |
| `start_time` | ISO string | now − `hours` | — | UTC, e.g. `2026-09-01T00:00:00` |
| `end_time` | ISO string | now | — | UTC |
| `limit` | int | 200 | 1–1000 | Max rows returned |

**Response:**
```json
{
  "count": 3,
  "station_id": "DEL_ITO",
  "start_time": "2026-09-01T06:00:00+00:00",
  "end_time": "2026-09-01T10:00:00+00:00",
  "observations": [
    {
      "timestamp_utc": "2026-09-01T07:00:00+00:00",
      "station_id": "DEL_ITO",
      "station_name": "ITO",
      "latitude": 28.6289,
      "longitude": 77.2412,
      "data_source": "openaq",
      "pm25": 87.3,
      "pm10": 142.1,
      "o3": 45.2,
      "no2": 35.0,
      "so2": 12.0,
      "co": 1.2,
      "aqi_raw": null,
      "aqi_computed": 110.4
    }
  ]
}
```

#### `GET /observations/latest`
Most recent AQ reading per station (last 48 h). Use for live AQI map.

```http
GET /observations/latest
```

Returns one row per station that has recent data.

#### `GET /observations/{station_id}`
AQ history for one station.

```http
GET /observations/DEL_ITO?hours=72
GET /observations/DEL_ITO?start_time=2026-09-01T00:00:00&end_time=2026-09-01T23:59:59
```

Returns 404 if `station_id` is not in the known station list.

---

### Weather

#### `GET /weather`
Hourly weather + atmospheric profile.

```http
GET /weather?hours=24
GET /weather?station_id=DEL_ITO&hours=48
```

Same query parameters as `/observations`.

**Response per observation:**
```json
{
  "timestamp_utc": "2026-09-01T07:00:00+00:00",
  "station_id": "DEL_ITO",
  "temperature": 28.5,
  "relative_humidity": 64.0,
  "wind_speed": 3.2,
  "wind_direction": 315.0,
  "surface_pressure": 995.0,
  "precipitation": 0.0,
  "solar_radiation": 650.0,
  "pbl_height": 480.0,
  "temp_925hpa": 26.3,
  "temp_850hpa": 22.1,
  "temp_700hpa": 14.5,
  "inversion_flag": false,
  "inversion_strength": -6.4,
  "temperature_profile": {"1013": 28.5, "925": 26.3, "850": 22.1, "700": 14.5},
  "mixing_volume_idx": 1536.0
}
```

| Field | Unit | Notes |
|---|---|---|
| `temperature` | °C | 2 m above ground |
| `wind_direction` | ° | Meteorological: 0° = from North, 315° = from NW |
| `pbl_height` | m | Planetary Boundary Layer — lower = pollution trapped |
| `inversion_flag` | bool | `true` when 850 hPa temp > surface + 2°C |
| `inversion_strength` | °C | Positive = inversion; larger = stronger lid |
| `temperature_profile` | dict | `{pressure_hPa: temp_C}` — JSON object |
| `mixing_volume_idx` | m²/s | `pbl_height × wind_speed` — higher = better dispersion |

#### `GET /weather/latest`
Most recent weather reading per station.

#### `GET /weather/{station_id}`
Weather history for one station. Same params as above.

---

### Fire / Hotspots

#### `GET /fire/detections`
Raw NASA FIRMS VIIRS fire detections.

```http
GET /fire/detections?hours=48
GET /fire/detections?hours=48&min_confidence=nominal
GET /fire/detections?start_time=2026-09-01T00:00:00&end_time=2026-09-01T23:59:59
```

**Query parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `hours` | int | 48 | 1–720 |
| `start_time` | ISO string | now − `hours` | UTC |
| `end_time` | ISO string | now | UTC |
| `min_confidence` | string | none | `low` / `nominal` / `high` |
| `limit` | int | 500 | 1–2000 |

**Response:**
```json
{
  "count": 2,
  "start_time": "2026-08-30T10:00:00+00:00",
  "end_time":   "2026-09-01T10:00:00+00:00",
  "detections": [
    {
      "timestamp_utc": "2026-09-01T01:30:00+00:00",
      "latitude": 30.74,
      "longitude": 76.79,
      "frp": 25.0,
      "confidence": "nominal",
      "satellite": "N",
      "bright_ti4": 320.5,
      "daynight": "D"
    }
  ]
}
```

> Fire detections covering the Punjab/Haryana/Delhi bounding box (73°E–80°E, 27.5°N–33°N).

#### `GET /fire/risk`
Per-station fire transport risk derived features.

```http
GET /fire/risk?hours=48
GET /fire/risk?station_id=DEL_ITO&hours=48
```

**Response per record:**
```json
{
  "timestamp_utc": "2026-09-01T07:00:00+00:00",
  "station_id": "DEL_ITO",
  "station_name": "Del Ito",
  "fire_count_300km": 3.0,
  "fire_count_500km": 7.0,
  "total_frp_300km": 85.5,
  "fire_distance_km": 245.3,
  "fire_nearest_frp": 25.0,
  "fire_transport_risk": 0.72,
  "wind_transport_idx": 0.85
}
```

| Field | Range | Notes |
|---|---|---|
| `fire_transport_risk` | 0–1 | Composite: fire proximity + FRP + NW wind alignment |
| `wind_transport_idx` | 0–1 | `1.0` = perfect NW flow from Punjab source region |

> These fields are `null` until the ingestion pipeline has run and fire aggregation is complete.

#### `GET /fire/risk/{station_id}`
Fire risk history for one station.

---

### Forecast (requires trained model)

> **Note:** All forecast endpoints return HTTP 200 with `model_trained: false` (or `shap_available: false`) when no model has been trained yet — they never return HTTP 500. Check these flags before rendering forecast UI.

#### `GET /forecast/{station_id}`
72-hour AQI and pollutant forecast.

```http
GET /forecast/DEL_ITO
GET /forecast/DEL_ITO?hours=24
```

**Query parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `hours` | int | 72 | 1–72 — how many future hours to return |

**Response (model trained):**
```json
{
  "station_id": "DEL_ITO",
  "generated_at": "2026-09-01T09:00:00+00:00",
  "model_version": "xgb_360models",
  "model_trained": true,
  "count": 72,
  "hourly": [
    {
      "forecast_hour": 1,
      "target_utc": "2026-09-01T10:00:00+00:00",
      "pm25": 92.4,
      "pm10": 148.6,
      "o3": 43.2,
      "no2": 38.7,
      "aqi_computed": 118.3,
      "aqi_category": "Moderate"
    }
  ],
  "message": null
}
```

**Response (no model trained):**
```json
{
  "station_id": "DEL_ITO",
  "generated_at": null,
  "model_version": null,
  "model_trained": false,
  "count": 0,
  "hourly": [],
  "message": "No forecast available. The model has not been trained yet..."
}
```

**AQI category values:**

| Category | AQI Range | Colour suggestion |
|---|---|---|
| `Good` | 0–50 | `#00b050` green |
| `Satisfactory` | 51–100 | `#92d050` yellow-green |
| `Moderate` | 101–200 | `#ffff00` yellow |
| `Poor` | 201–300 | `#ff9900` orange |
| `Very Poor` | 301–400 | `#ff0000` red |
| `Severe` | 401+ | `#c00000` dark red |

#### `GET /forecast/{station_id}/explain`
SHAP explanation for the most recent forecast.

```http
GET /forecast/DEL_ITO/explain
GET /forecast/DEL_ITO/explain?target=pm10
```

**Query parameters:**

| Param | Type | Default | Valid values |
|---|---|---|---|
| `target` | string | `pm25` | `pm25`, `pm10`, `o3`, `no2`, `aqi_computed` |

**Response (SHAP available):**
```json
{
  "station_id": "DEL_ITO",
  "target": "pm25",
  "horizon_hours": 24,
  "top_features": [
    {
      "rank": 1,
      "name": "pbl_height",
      "label": "Boundary layer height",
      "shap_value": 12.5,
      "contribution_pct": 38.0
    },
    {
      "rank": 2,
      "name": "wind_transport_idx",
      "label": "NW wind transport",
      "shap_value": 8.3,
      "contribution_pct": 25.0
    }
  ],
  "explanation_text": "PM2.5 forecast for the next 24 h is primarily driven by: Boundary layer height (38%), NW wind transport (25%), Stubble season (15%).",
  "inversion_detected": true,
  "shap_available": true,
  "message": null
}
```

**Response (no model):**
```json
{
  "station_id": "DEL_ITO",
  "target": "pm25",
  "horizon_hours": 24,
  "top_features": [],
  "explanation_text": "",
  "inversion_detected": false,
  "shap_available": false,
  "message": "No explanation available. Run the ingestion pipeline after training the model..."
}
```

---

### Pipeline

#### `POST /pipeline/run`
Trigger a full ingestion + forecast run. Returns HTTP 202 immediately; runs in background.

```http
POST /pipeline/run
Content-Type: application/json

{
  "mode": "realtime",
  "skip_sources": [],
  "skip_processing": false
}
```

**Request body:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `mode` | string | `"realtime"` | `"realtime"` or `"historical"` |
| `start_date` | string | null | Required for historical: `"YYYY-MM-DD"` |
| `end_date` | string | null | Required for historical: `"YYYY-MM-DD"` |
| `skip_sources` | string[] | `[]` | Sources to skip: `openaq`, `openmeteo`, `era5`, `firms`, `gadm` |
| `skip_processing` | bool | `false` | Skip Phase 4 feature engineering |

**Response (202 Accepted):**
```json
{
  "run_id": "run_20260901T093000Z_a1b2c3",
  "mode": "realtime",
  "status": "accepted",
  "total_duration_sec": 0.0,
  "results": []
}
```

> Use `GET /pipeline/runs` to check progress. The pipeline runs async; results appear in the audit table.

#### `GET /pipeline/runs`
List recent pipeline run audit records.

```http
GET /pipeline/runs
GET /pipeline/runs?n=50
```

**Query parameters:** `n` (int, 1–200, default 20)

**Response:**
```json
{
  "count": 7,
  "runs": [
    {
      "id": 42,
      "run_timestamp": "2026-09-01T09:30:00+00:00",
      "source_name": "openaq",
      "mode": "realtime",
      "status": "success",
      "rows_written": 240,
      "duration_sec": 4.2,
      "error_message": null
    }
  ]
}
```

| `status` value | Meaning |
|---|---|
| `success` | Fetched and stored data |
| `failed` | Error (check `error_message`) |
| `skipped` | Disabled in config or explicitly skipped |
| `no_data` | Source returned no rows |

---

## 6. Suggested Frontend Usage Patterns

### Live AQI Map

```javascript
// Fetch all stations + latest readings in parallel
const [stations, latest] = await Promise.all([
  fetch('/stations').then(r => r.json()),
  fetch('/observations/latest').then(r => r.json()),
]);

// Merge by station_id
const map = Object.fromEntries(
  latest.observations.map(o => [o.station_id, o])
);
stations.stations.forEach(s => {
  const obs = map[s.station_id];
  renderMarker(s.latitude, s.longitude, obs?.aqi_computed, obs?.pm25);
});
```

### Station Detail Page

```javascript
const stationId = 'DEL_ITO';

// Fetch last 48 h of AQ + weather + fire risk + 72-h forecast in parallel
const [aq, wx, fire, forecast] = await Promise.all([
  fetch(`/observations/${stationId}?hours=48`).then(r => r.json()),
  fetch(`/weather/${stationId}?hours=48`).then(r => r.json()),
  fetch(`/fire/risk/${stationId}?hours=48`).then(r => r.json()),
  fetch(`/forecast/${stationId}`).then(r => r.json()),
]);

// Check if forecast is available
if (!forecast.model_trained) {
  showMessage(forecast.message);   // "No forecast available..."
} else {
  renderForecastChart(forecast.hourly);
}
```

### Forecast Explainability Panel

```javascript
const explain = await fetch(`/forecast/${stationId}/explain?target=pm25`)
  .then(r => r.json());

if (explain.shap_available) {
  renderExplanationBar(explain.top_features);
  renderText(explain.explanation_text);
  if (explain.inversion_detected) {
    showAlert("Temperature inversion detected — pollution trapped near surface");
  }
}
```

### Health Check for Status Bar

```javascript
const health = await fetch('/health').then(r => r.json());
const isHealthy = health.database === 'connected';
const lastRun = health.last_ingestion_run
  ? new Date(health.last_ingestion_run)
  : null;
```

---

## 7. TypeScript Types (reference)

```typescript
// Core types — derived from Pydantic schemas

export interface Station {
  station_id: string;
  name: string;
  city: string;
  state: string;
  latitude: number;
  longitude: number;
  agency: string;
  zone: string;
  active: boolean;
  openaq_id: number | null;
}

export interface AQIObservation {
  timestamp_utc: string | null;
  station_id: string | null;
  station_name: string | null;
  latitude: number | null;
  longitude: number | null;
  data_source: string | null;
  pm25: number | null;
  pm10: number | null;
  o3: number | null;
  no2: number | null;
  so2: number | null;
  co: number | null;
  aqi_raw: number | null;
  aqi_computed: number | null;
}

export interface WeatherObservation {
  timestamp_utc: string | null;
  station_id: string | null;
  temperature: number | null;
  relative_humidity: number | null;
  wind_speed: number | null;
  wind_direction: number | null;
  surface_pressure: number | null;
  precipitation: number | null;
  solar_radiation: number | null;
  pbl_height: number | null;
  temp_925hpa: number | null;
  temp_850hpa: number | null;
  temp_700hpa: number | null;
  inversion_flag: boolean | null;
  inversion_strength: number | null;
  temperature_profile: Record<string, number> | null;
  mixing_volume_idx: number | null;
}

export type AQICategory =
  | 'Good' | 'Satisfactory' | 'Moderate'
  | 'Poor' | 'Very Poor' | 'Severe' | 'Unknown';

export interface ForecastHour {
  forecast_hour: number;             // 1–72
  target_utc: string | null;
  pm25: number | null;
  pm10: number | null;
  o3: number | null;
  no2: number | null;
  aqi_computed: number | null;
  aqi_category: AQICategory | null;
}

export interface ForecastResponse {
  station_id: string;
  generated_at: string | null;
  model_version: string | null;
  model_trained: boolean;            // false = no model yet
  count: number;
  hourly: ForecastHour[];
  message: string | null;
}

export interface ExplanationFeature {
  rank: number;
  name: string;
  label: string;
  shap_value: number;
  contribution_pct: number;
}

export interface ForecastExplanationResponse {
  station_id: string;
  target: string;
  horizon_hours: number;
  top_features: ExplanationFeature[];
  explanation_text: string;
  inversion_detected: boolean;
  shap_available: boolean;           // false = no SHAP data yet
  message: string | null;
}

export interface FireDetection {
  timestamp_utc: string | null;
  latitude: number | null;
  longitude: number | null;
  frp: number | null;
  confidence: string | null;
  satellite: string | null;
  daynight: 'D' | 'N' | null;
}

export interface FireRiskRecord {
  timestamp_utc: string | null;
  station_id: string | null;
  fire_count_300km: number | null;
  fire_count_500km: number | null;
  total_frp_300km: number | null;
  fire_distance_km: number | null;
  fire_nearest_frp: number | null;
  fire_transport_risk: number | null;  // 0–1
  wind_transport_idx: number | null;   // 0–1
}

export interface HealthResponse {
  status: 'ok';
  version: string;
  database: string;
  observations_count: number;
  fire_detections_count: number;
  last_ingestion_run: string | null;
  last_ingestion_status: string | null;
}

export interface PipelineRunRecord {
  id: number | null;
  run_timestamp: string | null;
  source_name: string | null;
  mode: 'realtime' | 'historical' | 'static' | null;
  status: 'success' | 'failed' | 'skipped' | 'no_data' | null;
  rows_written: number;
  duration_sec: number | null;
  error_message: string | null;
}
```

---

## 8. Pagination Notes

The API uses a simple `limit` parameter (not cursor or offset pagination).

- `limit` controls the **maximum** number of rows returned.
- Rows are returned in **ascending timestamp order**, and the most recent `limit` rows are kept when the result exceeds the limit.
- There is no `offset`, `page`, or cursor parameter.
- For typical frontend use (charts, tables) the default `limit=200` and `hours=24` is sufficient.
- For historical analysis, increase `hours` (up to 720 = 30 days) and `limit` (up to 1000).

---

## 9. Seeding Data for Development (without API keys)

```bash
# Start API with empty DB — all endpoints return 200 with count=0
python scripts/run_api.py

# Optionally seed test data using the integration test helper
python -c "
from tests.integration.conftest import _seed
from src.storage.db_client import DBClient
db = DBClient()
# _seed(db)  # Seeds 6 obs rows + 3 fire rows (relative to now-3h..now-1h)
"
```

---

## 10. Running the Full Test Suite

```bash
python -m pytest tests/ -o "addopts=" -q
```

Expected: **426 passed** (232 unit + 194 integration).

To run only integration tests:
```bash
python -m pytest tests/integration/ -o "addopts=" -q
```
