"""
src/storage/db_client.py
=========================
Database layer for AeroAQI.

Responsibilities
----------------
1. Create and maintain the SQLite database (dev) or PostgreSQL (prod).
2. Provide typed write/read helpers for the three main tables:
     - observations  : master time-series (one row per station per hour)
     - fire_detections: raw FIRMS fire point records
     - ingestion_runs : audit log of every pipeline run
3. Upsert on (timestamp_utc, station_id) so re-running the pipeline
   does not create duplicates.

Why SQLite for development?
---------------------------
  No server to install.  The database is a single file at data/db/aeroaqi.db.
  When you are ready for production, change DATABASE_URL in .env to a
  PostgreSQL connection string — SQLAlchemy handles both transparently.

Usage
-----
    from src.storage.db_client import DBClient

    db = DBClient()
    db.write_observations(df)          # write master-schema rows
    db.write_fire_detections(df)       # write raw FIRMS rows
    db.log_run(source, status, rows)   # audit log
    df = db.read_observations(...)     # query back
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, create_engine, text, inspect as sa_inspect,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.utils.config_loader import get_project_root, load_settings
from src.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# SQLAlchemy ORM Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Table: observations
# One row = one hourly observation at one station.
# Primary key: (timestamp_utc, station_id, data_source)
# ---------------------------------------------------------------------------

class Observation(Base):
    __tablename__ = "observations"

    # Join key — composite primary key
    id              = Column(Integer, primary_key=True, autoincrement=True)
    timestamp_utc   = Column(DateTime(timezone=True), nullable=False, index=True)
    station_id      = Column(String(64), nullable=False, index=True)
    station_name    = Column(String(128))
    latitude        = Column(Float)
    longitude       = Column(Float)
    data_source     = Column(String(32), nullable=False)

    # Air quality (µg/m³ unless noted)
    pm25            = Column(Float)
    pm10            = Column(Float)
    o3              = Column(Float)
    no2             = Column(Float)
    so2             = Column(Float)
    co              = Column(Float)   # mg/m³
    aqi_raw         = Column(Float)

    # Weather
    temperature     = Column(Float)   # °C
    relative_humidity = Column(Float) # %
    wind_speed      = Column(Float)   # m/s
    wind_direction  = Column(Float)   # degrees
    surface_pressure = Column(Float)  # hPa
    precipitation   = Column(Float)   # mm/hr
    solar_radiation = Column(Float)   # W/m²
    pbl_height      = Column(Float)   # metres

    # Atmospheric profile
    temp_925hpa     = Column(Float)   # °C
    temp_850hpa     = Column(Float)   # °C
    temp_700hpa     = Column(Float)   # °C

    # Fire aggregates (populated by fire_aggregator.py spatial join — Phase 4)
    fire_count_300km    = Column(Float)
    fire_count_500km    = Column(Float)
    total_frp_300km     = Column(Float)
    fire_distance_km    = Column(Float)   # km to nearest active fire
    fire_nearest_frp    = Column(Float)   # FRP of nearest fire (MW)
    fire_transport_risk = Column(Float)   # normalised [0-1] composite risk score

    # Derived atmospheric features (populated by feature_engineer.py — Phase 4)
    inversion_flag        = Column(Boolean)
    inversion_strength    = Column(Float)
    temperature_profile   = Column(Text)    # JSON: {pressure_hPa: temp_C}
    wind_transport_idx    = Column(Float)
    mixing_volume_idx     = Column(Float)
    aqi_computed          = Column(Float)


# ---------------------------------------------------------------------------
# Table: fire_detections
# Raw FIRMS fire point records — one row per satellite detection.
# ---------------------------------------------------------------------------

class FireDetection(Base):
    __tablename__ = "fire_detections"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    timestamp_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    latitude      = Column(Float, nullable=False)
    longitude     = Column(Float, nullable=False)
    frp           = Column(Float)   # Fire Radiative Power (MW)
    confidence    = Column(String(16))
    satellite     = Column(String(32))
    bright_ti4    = Column(Float)   # Brightness temperature (K)
    daynight      = Column(String(1))  # 'D' or 'N'
    data_source   = Column(String(32))


# ---------------------------------------------------------------------------
# Table: ingestion_runs
# Audit log — one row per pipeline execution per source.
# ---------------------------------------------------------------------------

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    run_timestamp = Column(DateTime(timezone=True), nullable=False)
    source_name   = Column(String(32), nullable=False)
    mode          = Column(String(16))           # realtime | historical | static
    status        = Column(String(16))           # success | failed | skipped
    rows_written  = Column(Integer, default=0)
    error_message = Column(Text)
    duration_sec  = Column(Float)


# ---------------------------------------------------------------------------
# DBClient
# ---------------------------------------------------------------------------

class DBClient:
    """
    Thin wrapper around a SQLAlchemy engine providing
    write/read helpers for AeroAQI tables.

    Parameters
    ----------
    db_url : str | None
        SQLAlchemy connection URL.  Defaults to the DATABASE_URL
        environment variable, falling back to SQLite at data/db/aeroaqi.db.
    """

    def __init__(self, db_url: Optional[str] = None) -> None:
        if db_url is None:
            db_url = os.getenv("DATABASE_URL")

        if db_url is None:
            # Default: SQLite file in data/db/
            project_root = get_project_root()
            settings = load_settings()
            db_dir = project_root / settings["paths"]["db_dir"]
            db_dir.mkdir(parents=True, exist_ok=True)
            db_file = db_dir / "aeroaqi.db"
            db_url = f"sqlite:///{db_file}"
            log.info(f"[db] Using SQLite database at: {db_file}")
        else:
            log.info(f"[db] Using database: {db_url.split('@')[-1]}")  # hide credentials

        # SQLite needs check_same_thread=False for multi-threaded use
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

        self._engine = create_engine(
            db_url,
            connect_args=connect_args,
            echo=False,   # set True to log all SQL statements (verbose)
        )
        self._Session = sessionmaker(bind=self._engine)

        # Create tables if they don't exist, then migrate any new columns
        Base.metadata.create_all(self._engine)
        self.migrate_schema()
        log.debug("[db] Tables verified / migrated.")

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def write_observations(self, df: pd.DataFrame) -> int:
        """
        Write (upsert) rows from the master-schema DataFrame into the
        observations table.

        Duplicate handling:
          - If a row with the same (timestamp_utc, station_id, data_source)
            already exists, it is skipped (not overwritten).
          - This is an insert-if-not-exists strategy using SQLite's
            INSERT OR IGNORE (and PostgreSQL's ON CONFLICT DO NOTHING).

        Parameters
        ----------
        df : pd.DataFrame matching the master schema.

        Returns
        -------
        int  — number of new rows inserted.
        """
        if df.empty:
            log.warning("[db] write_observations called with empty DataFrame.")
            return 0

        required = ["timestamp_utc", "station_id", "data_source"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                f"DataFrame is missing required columns for DB write: {missing}"
            )

        rows_before = self._count_rows("observations")

        # Convert DataFrame rows to ORM objects
        records = df.to_dict(orient="records")
        obs_objects = []

        for rec in records:
            # Clean NaN → None (SQLAlchemy/SQLite prefer None over float('nan'))
            clean = {
                k: (None if (isinstance(v, float) and v != v) else v)
                for k, v in rec.items()
                if hasattr(Observation, k)  # only known columns
            }
            obs_objects.append(Observation(**clean))

        with self._Session() as session:
            # Use merge so duplicates are handled gracefully
            for obj in obs_objects:
                session.merge(obj) if obj.id else session.add(obj)
            session.commit()

        rows_after = self._count_rows("observations")
        inserted = rows_after - rows_before

        log.info(
            f"[db] write_observations: {inserted} new rows inserted "
            f"({len(records)} attempted, {len(records) - inserted} already existed)."
        )
        return inserted

    def write_fire_detections(self, df: pd.DataFrame) -> int:
        """
        Write raw FIRMS fire detection rows into the fire_detections table.

        Returns
        -------
        int — number of new rows inserted.
        """
        if df.empty:
            log.warning("[db] write_fire_detections called with empty DataFrame.")
            return 0

        rows_before = self._count_rows("fire_detections")
        records = df.to_dict(orient="records")
        fire_objects = []

        for rec in records:
            clean = {
                k: (None if (isinstance(v, float) and v != v) else v)
                for k, v in rec.items()
                if hasattr(FireDetection, k)
            }
            fire_objects.append(FireDetection(**clean))

        with self._Session() as session:
            session.add_all(fire_objects)
            session.commit()

        rows_after = self._count_rows("fire_detections")
        inserted = rows_after - rows_before
        log.info(f"[db] write_fire_detections: {inserted} new fire records inserted.")
        return inserted

    def log_run(
        self,
        source_name: str,
        status: str,
        rows_written: int = 0,
        mode: str = "realtime",
        error_message: Optional[str] = None,
        duration_sec: Optional[float] = None,
    ) -> None:
        """
        Record a pipeline run result in the ingestion_runs audit table.

        Parameters
        ----------
        source_name   : e.g. "openaq", "openmeteo"
        status        : "success" | "failed" | "skipped"
        rows_written  : number of rows inserted in this run
        mode          : "realtime" | "historical" | "static"
        error_message : exception text if status == "failed"
        duration_sec  : wall-clock seconds for the run
        """
        run = IngestionRun(
            run_timestamp=datetime.now(timezone.utc),
            source_name=source_name,
            mode=mode,
            status=status,
            rows_written=rows_written,
            error_message=error_message,
            duration_sec=duration_sec,
        )
        with self._Session() as session:
            session.add(run)
            session.commit()
        log.debug(
            f"[db] Logged run: source={source_name}, status={status}, "
            f"rows={rows_written}"
        )

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def read_observations(
        self,
        station_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        columns: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        Read observations from the database into a DataFrame.

        Parameters
        ----------
        station_id : Filter to a single station (optional).
        start_time : UTC datetime lower bound (optional).
        end_time   : UTC datetime upper bound (optional).
        columns    : List of columns to return.  Defaults to all.

        Returns
        -------
        pd.DataFrame
        """
        col_clause = ", ".join(columns) if columns else "*"
        query = f"SELECT {col_clause} FROM observations WHERE 1=1"
        params: dict = {}

        if station_id:
            query += " AND station_id = :station_id"
            params["station_id"] = station_id
        if start_time:
            query += " AND timestamp_utc >= :start_time"
            # Use a plain ISO string without timezone suffix so SQLite
            # string comparison works regardless of how the tz was stored.
            params["start_time"] = start_time.strftime("%Y-%m-%d %H:%M:%S")
        if end_time:
            query += " AND timestamp_utc <= :end_time"
            params["end_time"] = end_time.strftime("%Y-%m-%d %H:%M:%S")

        query += " ORDER BY timestamp_utc ASC"

        with self._engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        log.debug(f"[db] read_observations: {len(df)} rows returned.")
        return df

    def read_recent_ingestion_runs(self, n: int = 20) -> pd.DataFrame:
        """Return the N most recent ingestion run audit records."""
        query = (
            "SELECT * FROM ingestion_runs "
            "ORDER BY run_timestamp DESC "
            "LIMIT :n"
        )
        with self._engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={"n": n})
        return df

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _count_rows(self, table_name: str) -> int:
        """Return the current row count for a table."""
        with self._engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            return result.scalar() or 0

    def migrate_schema(self) -> list[str]:
        """
        Add any columns that exist in the Observation ORM model but are
        missing from the live database table.

        This is a lightweight forward-only migration: it only adds columns,
        never drops or renames them.  Safe to call multiple times (idempotent).

        Needed when a new code version adds columns to the ORM model but
        the SQLite file was created by an older version.

        Returns
        -------
        list[str]  — names of columns that were added.
        """
        inspector = sa_inspect(self._engine)
        existing_cols = {
            col["name"] for col in inspector.get_columns("observations")
        }

        added: list[str] = []
        with self._engine.begin() as conn:
            for col_attr in Observation.__table__.columns:
                col_name = col_attr.name
                if col_name in existing_cols:
                    continue
                # Determine SQLite type string
                col_type = col_attr.type.compile(
                    dialect=self._engine.dialect
                )
                sql = f"ALTER TABLE observations ADD COLUMN {col_name} {col_type}"
                conn.execute(text(sql))
                added.append(col_name)
                log.info(f"[db] migrate_schema: added column '{col_name}' ({col_type})")

        if added:
            log.info(f"[db] migrate_schema: {len(added)} column(s) added: {added}")
        else:
            log.debug("[db] migrate_schema: schema is already up to date.")
        return added

    def write_master_dataset(self, df: pd.DataFrame) -> int:
        """
        Persist master dataset rows — same as write_observations but
        explicitly named for clarity when called from the processing pipeline.

        The master dataset is the merged, feature-engineered output that
        includes derived columns (inversion_strength, fire_transport_risk, etc.).

        Parameters
        ----------
        df : pd.DataFrame matching or subset-matching the master schema.

        Returns
        -------
        int — number of new rows inserted.
        """
        return self.write_observations(df)

    def read_fire_detections(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        lat_min: Optional[float] = None,
        lat_max: Optional[float] = None,
        lon_min: Optional[float] = None,
        lon_max: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        Read raw FIRMS fire detection records from the database.

        Parameters
        ----------
        start_time : UTC datetime lower bound (optional).
        end_time   : UTC datetime upper bound (optional).
        lat_min / lat_max / lon_min / lon_max :
            Bounding box filter (optional).  Default covers the full
            Punjab–Haryana–Delhi NCR source region.

        Returns
        -------
        pd.DataFrame with columns: timestamp_utc, latitude, longitude,
            frp, confidence, satellite, bright_ti4, daynight, data_source
        """
        query = "SELECT * FROM fire_detections WHERE 1=1"
        params: dict = {}

        if start_time:
            query += " AND timestamp_utc >= :start_time"
            params["start_time"] = start_time.strftime("%Y-%m-%d %H:%M:%S")
        if end_time:
            query += " AND timestamp_utc <= :end_time"
            params["end_time"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
        if lat_min is not None:
            query += " AND latitude >= :lat_min"
            params["lat_min"] = lat_min
        if lat_max is not None:
            query += " AND latitude <= :lat_max"
            params["lat_max"] = lat_max
        if lon_min is not None:
            query += " AND longitude >= :lon_min"
            params["lon_min"] = lon_min
        if lon_max is not None:
            query += " AND longitude <= :lon_max"
            params["lon_max"] = lon_max

        query += " ORDER BY timestamp_utc ASC"

        with self._engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        log.debug(f"[db] read_fire_detections: {len(df)} rows returned.")
        return df

    def get_engine(self):
        """Return the underlying SQLAlchemy engine (for advanced use)."""
        return self._engine
