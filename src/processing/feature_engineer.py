"""
src/processing/feature_engineer.py
=====================================
Derives physics-informed features from observed variables in the master dataset.

This module is the bridge between raw measurements and model-ready features.
It operates on a DataFrame that already has weather and fire columns populated,
and appends the derived columns defined in master_schema.py.

Derived columns computed here
------------------------------
  inversion_flag        (boolean)   — temperature inversion indicator
  inversion_strength    (Float64)   — strength of the inversion in °C
  temperature_profile   (string)    — JSON of {pressure_hPa: temp_C}
  wind_transport_idx    (Float64)   — NW wind alignment score [0, 1]
  mixing_volume_idx     (Float64)   — pbl_height × wind_speed
  fire_transport_risk   (Float64)   — composite fire transport risk [0, 1]
  aqi_computed          (Float64)   — CPCB AQI from PM2.5 and PM10

Rules
-----
- Never overwrite an existing non-NaN value.  Re-running is idempotent.
- Never replace a NaN input with zero.
- Every function documents exactly which input columns it requires.
- If a required input column is missing or all-NaN, the output column
  is left as NaN with a logged warning.

Physics notes
-------------
Temperature inversion:
  A temperature inversion occurs when the air temperature increases with
  altitude instead of decreasing.  Near Delhi, a shallow surface inversion
  at night traps pollutants close to the ground.

  We detect it by comparing the 850 hPa level temperature (~1500 m) to the
  2 m surface temperature.  When temp_850hpa > temperature + THRESHOLD,
  an inversion is flagged.

  Threshold = 2 °C  (empirical value used in several South Asian AQ studies).

Mixing volume index:
  MVI = PBL_height (m) × wind_speed (m/s)
  Units: m²/s.  Higher = more ventilation = better pollutant dispersal.
  Reference: Seinfeld & Pandis, "Atmospheric Chemistry and Physics", 3rd ed.

Wind transport index:
  Directional score [0, 1] — how well the current wind direction aligns
  with NW flow (315°) that brings Punjab/Haryana smoke toward Delhi.
  Uses the cosine formula from unit_converter.nw_wind_alignment().

Fire transport risk:
  Composite score combining three signals:
    1. NW wind alignment  (weight 0.40)
    2. Proximity signal   = exp(-fire_distance_km / 500)  (weight 0.35)
    3. FRP signal         = tanh(total_frp_300km / 1000)  (weight 0.25)
  All signals are in [0, 1] before weighting.
  The final score is clipped to [0, 1].
  NaN if all three inputs are NaN.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.processing.unit_converter import compute_cpcb_aqi, nw_wind_alignment
from src.utils.logger import get_logger

log = get_logger(__name__)

# Inversion detection threshold (°C)
_INVERSION_THRESHOLD_C = 2.0

# Fire transport risk weights (must sum to 1.0)
_W_WIND   = 0.40
_W_PROX   = 0.35
_W_FRP    = 0.25

# Normalisation constants for fire signals
_PROX_DECAY_KM   = 500.0   # e-folding distance for proximity signal
_FRP_SATURATION  = 1000.0  # FRP level at which tanh ≈ 0.76


class FeatureEngineer:
    """
    Computes all DERIVED columns for the master dataset.

    Usage
    -----
        from src.processing.feature_engineer import FeatureEngineer

        fe = FeatureEngineer()
        enriched_df = fe.compute_all(df)
    """

    def __init__(
        self,
        inversion_threshold_c: float = _INVERSION_THRESHOLD_C,
    ) -> None:
        self._inv_thresh = inversion_threshold_c

    # ------------------------------------------------------------------
    # Master entry point
    # ------------------------------------------------------------------

    def compute_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all derived feature columns and append them to df.

        Calls each individual compute method in dependency order.
        Each method is safe to call when its inputs are partially NaN.

        Parameters
        ----------
        df : pd.DataFrame — master dataset with OBSERVED columns populated.

        Returns
        -------
        pd.DataFrame — same rows, with DERIVED columns appended/filled.
        """
        if df.empty:
            log.warning("[feat_eng] Input DataFrame is empty — skipping.")
            return df

        df = df.copy()

        df = self.compute_inversion(df)
        df = self.compute_temperature_profile(df)
        df = self.compute_mixing_volume(df)
        df = self.compute_wind_transport(df)
        df = self.compute_fire_transport_risk(df)
        df = self.compute_aqi(df)

        log.info(
            f"[feat_eng] Feature engineering complete — "
            f"{len(df)} rows, {df.shape[1]} columns."
        )
        return df

    # ------------------------------------------------------------------
    # Individual feature methods (each idempotent)
    # ------------------------------------------------------------------

    def compute_inversion(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute inversion_flag and inversion_strength.

        Requires: temperature, temp_850hpa
        Produces: inversion_strength, inversion_flag

        inversion_strength = temp_850hpa − temperature
        inversion_flag     = True when inversion_strength > threshold (2 °C)
        """
        df = df.copy()

        if "temperature" not in df.columns or "temp_850hpa" not in df.columns:
            log.warning(
                "[feat_eng] compute_inversion: missing 'temperature' or "
                "'temp_850hpa' columns — skipping."
            )
            if "inversion_strength" not in df.columns:
                df["inversion_strength"] = np.nan
            if "inversion_flag" not in df.columns:
                df["inversion_flag"] = pd.NA
            return df

        t_surf = pd.to_numeric(df["temperature"], errors="coerce")
        t_850 = pd.to_numeric(df["temp_850hpa"], errors="coerce")

        strength = t_850 - t_surf

        # Only fill rows where both inputs are available
        have_both = t_surf.notna() & t_850.notna()

        if "inversion_strength" not in df.columns:
            df["inversion_strength"] = np.nan
        df.loc[have_both, "inversion_strength"] = strength[have_both]

        if "inversion_flag" not in df.columns:
            df["inversion_flag"] = pd.NA
        df.loc[have_both, "inversion_flag"] = (
            strength[have_both] > self._inv_thresh
        )

        n_inv = int(have_both.sum() and (strength[have_both] > self._inv_thresh).sum())
        log.debug(
            f"[feat_eng] compute_inversion: "
            f"{have_both.sum()} rows processed, {n_inv} inversions detected."
        )
        return df

    def compute_temperature_profile(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build a JSON-serialised temperature profile from pressure-level columns.

        Requires: (any of) temp_925hpa, temp_850hpa, temp_700hpa
        Also uses: temperature (surface, added as key 1013)
        Produces: temperature_profile

        Format: '{"1013": 28.1, "925": 26.3, "850": 22.1, "700": 14.5}'
        Levels with NaN values are omitted from the JSON.
        If all levels are NaN the column is set to NaN (not "{}").
        """
        df = df.copy()

        level_map = {
            "1013": "temperature",
            "925":  "temp_925hpa",
            "850":  "temp_850hpa",
            "700":  "temp_700hpa",
        }

        def _build_profile(row: pd.Series) -> str | float:
            profile = {}
            for pressure, col in level_map.items():
                if col in row.index:
                    val = row[col]
                    if pd.notna(val):
                        profile[pressure] = round(float(val), 2)
            if not profile:
                return float("nan")
            return json.dumps(profile)

        # Always initialise as plain Python object column to avoid
        # Arrow/numpy dtype conflicts when assigning string values.
        if "temperature_profile" not in df.columns:
            existing = [None] * len(df)
        else:
            existing = list(df["temperature_profile"].where(
                df["temperature_profile"].notna(), other=None
            ))

        # Only compute for rows where at least one level is available
        level_cols = [c for c in level_map.values() if c in df.columns]
        if not level_cols:
            log.warning(
                "[feat_eng] compute_temperature_profile: no pressure-level "
                "columns found — skipping."
            )
            df["temperature_profile"] = existing
            return df

        has_any = df[level_cols].notna().any(axis=1)

        # Build a plain Python list — avoids all pandas dtype conflicts
        new_col = existing[:]
        for iloc_pos, (idx, row) in enumerate(df.iterrows()):
            if has_any.iloc[iloc_pos] and existing[iloc_pos] is None:
                new_col[iloc_pos] = _build_profile(row)

        # Assign as a plain object-dtype Series
        df["temperature_profile"] = pd.array(new_col, dtype=object)

        log.debug(
            f"[feat_eng] compute_temperature_profile: "
            f"{has_any.sum()} profiles built."
        )
        return df

    def compute_mixing_volume(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute mixing_volume_idx = pbl_height × wind_speed.

        Requires: pbl_height (m), wind_speed (m/s)
        Produces: mixing_volume_idx (m²/s)

        NaN if either input is NaN (not zero — zero wind or zero PBL
        would each have physical meaning).
        """
        df = df.copy()

        if "pbl_height" not in df.columns or "wind_speed" not in df.columns:
            log.warning(
                "[feat_eng] compute_mixing_volume: missing 'pbl_height' "
                "or 'wind_speed' — skipping."
            )
            if "mixing_volume_idx" not in df.columns:
                df["mixing_volume_idx"] = np.nan
            return df

        pbl = pd.to_numeric(df["pbl_height"], errors="coerce")
        ws = pd.to_numeric(df["wind_speed"], errors="coerce")

        have_both = pbl.notna() & ws.notna()

        if "mixing_volume_idx" not in df.columns:
            df["mixing_volume_idx"] = np.nan
        df.loc[have_both, "mixing_volume_idx"] = pbl[have_both] * ws[have_both]

        log.debug(
            f"[feat_eng] compute_mixing_volume: "
            f"{have_both.sum()} rows computed."
        )
        return df

    def compute_wind_transport(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute wind_transport_idx = NW wind alignment score [0, 1].

        Requires: wind_direction (°, met convention)
        Produces: wind_transport_idx

        Uses cosine formula: (1 + cos(direction − 315°)) / 2
        """
        df = df.copy()

        if "wind_direction" not in df.columns:
            log.warning(
                "[feat_eng] compute_wind_transport: 'wind_direction' "
                "column missing — skipping."
            )
            if "wind_transport_idx" not in df.columns:
                df["wind_transport_idx"] = np.nan
            return df

        wd = pd.to_numeric(df["wind_direction"], errors="coerce")
        have_wd = wd.notna()

        if "wind_transport_idx" not in df.columns:
            df["wind_transport_idx"] = np.nan
        df.loc[have_wd, "wind_transport_idx"] = nw_wind_alignment(wd[have_wd]).values

        log.debug(
            f"[feat_eng] compute_wind_transport: "
            f"{have_wd.sum()} rows computed."
        )
        return df

    def compute_fire_transport_risk(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute fire_transport_risk — composite [0, 1] fire risk score.

        Inputs (all optional — missing ones reduce the score proportionally):
          wind_transport_idx   NW wind alignment score [0, 1]     weight 0.40
          fire_distance_km     km to nearest fire                  weight 0.35
          total_frp_300km      total FRP (MW) within 300 km        weight 0.25

        Signals:
          wind_signal  = wind_transport_idx  (already [0, 1])
          prox_signal  = exp(-fire_distance_km / 500)  ([0, 1]: 1=nearby, 0=far)
          frp_signal   = tanh(total_frp_300km / 1000)  ([0, 1]: saturates at high FRP)

        When a signal is unavailable (NaN):
          - Its weight is redistributed to the available signals.
          - If ALL inputs are NaN, result is NaN.
        """
        df = df.copy()

        if "fire_transport_risk" not in df.columns:
            df["fire_transport_risk"] = np.nan

        w_wind = pd.to_numeric(
            df.get("wind_transport_idx", pd.Series(dtype=float)), errors="coerce"
        )
        dist = pd.to_numeric(
            df.get("fire_distance_km", pd.Series(dtype=float)), errors="coerce"
        )
        frp_total = pd.to_numeric(
            df.get("total_frp_300km", pd.Series(dtype=float)), errors="coerce"
        )

        # Re-index to match df
        w_wind    = w_wind.reindex(df.index)
        dist      = dist.reindex(df.index)
        frp_total = frp_total.reindex(df.index)

        prox_signal = np.exp(-dist / _PROX_DECAY_KM)   # [0, 1]
        frp_signal  = np.tanh(frp_total / _FRP_SATURATION)  # [0, 1]

        # Build weighted sum with available signals only
        scores = pd.Series(np.nan, index=df.index)
        for i in df.index:
            signals = []
            weights = []
            if pd.notna(w_wind.get(i)):
                signals.append(float(w_wind[i]))
                weights.append(_W_WIND)
            if pd.notna(prox_signal.get(i)):
                signals.append(float(prox_signal[i]))
                weights.append(_W_PROX)
            if pd.notna(frp_signal.get(i)):
                signals.append(float(frp_signal[i]))
                weights.append(_W_FRP)

            if not signals:
                continue

            total_w = sum(weights)
            score = sum(s * w for s, w in zip(signals, weights)) / total_w
            scores[i] = float(np.clip(score, 0.0, 1.0))

        df["fire_transport_risk"] = scores

        n_computed = scores.notna().sum()
        log.debug(
            f"[feat_eng] compute_fire_transport_risk: "
            f"{n_computed} rows computed."
        )
        return df

    def compute_aqi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute aqi_computed using the CPCB sub-index formula.

        Requires: pm25 (µg/m³), pm10 (µg/m³)
        Produces: aqi_computed

        Only fills rows where aqi_raw is NaN (prefer the observed value
        when it is available).

        AQI = max(PM2.5 sub-index, PM10 sub-index)
        """
        df = df.copy()

        has_pm25 = "pm25" in df.columns
        has_pm10 = "pm10" in df.columns

        if not has_pm25 and not has_pm10:
            log.warning(
                "[feat_eng] compute_aqi: neither 'pm25' nor 'pm10' "
                "columns found — skipping."
            )
            if "aqi_computed" not in df.columns:
                df["aqi_computed"] = np.nan
            return df

        pm25_ser = pd.to_numeric(
            df["pm25"] if has_pm25 else pd.Series(np.nan, index=df.index),
            errors="coerce",
        )
        pm10_ser = pd.to_numeric(
            df["pm10"] if has_pm10 else pd.Series(np.nan, index=df.index),
            errors="coerce",
        )

        computed = compute_cpcb_aqi(pm25_ser, pm10_ser)

        if "aqi_computed" not in df.columns:
            df["aqi_computed"] = np.nan

        # Only fill where aqi_computed is still NaN (don't overwrite)
        needs_fill = df["aqi_computed"].isna() & computed.notna()
        df.loc[needs_fill, "aqi_computed"] = computed[needs_fill]

        log.debug(
            f"[feat_eng] compute_aqi: {needs_fill.sum()} rows computed."
        )
        return df
