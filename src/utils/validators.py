"""
src/utils/validators.py
=======================
Data-quality validation functions for AeroAQI.

Every fetcher calls these helpers AFTER loading raw data and BEFORE
writing to the processed directory or database.

Rules enforced
--------------
1.  Required columns must be present.
2.  Timestamps must be timezone-aware UTC; non-parseable values → error.
3.  Latitude must be in [23.0, 32.0] for Delhi NCR context.
4.  Longitude must be in [73.0, 80.0] for Delhi NCR context.
5.  Each numeric column has a physical valid_min / valid_max.
    Values outside the range are set to NaN and logged as warnings,
    never silently replaced with zero.
6.  Duplicate rows (same station_id + timestamp_utc) are detected and
    the second occurrence is dropped with a warning.
7.  Completeness below a threshold triggers a warning (not an error)
    because sparse data is normal for some sources.

Return convention
-----------------
All public functions return a (DataFrame, list[str]) tuple:
    df      — cleaned DataFrame (may have fewer rows than input)
    issues  — list of human-readable warning/error strings

Callers decide whether to raise on errors or just log them.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.schema.master_schema import SCHEMA_LOOKUP, REQUIRED_COLUMNS
from src.utils.logger import get_logger

log = get_logger(__name__)

# Minimum fraction of non-null values before a completeness warning fires.
_MIN_COMPLETENESS = 0.5


# ---------------------------------------------------------------------------
# 1. Column presence check
# ---------------------------------------------------------------------------

def check_required_columns(
    df: pd.DataFrame,
    required: list[str] | None = None,
) -> list[str]:
    """
    Verify that all required columns exist in the DataFrame.

    Parameters
    ----------
    df       : Input DataFrame.
    required : Column names to check.  Defaults to REQUIRED_COLUMNS from
               the master schema if not provided.

    Returns
    -------
    list[str]
        List of error messages (empty = all good).
    """
    if required is None:
        required = REQUIRED_COLUMNS
    errors: list[str] = []
    missing = [c for c in required if c not in df.columns]
    if missing:
        msg = f"Missing required columns: {missing}"
        log.error(msg)
        errors.append(msg)
    return errors


# ---------------------------------------------------------------------------
# 2. Timestamp normalisation
# ---------------------------------------------------------------------------

def normalise_timestamps(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp_utc",
) -> tuple[pd.DataFrame, list[str]]:
    """
    Parse and standardise the timestamp column to UTC.

    - Strings and Unix epochs are both handled.
    - Rows where the timestamp cannot be parsed are DROPPED (not zeroed).
    - The column is always returned as datetime64[ns, UTC].

    Returns
    -------
    (cleaned_df, issues)
    """
    issues: list[str] = []

    if timestamp_col not in df.columns:
        issues.append(f"Timestamp column '{timestamp_col}' not found — cannot normalise.")
        log.error(issues[-1])
        return df, issues

    original_len = len(df)

    # Attempt conversion; coerce un-parseable values to NaT
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], utc=True, errors="coerce")

    nat_count = df[timestamp_col].isna().sum()
    if nat_count > 0:
        msg = (
            f"{nat_count} rows had unparseable timestamps and were dropped "
            f"(out of {original_len} total rows)."
        )
        log.warning(msg)
        issues.append(msg)
        df = df.dropna(subset=[timestamp_col]).copy()

    # Ensure timezone is UTC (handles already-tz-aware inputs)
    df[timestamp_col] = df[timestamp_col].dt.tz_convert("UTC")

    # Truncate to the hour for consistent joining
    df[timestamp_col] = df[timestamp_col].dt.floor("h")

    return df, issues


# ---------------------------------------------------------------------------
# 3. Coordinate validation
# ---------------------------------------------------------------------------

def validate_coordinates(
    df: pd.DataFrame,
    lat_col: str = "latitude",
    lon_col: str = "longitude",
    lat_bounds: tuple[float, float] = (23.0, 32.0),
    lon_bounds: tuple[float, float] = (73.0, 80.0),
) -> tuple[pd.DataFrame, list[str]]:
    """
    Check that latitude and longitude are within the expected Delhi NCR
    regional bounds.  Rows outside the bounds are DROPPED with a warning.

    The bounds are wider than strict Delhi NCR to accommodate source-region
    fire data (Punjab, Haryana, western UP).

    Returns
    -------
    (cleaned_df, issues)
    """
    issues: list[str] = []
    original_len = len(df)

    for col, (lo, hi) in ((lat_col, lat_bounds), (lon_col, lon_bounds)):
        if col not in df.columns:
            issues.append(f"Coordinate column '{col}' not found.")
            log.error(issues[-1])
            continue

        # Convert to numeric first — non-numeric values become NaN
        df[col] = pd.to_numeric(df[col], errors="coerce")

        out_of_range = df[(df[col] < lo) | (df[col] > hi) | df[col].isna()]
        if not out_of_range.empty:
            msg = (
                f"{len(out_of_range)} rows have {col} outside [{lo}, {hi}] "
                f"and were dropped."
            )
            log.warning(msg)
            issues.append(msg)
            df = df[(df[col] >= lo) & (df[col] <= hi)].copy()

    return df, issues


# ---------------------------------------------------------------------------
# 4. Physical range validation for numeric columns
# ---------------------------------------------------------------------------

def validate_physical_ranges(
    df: pd.DataFrame,
    columns: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """
    For each numeric column that has a valid_min / valid_max defined in
    the master schema, replace out-of-range values with NaN.

    IMPORTANT: values are set to NaN, NEVER to zero.  This preserves the
    distinction between "no measurement" (NaN) and "zero pollution" (0.0).

    Parameters
    ----------
    df      : DataFrame to validate.
    columns : Subset of columns to check.  Defaults to all schema columns
              that are present in df.

    Returns
    -------
    (cleaned_df, issues)  — df is modified in-place, issues is a log list.
    """
    issues: list[str] = []
    if columns is None:
        columns = [c for c in SCHEMA_LOOKUP if c in df.columns]

    for col in columns:
        spec = SCHEMA_LOOKUP.get(col)
        if spec is None:
            continue

        if spec.valid_min is None and spec.valid_max is None:
            continue  # no bounds defined for this column

        if col not in df.columns:
            continue

        # Convert to numeric; non-numeric → NaN
        df[col] = pd.to_numeric(df[col], errors="coerce")

        mask = pd.Series([False] * len(df), index=df.index)

        if spec.valid_min is not None:
            mask = mask | (df[col] < spec.valid_min)
        if spec.valid_max is not None:
            mask = mask | (df[col] > spec.valid_max)

        bad_count = int(mask.sum())
        if bad_count > 0:
            # Show a sample of the bad values for debugging
            sample_vals = df.loc[mask, col].head(5).tolist()
            msg = (
                f"Column '{col}': {bad_count} value(s) outside physical range "
                f"[{spec.valid_min}, {spec.valid_max}] set to NaN. "
                f"Sample bad values: {sample_vals}"
            )
            log.warning(msg)
            issues.append(msg)
            # Set to NaN — NOT zero
            df.loc[mask, col] = np.nan

    return df, issues


# ---------------------------------------------------------------------------
# 5. Duplicate detection
# ---------------------------------------------------------------------------

def remove_duplicates(
    df: pd.DataFrame,
    key_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Detect and remove duplicate rows based on key columns.

    Default key: (timestamp_utc, station_id).
    If station_id is absent (e.g. gridded data), key falls back to
    (timestamp_utc, latitude, longitude).

    The first occurrence is kept; subsequent duplicates are dropped.

    Returns
    -------
    (deduplicated_df, issues)
    """
    issues: list[str] = []

    if key_columns is None:
        if "station_id" in df.columns:
            key_columns = ["timestamp_utc", "station_id"]
        else:
            key_columns = ["timestamp_utc", "latitude", "longitude"]

    # Only use key columns that are actually present
    available_keys = [c for c in key_columns if c in df.columns]
    if not available_keys:
        issues.append("No key columns found for duplicate check — skipping.")
        log.warning(issues[-1])
        return df, issues

    n_before = len(df)
    df = df.drop_duplicates(subset=available_keys, keep="first").copy()
    n_dropped = n_before - len(df)

    if n_dropped > 0:
        msg = (
            f"Removed {n_dropped} duplicate rows "
            f"(key columns: {available_keys})."
        )
        log.warning(msg)
        issues.append(msg)

    return df, issues


# ---------------------------------------------------------------------------
# 6. Completeness check (warning only, no rows dropped)
# ---------------------------------------------------------------------------

def check_completeness(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    min_fraction: float = _MIN_COMPLETENESS,
) -> list[str]:
    """
    Warn when a column has fewer than min_fraction non-null values.

    This is informational — it does NOT modify the DataFrame.

    Returns
    -------
    list[str]  — warning messages for columns below the threshold.
    """
    warnings: list[str] = []
    if len(df) == 0:
        warnings.append("DataFrame is empty — cannot check completeness.")
        log.warning(warnings[-1])
        return warnings

    if columns is None:
        columns = list(df.columns)

    for col in columns:
        if col not in df.columns:
            continue
        frac = df[col].notna().mean()
        if frac < min_fraction:
            msg = (
                f"Column '{col}' is only {frac:.1%} complete "
                f"(threshold: {min_fraction:.0%})."
            )
            log.warning(msg)
            warnings.append(msg)

    return warnings


# ---------------------------------------------------------------------------
# 7. Master validation runner — call this from each fetcher
# ---------------------------------------------------------------------------

def run_all_validations(
    df: pd.DataFrame,
    source_name: str,
    required_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, bool]:
    """
    Run the full validation suite on a fetched DataFrame and return the
    cleaned result.

    Parameters
    ----------
    df               : Raw-ish DataFrame from a fetcher.
    source_name      : Name of the data source (used in log messages).
    required_columns : Override the default REQUIRED_COLUMNS list if needed.

    Returns
    -------
    (cleaned_df, success)
        success is False if any hard errors were found (missing required
        columns, completely empty result, etc.).
    """
    all_issues: list[str] = []
    success = True

    log.info(f"[{source_name}] Starting validation — {len(df)} rows incoming.")

    # 0. Empty check
    if df.empty:
        log.error(f"[{source_name}] DataFrame is empty after fetch — nothing to validate.")
        return df, False

    # 1. Required columns
    col_errors = check_required_columns(df, required_columns)
    all_issues.extend(col_errors)
    if col_errors:
        success = False
        # Cannot proceed with remaining checks if join keys are absent
        return df, success

    # 2. Timestamps
    df, ts_issues = normalise_timestamps(df)
    all_issues.extend(ts_issues)

    # 3. Coordinates (skip for fire raw-point data which uses its own columns)
    if "latitude" in df.columns and "longitude" in df.columns:
        df, coord_issues = validate_coordinates(df)
        all_issues.extend(coord_issues)

    # 4. Physical ranges
    df, range_issues = validate_physical_ranges(df)
    all_issues.extend(range_issues)

    # 5. Duplicates
    df, dup_issues = remove_duplicates(df)
    all_issues.extend(dup_issues)

    # 6. Completeness warning
    warn_issues = check_completeness(df)
    all_issues.extend(warn_issues)

    # Summary
    n_issues = len(all_issues)
    if n_issues == 0:
        log.info(f"[{source_name}] Validation passed — {len(df)} clean rows.")
    else:
        log.warning(
            f"[{source_name}] Validation completed with {n_issues} issue(s) — "
            f"{len(df)} rows remain."
        )

    return df, success
