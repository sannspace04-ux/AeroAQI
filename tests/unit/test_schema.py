"""
tests/unit/test_schema.py
==========================
Unit tests for src/schema/master_schema.py

Run with:
    pytest tests/unit/test_schema.py -v
"""

import pandas as pd
import pytest

from src.schema.master_schema import (
    COLUMN_NAMES,
    MASTER_SCHEMA,
    REQUIRED_COLUMNS,
    SCHEMA_LOOKUP,
    ColumnSpec,
    empty_master_dataframe,
)


class TestMasterSchema:

    def test_all_column_names_are_unique(self):
        names = [c.name for c in MASTER_SCHEMA]
        assert len(names) == len(set(names)), "Duplicate column names found in MASTER_SCHEMA"

    def test_column_names_list_matches_schema(self):
        assert COLUMN_NAMES == [c.name for c in MASTER_SCHEMA]

    def test_schema_lookup_keys_match_column_names(self):
        assert set(SCHEMA_LOOKUP.keys()) == set(COLUMN_NAMES)

    def test_required_columns_are_not_nullable(self):
        for name in REQUIRED_COLUMNS:
            spec = SCHEMA_LOOKUP[name]
            assert not spec.nullable, (
                f"Column '{name}' is in REQUIRED_COLUMNS but is marked nullable=True"
            )

    def test_join_key_columns_are_required(self):
        """timestamp_utc and station_id must always be required."""
        assert "timestamp_utc" in REQUIRED_COLUMNS
        assert "station_id" in REQUIRED_COLUMNS

    def test_valid_min_less_than_valid_max(self):
        for spec in MASTER_SCHEMA:
            if spec.valid_min is not None and spec.valid_max is not None:
                assert spec.valid_min < spec.valid_max, (
                    f"Column '{spec.name}': valid_min ({spec.valid_min}) "
                    f">= valid_max ({spec.valid_max})"
                )

    def test_all_categories_are_known_values(self):
        known = {"OBSERVED", "DERIVED", "DEFERRED"}
        for spec in MASTER_SCHEMA:
            assert spec.category in known, (
                f"Column '{spec.name}' has unknown category '{spec.category}'"
            )

    def test_all_sources_are_non_empty_strings(self):
        for spec in MASTER_SCHEMA:
            assert isinstance(spec.source, str) and spec.source.strip(), (
                f"Column '{spec.name}' has empty source field"
            )


class TestEmptyMasterDataframe:

    def test_returns_dataframe(self):
        df = empty_master_dataframe()
        assert isinstance(df, pd.DataFrame)

    def test_has_zero_rows(self):
        df = empty_master_dataframe()
        assert len(df) == 0

    def test_has_all_schema_columns(self):
        df = empty_master_dataframe()
        for col in COLUMN_NAMES:
            assert col in df.columns, f"Column '{col}' missing from empty_master_dataframe()"

    def test_no_extra_columns(self):
        df = empty_master_dataframe()
        extra = [c for c in df.columns if c not in COLUMN_NAMES]
        assert extra == [], f"Unexpected extra columns: {extra}"

    def test_calling_twice_returns_independent_copies(self):
        df1 = empty_master_dataframe()
        df2 = empty_master_dataframe()
        # Modifying one should not affect the other
        df1["station_id"] = pd.array(["TEST"], dtype="string")
        assert len(df2) == 0
