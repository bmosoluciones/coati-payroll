# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for TableLookup strict/non-strict behavior."""

from decimal import Decimal

import pytest

from coati_payroll.formula_engine import CalculationError
from coati_payroll.formula_engine.tables.table_lookup import TableLookup


class TestTableLookupStrictMode:
    """Tests for strict mode fail-closed behavior in TableLookup."""

    def test_empty_table_strict_raises(self):
        lookup = TableLookup({"tax_table": []}, strict_mode=True)
        with pytest.raises(CalculationError, match="empty"):
            lookup.lookup("tax_table", Decimal("100"))

    def test_unordered_table_strict_raises(self):
        lookup = TableLookup(
            {
                "tax_table": [
                    {"min": 100000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                ]
            },
            strict_mode=True,
        )
        with pytest.raises(CalculationError, match="not ordered"):
            lookup.lookup("tax_table", Decimal("150000"))

    def test_overlapping_brackets_strict_raises(self):
        lookup = TableLookup(
            {
                "tax_table": [
                    {"min": 0, "max": 200000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000, "max": 300000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
            strict_mode=True,
        )
        with pytest.raises(CalculationError, match="Multiple tax brackets match"):
            lookup.lookup("tax_table", Decimal("150000"))

    def test_contiguous_brackets_share_boundary_without_failing_strict_mode(self):
        """A boundary accepted by the validator must be executable in strict mode."""
        lookup = TableLookup(
            {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
            strict_mode=True,
        )

        result = lookup.lookup("tax_table", Decimal("100000"))

        assert result["rate"] == Decimal("0.15")
        assert result["tax"] == Decimal("0.00")

    def test_no_bracket_strict_raises(self):
        lookup = TableLookup(
            {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                ]
            },
            strict_mode=True,
        )
        with pytest.raises(CalculationError, match="No tax bracket found"):
            lookup.lookup("tax_table", Decimal("-1"))

    def test_empty_table_non_strict_returns_zeroes(self):
        lookup = TableLookup({"tax_table": []}, strict_mode=False)
        result = lookup.lookup("tax_table", Decimal("100"))
        assert result == {
            "tax": Decimal("0"),
            "rate": Decimal("0"),
            "fixed": Decimal("0"),
            "over": Decimal("0"),
        }
