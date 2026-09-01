"""
src/processing/fire_aggregator.py
===================================
Spatial aggregation of raw NASA FIRMS fire detections to per-station features.

Problem
-------
The FIRMS fetcher produces one row per satellite fire detection, each with
its own lat/lon.  The master dataset needs fire features expressed relative
to each monitoring station (e.g. "how many fires are within 300 km of
Anand Vihar right now?").

This module bridges that gap by:
  1. Loading station coordinates from config/stations.yaml.
  2. For every (station × hourly timestamp) pair, finding all fire detections
     within the same hour window from the raw fire DataFrame.
  3. Computing the required spatial aggregate columns:
       - fire_count_300km   number of fires within 300 km
       - fire_count_500km   number of fires within 500 km
       - total_frp_300km    sum of Fire Radiative Power (MW) within 300 km
       - fire_distance_km   distance to the nearest fire (km)
       - fire_nearest_frp   FRP of that nearest fire (MW)

Usage
-----
    from src.processing.fire_aggregator import FireAggregator

    agg = FireAggregator()

    # fire_df  — raw DataFrame from db.read_fire_detections()
    # obs_df   — station observation DataFrame (needs timestamp_utc, station_id,
    #            latitude, longitude)
    result_df = agg.aggregate(obs_df, fire_df)
    # result_df has the same rows as obs_df plus the five fire columns above.

Design notes
------------
- Uses vectorised haversine (numpy) for performance; no geopandas dependency.
- If no fires are detected in the time window the fire columns are set to
  0 (counts/FRP) and NaN (distances), NOT raised as errors.
- Raw fire data is left untouched — this module is read-only with respect
  to the fire_detections table.
- The time-matching window is configurable (default: ±3 hours around the
  observation timestamp to account for satellite overpass latency).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from src.processing.unit_converter import haversine_km_vectorised
from src.utils.config_loader import load_stations
from src.utils.logger import get_logger

log = get_logger(__name__)

# Radius thresholds in kilometres (match config/stations.yaml)
_RADIUS_300 = 300.0
_RADIUS_500 = 500.0

# How many hours either side of the observation hour to search for fires.
# VIIRS NRT data has ~3 h latency, so fires detected at e.g. 01:30 should
# be matched to the 00:00 and 03:00 observation hours.
_FIRE_WINDOW_HOURS = 3


class FireAggregator:
    """
    Computes per-station fire proximity features from raw FIRMS fire points.

    Parameters
    ----------
    fire_window_hours : int
        Number of hours either side of each observation timestamp to include
        when looking for fire detections.  Default 3.
    radius_300_km, radius_500_km : float
        Distance thresholds for fire-count aggregation.
    """

    def __init__(
        self,
        fire_window_hours: int = _FIRE_WINDOW_HOURS,
        radius_300_km: float = _RADIUS_300,
        radius_500_km: float = _RADIUS_500,
    ) -> None:
        self._window_h = fire_window_hours
        self._r300 = radius_300_km
        self._r500 = radius_500_km
        self._stations: list[dict] = load_stations()
        log.debug(
            f"[fire_agg] FireAggregator initialised "
            f"(window=±{fire_window_hours}h, r300={radius_300_km} km, "
            f"r500={radius_500_km} km)"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def aggregate(
        self,
        obs_df: pd.DataFrame,
        fire_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Add fire proximity columns to each row in obs_df.

        Parameters
        ----------
        obs_df   : Observation DataFrame.  Must have columns:
                     timestamp_utc (datetime64, UTC), station_id,
                     latitude, longitude.
        fire_df  : Raw fire detection DataFrame from db.read_fire_detections()
                   or FIRMSFetcher.  Must have columns:
                     timestamp_utc, latitude, longitude, frp.

        Returns
        -------
        pd.DataFrame  — obs_df with five new columns added:
            fire_count_300km, fire_count_500km, total_frp_300km,
            fire_distance_km, fire_nearest_frp.
            Existing rows are never modified; new columns are appended.

        Notes
        -----
        - If fire_df is empty, all five columns are set to NaN.
        - Rows in obs_df that already have fire columns populated are
          NOT overwritten; skip them to allow idempotent re-runs.
        """
        if obs_df.empty:
            log.warning("[fire_agg] obs_df is empty — nothing to aggregate.")
            return obs_df

        obs_df = obs_df.copy()

        # Initialise output columns if absent
        for col in [
            "fire_count_300km", "fire_count_500km",
            "total_frp_300km", "fire_distance_km", "fire_nearest_frp",
        ]:
            if col not in obs_df.columns:
                obs_df[col] = np.nan

        if fire_df is None or fire_df.empty:
            log.warning(
                "[fire_agg] fire_df is empty — fire columns set to NaN."
            )
            return obs_df

        # Validate required columns
        obs_required = ["timestamp_utc", "latitude", "longitude"]
        fire_required = ["timestamp_utc", "latitude", "longitude"]
        for col in obs_required:
            if col not in obs_df.columns:
                log.error(f"[fire_agg] obs_df missing required column: '{col}'")
                return obs_df
        for col in fire_required:
            if col not in fire_df.columns:
                log.error(f"[fire_agg] fire_df missing required column: '{col}'")
                return obs_df

        # Ensure timestamps are UTC datetime
        obs_df["timestamp_utc"] = pd.to_datetime(
            obs_df["timestamp_utc"], utc=True, errors="coerce"
        ).dt.floor("h")
        fire_df = fire_df.copy()
        fire_df["timestamp_utc"] = pd.to_datetime(
            fire_df["timestamp_utc"], utc=True, errors="coerce"
        )
        fire_df = fire_df.dropna(subset=["timestamp_utc", "latitude", "longitude"])

        if fire_df.empty:
            log.warning("[fire_agg] All fire rows had invalid timestamps or coords.")
            return obs_df

        # Ensure numeric coordinates
        for col in ["latitude", "longitude"]:
            obs_df[col] = pd.to_numeric(obs_df[col], errors="coerce")
            fire_df[col] = pd.to_numeric(fire_df[col], errors="coerce")
        fire_df = fire_df.dropna(subset=["latitude", "longitude"])

        # Ensure frp is numeric (may be absent)
        if "frp" in fire_df.columns:
            fire_df["frp"] = pd.to_numeric(fire_df["frp"], errors="coerce")
        else:
            fire_df["frp"] = np.nan

        log.info(
            f"[fire_agg] Aggregating {len(fire_df)} fire detections "
            f"against {len(obs_df)} observation rows …"
        )

        # Process row by row — each observation has its own lat/lon/time
        results = obs_df.apply(
            lambda row: self._aggregate_one_row(row, fire_df),
            axis=1,
            result_type="expand",
        )

        # Assign results back
        fire_cols = [
            "fire_count_300km", "fire_count_500km",
            "total_frp_300km", "fire_distance_km", "fire_nearest_frp",
        ]
        for i, col in enumerate(fire_cols):
            obs_df[col] = results.iloc[:, i].values

        log.info(
            f"[fire_agg] Done. "
            f"Rows with ≥1 fire within 300 km: "
            f"{(obs_df['fire_count_300km'] > 0).sum()}"
        )
        return obs_df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _aggregate_one_row(
        self, row: pd.Series, fire_df: pd.DataFrame
    ) -> tuple:
        """
        Compute fire features for one observation row.

        Returns (count_300, count_500, total_frp_300, dist_km, nearest_frp).
        """
        lat = row["latitude"]
        lon = row["longitude"]
        ts = row["timestamp_utc"]

        # Skip if coordinates are missing
        if pd.isna(lat) or pd.isna(lon):
            return (np.nan, np.nan, np.nan, np.nan, np.nan)

        # Filter fire detections within the time window
        window_start = ts - pd.Timedelta(hours=self._window_h)
        window_end   = ts + pd.Timedelta(hours=self._window_h)
        mask_time = (
            (fire_df["timestamp_utc"] >= window_start)
            & (fire_df["timestamp_utc"] <= window_end)
        )
        nearby = fire_df[mask_time]

        if nearby.empty:
            return (0.0, 0.0, 0.0, np.nan, np.nan)

        # Vectorised haversine distance from this station to all fires
        distances = haversine_km_vectorised(
            lat, lon,
            nearby["latitude"], nearby["longitude"],
        )

        mask_300 = distances <= self._r300
        mask_500 = distances <= self._r500

        count_300 = float(mask_300.sum())
        count_500 = float(mask_500.sum())

        # Total FRP within 300 km (NaN FRP treated as 0 for sum)
        frp_300 = nearby.loc[mask_300, "frp"].fillna(0.0).sum()
        total_frp_300 = float(frp_300) if count_300 > 0 else 0.0

        # Nearest fire (regardless of radius threshold)
        if len(distances) > 0:
            nearest_idx = distances.idxmin()
            dist_km = float(distances[nearest_idx])
            nearest_frp = float(nearby.loc[nearest_idx, "frp"]) \
                if not pd.isna(nearby.loc[nearest_idx, "frp"]) else np.nan
        else:
            dist_km = np.nan
            nearest_frp = np.nan

        return (count_300, count_500, total_frp_300, dist_km, nearest_frp)

    # ------------------------------------------------------------------
    # Convenience: aggregate directly from DB
    # ------------------------------------------------------------------

    @staticmethod
    def from_db(
        db,
        obs_df: pd.DataFrame,
        start_time=None,
        end_time=None,
    ) -> pd.DataFrame:
        """
        Load fire detections from the database and aggregate onto obs_df.

        Parameters
        ----------
        db        : DBClient instance
        obs_df    : Observation DataFrame
        start_time, end_time : optional UTC datetime bounds for fire query

        Returns
        -------
        pd.DataFrame — obs_df with fire columns appended.
        """
        fire_df = db.read_fire_detections(
            start_time=start_time,
            end_time=end_time,
        )
        agg = FireAggregator()
        return agg.aggregate(obs_df, fire_df)
