"""
src/processing/quality_report.py
===================================
Generates a human-readable and machine-readable data-quality report for the
master dataset.

What it measures
----------------
For each column:
  - completeness   fraction of non-NaN rows
  - in_range_frac  fraction of non-NaN values within physical bounds (schema)
  - n_total        total rows
  - n_valid        non-NaN rows
  - n_invalid      rows with out-of-range values
  - min, max       observed min/max (ignoring NaN)
  - mean, std      descriptive stats

Summary metrics:
  - overall_completeness   mean completeness across all columns
  - columns_below_50pct    list of columns with < 50% completeness
  - columns_out_of_range   list of columns with any out-of-range values
  - unavailable_fields     fields that are entirely NaN (data source not configured)

Usage
-----
    from src.processing.quality_report import QualityReport

    report = QualityReport(df)
    summary = report.summary()          # dict — print-friendly
    col_df  = report.per_column_stats() # DataFrame — one row per column
    report.print_report()               # formatted ASCII table
    report.save(path)                   # saves both JSON + CSV
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.schema.master_schema import MASTER_SCHEMA, SCHEMA_LOOKUP
from src.utils.logger import get_logger

log = get_logger(__name__)

# Columns that are EXPECTED to be entirely NaN when sources are not configured
_KNOWN_UNAVAILABLE: dict[str, str] = {
    "aqi_raw":             "Requires raw AQI from CPCB/OpenAQ data source",
    "fire_count_300km":    "Requires FIRMS fire data + spatial aggregation",
    "fire_count_500km":    "Requires FIRMS fire data + spatial aggregation",
    "total_frp_300km":     "Requires FIRMS fire data + spatial aggregation",
    "fire_distance_km":    "Requires FIRMS fire data + spatial aggregation",
    "fire_nearest_frp":    "Requires FIRMS fire data + spatial aggregation",
    "fire_transport_risk": "Requires fire data + wind_direction + spatial aggregation",
    "temperature_profile": "Requires Open-Meteo pressure-level variables",
    "inversion_flag":      "Requires temperature + temp_850hpa (feature engineering)",
    "inversion_strength":  "Requires temperature + temp_850hpa (feature engineering)",
    "wind_transport_idx":  "Requires wind_direction (feature engineering)",
    "mixing_volume_idx":   "Requires pbl_height + wind_speed (feature engineering)",
    "aqi_computed":        "Requires pm25 and/or pm10 (feature engineering)",
}


class QualityReport:
    """
    Data quality report for the master dataset.

    Parameters
    ----------
    df        : pd.DataFrame — master dataset to assess
    source_name : str        — label for log messages (default "master")
    """

    def __init__(
        self, df: pd.DataFrame, source_name: str = "master"
    ) -> None:
        self._df = df
        self._source = source_name
        self._generated_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Per-column statistics
    # ------------------------------------------------------------------

    def per_column_stats(self) -> pd.DataFrame:
        """
        Return a DataFrame with one row per column showing completeness
        and range metrics.

        Columns in the output:
          column, n_total, n_valid, completeness_pct, n_out_of_range,
          in_range_pct, obs_min, obs_max, obs_mean, obs_std,
          schema_min, schema_max, category, source, available
        """
        rows = []
        n_total = len(self._df)

        for spec in MASTER_SCHEMA:
            col = spec.name
            if col not in self._df.columns:
                rows.append({
                    "column": col,
                    "n_total": n_total,
                    "n_valid": 0,
                    "completeness_pct": 0.0,
                    "n_out_of_range": 0,
                    "in_range_pct": None,
                    "obs_min": None,
                    "obs_max": None,
                    "obs_mean": None,
                    "obs_std": None,
                    "schema_min": spec.valid_min,
                    "schema_max": spec.valid_max,
                    "category": spec.category,
                    "source": spec.source,
                    "available": False,
                    "note": "Column absent from DataFrame",
                })
                continue

            series = self._df[col]
            # Try converting to numeric for stats (skip non-numeric)
            numeric = pd.to_numeric(series, errors="coerce")
            n_valid = int(series.notna().sum())
            completeness = (n_valid / n_total * 100.0) if n_total > 0 else 0.0

            n_oor = 0
            in_range_pct = None
            if n_valid > 0 and (spec.valid_min is not None or spec.valid_max is not None):
                mask_valid = numeric.notna()
                mask_lo = (numeric < spec.valid_min) if spec.valid_min is not None \
                    else pd.Series(False, index=numeric.index)
                mask_hi = (numeric > spec.valid_max) if spec.valid_max is not None \
                    else pd.Series(False, index=numeric.index)
                n_oor = int((mask_valid & (mask_lo | mask_hi)).sum())
                in_range_pct = ((n_valid - n_oor) / n_valid * 100.0)

            obs_min = float(numeric.min()) if n_valid > 0 else None
            obs_max = float(numeric.max()) if n_valid > 0 else None
            obs_mean = float(numeric.mean()) if n_valid > 0 else None
            obs_std = float(numeric.std()) if n_valid > 1 else None

            note = ""
            if n_valid == 0 and col in _KNOWN_UNAVAILABLE:
                note = _KNOWN_UNAVAILABLE[col]

            rows.append({
                "column": col,
                "n_total": n_total,
                "n_valid": n_valid,
                "completeness_pct": round(completeness, 1),
                "n_out_of_range": n_oor,
                "in_range_pct": round(in_range_pct, 1) if in_range_pct is not None else None,
                "obs_min": round(obs_min, 3) if obs_min is not None else None,
                "obs_max": round(obs_max, 3) if obs_max is not None else None,
                "obs_mean": round(obs_mean, 3) if obs_mean is not None else None,
                "obs_std": round(obs_std, 3) if obs_std is not None else None,
                "schema_min": spec.valid_min,
                "schema_max": spec.valid_max,
                "category": spec.category,
                "source": spec.source,
                "available": n_valid > 0,
                "note": note,
            })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Summary metrics
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """
        Return a dict of high-level quality metrics for the master dataset.

        Keys:
          generated_at, source, n_rows, n_columns_in_schema,
          n_columns_present, overall_completeness_pct,
          columns_below_50pct, columns_with_oor_values,
          unavailable_fields, time_range_utc
        """
        col_df = self.per_column_stats()

        n_rows = len(self._df)
        n_present = int(col_df["available"].sum())
        overall_completeness = float(col_df["completeness_pct"].mean())
        below_50 = col_df[col_df["completeness_pct"] < 50.0]["column"].tolist()
        has_oor = col_df[col_df["n_out_of_range"] > 0]["column"].tolist()

        unavailable = {
            row["column"]: row["note"]
            for _, row in col_df.iterrows()
            if not row["available"] and row["note"]
        }

        # Time range
        time_range = {"start": None, "end": None}
        if "timestamp_utc" in self._df.columns and not self._df.empty:
            ts = pd.to_datetime(self._df["timestamp_utc"], utc=True, errors="coerce")
            if ts.notna().any():
                time_range = {
                    "start": ts.min().isoformat(),
                    "end": ts.max().isoformat(),
                }

        return {
            "generated_at": self._generated_at.isoformat(),
            "source": self._source,
            "n_rows": n_rows,
            "n_columns_in_schema": len(MASTER_SCHEMA),
            "n_columns_present": n_present,
            "overall_completeness_pct": round(overall_completeness, 1),
            "columns_below_50pct": below_50,
            "columns_with_oor_values": has_oor,
            "unavailable_fields": unavailable,
            "time_range_utc": time_range,
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def print_report(self) -> None:
        """Print a formatted ASCII quality report to stdout."""
        s = self.summary()
        col_df = self.per_column_stats()

        divider = "─" * 80
        print(f"\n{divider}")
        print(f"  AeroAQI Master Dataset — Quality Report")
        print(f"  Generated : {s['generated_at']}")
        print(f"  Source    : {s['source']}")
        print(f"  Rows      : {s['n_rows']}")
        print(
            f"  Time range: "
            f"{s['time_range_utc']['start']} → {s['time_range_utc']['end']}"
        )
        print(divider)
        print(
            f"\n  Overall completeness : {s['overall_completeness_pct']:.1f}%"
        )
        print(
            f"  Columns present      : "
            f"{s['n_columns_present']}/{s['n_columns_in_schema']}"
        )

        if s["columns_below_50pct"]:
            print(f"\n  ⚠  Columns below 50% completeness:")
            for col in s["columns_below_50pct"]:
                print(f"      • {col}")

        if s["columns_with_oor_values"]:
            print(f"\n  ⚠  Columns with out-of-range values:")
            for col in s["columns_with_oor_values"]:
                n = int(col_df.loc[col_df["column"] == col, "n_out_of_range"].iloc[0])
                print(f"      • {col}  ({n} rows)")

        if s["unavailable_fields"]:
            print(f"\n  ℹ  Fields unavailable (source not yet configured):")
            for field, reason in s["unavailable_fields"].items():
                print(f"      • {field:<25}  {reason}")

        print(f"\n{'─' * 80}")
        header = (
            f"  {'Column':<26} {'Cat':8} {'Complete%':>10} "
            f"{'OOR':>6} {'Min':>8} {'Max':>8}"
        )
        print(header)
        print("─" * 80)
        for _, row in col_df.iterrows():
            comp = f"{row['completeness_pct']:.0f}%"
            oor = str(row["n_out_of_range"]) if row["n_out_of_range"] > 0 else "—"
            mn = f"{row['obs_min']:.1f}" if row["obs_min"] is not None else "—"
            mx = f"{row['obs_max']:.1f}" if row["obs_max"] is not None else "—"
            mark = " ✗" if row["n_out_of_range"] > 0 else ""
            print(
                f"  {row['column']:<26} {row['category']:8} {comp:>10} "
                f"{oor:>6} {mn:>8} {mx:>8}{mark}"
            )
        print(f"{'─' * 80}\n")

    def save(self, output_dir: Path) -> tuple[Path, Path]:
        """
        Save the quality report as:
          - <output_dir>/quality_report.json   (summary + per-column stats)
          - <output_dir>/quality_report.csv    (per-column stats only)

        Returns
        -------
        (json_path, csv_path)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        col_df = self.per_column_stats()
        s = self.summary()

        # Add per-column detail to JSON
        s["per_column"] = col_df.to_dict(orient="records")

        json_path = output_dir / "quality_report.json"
        json_path.write_text(
            json.dumps(s, indent=2, default=str), encoding="utf-8"
        )

        csv_path = output_dir / "quality_report.csv"
        col_df.to_csv(csv_path, index=False)

        log.info(
            f"[quality] Report saved → {json_path.name}, {csv_path.name}"
        )
        return json_path, csv_path
