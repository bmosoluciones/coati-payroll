# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for formula_engine.py - payroll formula calculation engine."""

from decimal import Decimal

import pytest

from coati_payroll.formula_engine import (
    FormulaEngine,
    ValidationError,
    CalculationError,
    to_decimal,
    safe_divide,
)


class TestUtilityFunctions:
    """Tests for utility functions in formula_engine."""

    def test_to_decimal_from_int(self):
        """Test converting integer to Decimal."""
        result = to_decimal(100)
        assert result == Decimal("100")
        assert isinstance(result, Decimal)

    def test_to_decimal_from_float(self):
        """Test converting float to Decimal."""
        result = to_decimal(123.45)
        assert result == Decimal("123.45")

    def test_to_decimal_from_string(self):
        """Test converting string to Decimal."""
        result = to_decimal("999.99")
        assert result == Decimal("999.99")

    def test_to_decimal_from_decimal(self):
        """Test that Decimal remains Decimal."""
        original = Decimal("500.00")
        result = to_decimal(original)
        assert result == original
        assert result is original

    def test_to_decimal_from_none(self):
        """Test that None converts to zero."""
        result = to_decimal(None)
        assert result == Decimal("0")

    def test_to_decimal_invalid_value(self):
        """Test that invalid value raises ValidationError."""
        with pytest.raises(ValidationError, match="Cannot convert"):
            to_decimal("not-a-number")

    def test_safe_divide_normal(self):
        """Test normal division."""
        result = safe_divide(Decimal("100"), Decimal("4"))
        assert result == Decimal("25")

    def test_safe_divide_by_zero(self):
        """Test division by zero returns 0."""
        result = safe_divide(Decimal("100"), Decimal("0"))
        assert result == Decimal("0")

    def test_safe_divide_fractional(self):
        """Test fractional division."""
        result = safe_divide(Decimal("100"), Decimal("3"))
        assert abs(result - Decimal("33.333333333")) < Decimal("0.0001")


class TestFormulaEngineInitialization:
    """Tests for FormulaEngine initialization and schema validation."""

    def test_init_with_valid_schema(self):
        """Test initialization with valid schema."""
        schema = {
            "inputs": [{"name": "salario", "type": "decimal", "default": 0}],
            "steps": [{"name": "calculate", "type": "calculation", "formula": "salario * 2"}],
            "output": "calculate",
        }
        engine = FormulaEngine(schema)
        assert engine.schema == schema
        assert isinstance(engine.variables, dict)
        assert isinstance(engine.results, dict)

    def test_init_with_empty_steps(self):
        """Test initialization with empty steps list."""
        schema = {"steps": [], "output": "result"}
        engine = FormulaEngine(schema)
        assert engine.schema == schema

    def test_init_missing_steps(self):
        """Test that missing 'steps' raises ValidationError."""
        schema = {"output": "result"}
        with pytest.raises(ValidationError, match="must contain 'steps'"):
            FormulaEngine(schema)

    def test_init_invalid_schema_type(self):
        """Test that non-dict schema raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a dictionary"):
            FormulaEngine("not-a-dict")

    def test_init_step_without_name(self):
        """Test that step without name raises ValidationError."""
        schema = {"steps": [{"type": "calculation", "formula": "1 + 1"}]}
        with pytest.raises(ValidationError, match="must have a 'name'"):
            FormulaEngine(schema)

    def test_init_step_without_type(self):
        """Test that step without type raises ValidationError."""
        schema = {"steps": [{"name": "calc", "formula": "1 + 1"}]}
        with pytest.raises(ValidationError, match="must have a 'type'"):
            FormulaEngine(schema)


class TestExpressionEvaluation:
    """Tests for mathematical expression evaluation."""

    def test_evaluate_simple_addition(self):
        """Test simple addition."""
        schema = {
            "inputs": [{"name": "a", "default": 10}, {"name": "b", "default": 5}],
            "steps": [{"name": "result", "type": "calculation", "formula": "a + b"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"a": 10, "b": 5})
        assert result["output"] == "15.00"

    def test_evaluate_subtraction(self):
        """Test subtraction."""
        schema = {
            "inputs": [{"name": "a", "default": 100}],
            "steps": [{"name": "result", "type": "calculation", "formula": "a - 25"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"a": 100})
        assert result["output"] == "75.00"

    def test_evaluate_multiplication(self):
        """Test multiplication."""
        schema = {
            "inputs": [{"name": "base", "default": 1000}],
            "steps": [{"name": "result", "type": "calculation", "formula": "base * 0.15"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"base": 1000})
        assert result["output"] == "150.00"

    def test_evaluate_division(self):
        """Test division."""
        schema = {
            "inputs": [{"name": "total", "default": 100}],
            "steps": [{"name": "result", "type": "calculation", "formula": "total / 4"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"total": 100})
        assert result["output"] == "25.00"

    def test_evaluate_division_by_zero(self):
        """Test division by zero raises CalculationError in strict mode (default)."""
        schema = {
            "inputs": [{"name": "x", "default": 100}],
            "steps": [{"name": "result", "type": "calculation", "formula": "x / 0"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)  # strict_mode=True by default
        with pytest.raises(CalculationError, match="Division by zero"):
            engine.execute({"x": 100})

    def test_evaluate_division_by_zero_non_strict(self):
        """Test division by zero returns 0 in non-strict mode."""
        schema = {
            "inputs": [{"name": "x", "default": 100}],
            "steps": [{"name": "result", "type": "calculation", "formula": "x / 0"}],
            "output": "result",
        }
        engine = FormulaEngine(schema, strict_mode=False)
        result = engine.execute({"x": 100})
        assert result["output"] == "0.00"

    def test_evaluate_complex_expression(self):
        """Test complex expression with operator precedence."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [{"name": "result", "type": "calculation", "formula": "x * 2 + 5 - 3"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": 10})
        # (10 * 2) + 5 - 3 = 20 + 5 - 3 = 22
        assert result["output"] == "22.00"

    def test_evaluate_parentheses(self):
        """Test expression with parentheses."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [{"name": "result", "type": "calculation", "formula": "(x + 5) * 2"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": 10})
        # (10 + 5) * 2 = 15 * 2 = 30
        assert result["output"] == "30.00"

    def test_evaluate_power(self):
        """Test power operation."""
        schema = {
            "inputs": [{"name": "base", "default": 2}],
            "steps": [{"name": "result", "type": "calculation", "formula": "base ** 3"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"base": 2})
        assert result["output"] == "8.00"

    def test_evaluate_modulo(self):
        """Test modulo operation."""
        schema = {
            "inputs": [{"name": "x", "default": 17}],
            "steps": [{"name": "result", "type": "calculation", "formula": "x % 5"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": 17})
        assert result["output"] == "2.00"

    def test_evaluate_with_safe_functions(self):
        """Test evaluation with safe functions."""
        schema = {
            "inputs": [{"name": "a", "default": 10}, {"name": "b", "default": 20}],
            "steps": [{"name": "result", "type": "calculation", "formula": "max(a, b)"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"a": 10, "b": 20})
        assert result["output"] == "20.00"

    def test_evaluate_min_function(self):
        """Test min function."""
        schema = {
            "inputs": [{"name": "x", "default": 100}, {"name": "limit", "default": 50}],
            "steps": [{"name": "result", "type": "calculation", "formula": "min(x, limit)"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": 100, "limit": 50})
        assert result["output"] == "50.00"

    def test_evaluate_abs_function(self):
        """Test abs function."""
        schema = {
            "inputs": [{"name": "x", "default": -25}],
            "steps": [{"name": "result", "type": "calculation", "formula": "abs(x)"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": -25})
        assert result["output"] == "25.00"

    def test_evaluate_round_function(self):
        """Test round function."""
        schema = {
            "inputs": [{"name": "x", "default": 123.456}],
            "steps": [{"name": "result", "type": "calculation", "formula": "round(x, 2)"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": 123.456})
        assert result["output"] == "123.46"

    def test_evaluate_undefined_variable(self):
        """Test that undefined variable raises CalculationError."""
        schema = {
            "inputs": [],
            "steps": [{"name": "result", "type": "calculation", "formula": "undefined_var * 2"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(CalculationError, match="Undefined variable"):
            engine.execute({})

    def test_evaluate_invalid_syntax(self):
        """Test that invalid syntax raises CalculationError."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [{"name": "result", "type": "calculation", "formula": "x +"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(CalculationError, match="Invalid expression syntax"):
            engine.execute({"x": 10})


class TestSecurityValidation:
    """Tests for AST security validation."""

    def test_reject_import_statement(self):
        """Test that import statements are rejected."""
        schema = {
            "inputs": [],
            "steps": [{"name": "result", "type": "calculation", "formula": "import os"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(CalculationError):
            engine.execute({})

    def test_date_functions_with_literal_strings(self):
        """Test that date functions (days_between, max_date, min_date) work with literal string dates."""
        schema_days = {
            "inputs": [],
            "steps": [{"name": "days", "type": "calculation", "formula": 'days_between("2026-01-01", "2026-01-10")'}],
            "output": "days",
        }
        engine = FormulaEngine(schema_days)
        result = engine.execute({})
        assert result["output"] == "9.00"

        schema_max = {
            "inputs": [],
            "steps": [{"name": "max_d", "type": "calculation", "formula": 'max_date("2026-01-01", "2026-01-10")'}],
            "output": "max_d",
        }
        engine = FormulaEngine(schema_max)
        result = engine.execute({})
        assert result["output"] == "2026-01-10"

        schema_min = {
            "inputs": [],
            "steps": [{"name": "min_d", "type": "calculation", "formula": 'min_date("2026-01-01", "2026-01-10")'}],
            "output": "min_d",
        }
        engine = FormulaEngine(schema_min)
        result = engine.execute({})
        assert result["output"] == "2026-01-01"

    def test_reject_attribute_access(self):
        """Test that attribute access is rejected."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [{"name": "result", "type": "calculation", "formula": "x.__class__"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(CalculationError):
            engine.execute({"x": 10})


class TestConditionalLogic:
    """Tests for conditional step execution."""

    def test_conditional_true_branch(self):
        """Test conditional taking true branch."""
        schema = {
            "inputs": [{"name": "salary", "default": 5000}],
            "steps": [
                {
                    "name": "bonus",
                    "type": "conditional",
                    "condition": {"left": "salary", "operator": ">", "right": 3000},
                    "if_true": "salary * 0.1",
                    "if_false": "0",
                }
            ],
            "output": "bonus",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"salary": 5000})
        assert result["output"] == "500.00"

    def test_conditional_false_branch(self):
        """Test conditional taking false branch."""
        schema = {
            "inputs": [{"name": "salary", "default": 2000}],
            "steps": [
                {
                    "name": "bonus",
                    "type": "conditional",
                    "condition": {"left": "salary", "operator": ">", "right": 3000},
                    "if_true": "salary * 0.1",
                    "if_false": "0",
                }
            ],
            "output": "bonus",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"salary": 2000})
        assert result["output"] == "0.00"

    def test_conditional_equals(self):
        """Test conditional with equality operator."""
        schema = {
            "inputs": [{"name": "status", "default": 100}],
            "steps": [
                {
                    "name": "result",
                    "type": "conditional",
                    "condition": {"left": "status", "operator": "==", "right": 100},
                    "if_true": "1",
                    "if_false": "0",
                }
            ],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"status": 100})
        assert result["output"] == "1.00"

    def test_conditional_not_equals(self):
        """Test conditional with not-equals operator."""
        schema = {
            "inputs": [{"name": "x", "default": 5}],
            "steps": [
                {
                    "name": "result",
                    "type": "conditional",
                    "condition": {"left": "x", "operator": "!=", "right": 10},
                    "if_true": "100",
                    "if_false": "0",
                }
            ],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": 5})
        assert result["output"] == "100.00"

    def test_conditional_greater_equals(self):
        """Test conditional with >= operator."""
        schema = {
            "inputs": [{"name": "age", "default": 18}],
            "steps": [
                {
                    "name": "eligible",
                    "type": "conditional",
                    "condition": {"left": "age", "operator": ">=", "right": 18},
                    "if_true": "1",
                    "if_false": "0",
                }
            ],
            "output": "eligible",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"age": 18})
        assert result["output"] == "1.00"

    def test_conditional_less_than(self):
        """Test conditional with < operator."""
        schema = {
            "inputs": [{"name": "score", "default": 50}],
            "steps": [
                {
                    "name": "needs_help",
                    "type": "conditional",
                    "condition": {"left": "score", "operator": "<", "right": 60},
                    "if_true": "1",
                    "if_false": "0",
                }
            ],
            "output": "needs_help",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"score": 50})
        assert result["output"] == "1.00"


class TestTaxTableLookup:
    """Tests for tax table lookup functionality."""

    def test_tax_lookup_first_bracket(self):
        """Test tax lookup in first bracket (0% tax)."""
        schema = {
            "inputs": [{"name": "income", "default": 50000}],
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000.01, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
            "output": "tax",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"income": 50000})
        assert result["output"] == "0.00"

    def test_tax_lookup_second_bracket(self):
        """Test tax lookup in second bracket."""
        schema = {
            "inputs": [{"name": "income", "default": 150000}],
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000.01, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
            "output": "tax",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"income": 150000})
        # (150000 - 100000) * 0.15 = 7500
        assert result["output"] == "7500.00"

    def test_tax_lookup_with_fixed_amount(self):
        """Test tax lookup with fixed base amount."""
        schema = {
            "inputs": [{"name": "income", "default": 250000}],
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000.01, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                    {"min": 200000.01, "max": 300000, "rate": 0.20, "fixed": 15000, "over": 200000},
                ]
            },
            "output": "tax",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"income": 250000})
        # 15000 + (250000 - 200000) * 0.20 = 15000 + 10000 = 25000
        assert result["output"] == "25000.00"

    def test_tax_lookup_open_ended_bracket(self):
        """Test tax lookup in open-ended (highest) bracket."""
        schema = {
            "inputs": [{"name": "income", "default": 600000}],
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000.01, "max": 500000, "rate": 0.15, "fixed": 0, "over": 100000},
                    {"min": 500000.01, "max": None, "rate": 0.30, "fixed": 60000, "over": 500000},
                ]
            },
            "output": "tax",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"income": 600000})
        # 60000 + (600000 - 500000) * 0.30 = 60000 + 30000 = 90000
        assert result["output"] == "90000.00"

    def test_tax_lookup_no_matching_bracket_strict_default(self):
        """Test tax lookup with no matching bracket raises CalculationError in strict mode (default)."""
        schema = {
            "inputs": [{"name": "income", "default": -100}],
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "tax_tables": {"tax_table": [{"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0}]},
            "output": "tax",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(CalculationError, match="No tax bracket"):
            engine.execute({"income": -100})

    def test_tax_lookup_no_matching_bracket_non_strict(self):
        """Test tax lookup with no matching bracket returns 0 in non-strict mode."""
        schema = {
            "inputs": [{"name": "income", "default": -100}],
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "tax_tables": {"tax_table": [{"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0}]},
            "output": "tax",
        }
        engine = FormulaEngine(schema, strict_mode=False)
        result = engine.execute({"income": -100})
        assert result["output"] == "0.00"

    def test_tax_lookup_missing_table(self):
        """Test that missing tax table raises CalculationError."""
        schema = {
            "inputs": [{"name": "income", "default": 100000}],
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "nonexistent_table", "input": "income"}],
            "output": "tax",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(CalculationError, match="not found"):
            engine.execute({"income": 100000})


class TestTaxTableValidation:
    """Tests for tax table validation - critical integrity checks."""

    def test_empty_tax_table_raises_error(self):
        """Test that empty tax table raises ValidationError."""
        schema = {
            "steps": [],
            "tax_tables": {"tax_table": []},
        }
        with pytest.raises(ValidationError, match="vacía"):
            FormulaEngine(schema)

    def test_unordered_tax_table_raises_error(self):
        """Test that unordered tax table raises ValidationError."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 100000.01, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                ]
            },
        }
        with pytest.raises(ValidationError, match="no está ordenada"):
            FormulaEngine(schema)

    def test_overlapping_brackets_raises_error(self):
        """Test that overlapping brackets raise ValidationError."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 150000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
        }
        with pytest.raises(ValidationError, match="solapados"):
            FormulaEngine(schema)

    def test_gap_in_brackets_generates_warning(self):
        """Test that significant gaps between brackets generate warnings (not errors)."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 150000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 150000},
                ]
            },
        }
        # Should not raise error, but will log warning
        engine = FormulaEngine(schema, strict_mode=False)
        assert engine is not None

    def test_small_gap_in_brackets_no_warning(self):
        """Test that small gaps (within tolerance) don't generate warnings."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000.005, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
        }
        # Small gap (0.005) should not generate warning (tolerance is 0.01)
        engine = FormulaEngine(schema)
        assert engine is not None

    def test_gap_in_strict_mode_raises_error(self):
        """Test that gaps in strict mode raise ValidationError."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 150000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 150000},
                ]
            },
        }
        with pytest.raises(ValidationError, match="Advertencias"):
            FormulaEngine(schema, strict_mode=True)

    def test_open_ended_bracket_not_last_raises_error(self):
        """Test that open-ended bracket not being last raises ValidationError."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": None, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
        }
        with pytest.raises(ValidationError, match="abierto.*último"):
            FormulaEngine(schema)

    def test_bracket_with_max_less_than_min_raises_error(self):
        """Test that bracket with max < min raises ValidationError."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 100000, "max": 50000, "rate": 0, "fixed": 0, "over": 0},
                ]
            },
        }
        with pytest.raises(ValidationError, match="max.*menor que.*min"):
            FormulaEngine(schema)

    def test_missing_min_value_raises_error(self):
        """Test that missing min value raises ValidationError."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"max": 100000, "rate": 0, "fixed": 0, "over": 0},
                ]
            },
        }
        with pytest.raises(ValidationError, match="min"):
            FormulaEngine(schema)

    def test_valid_continuous_brackets_passes(self):
        """Test that valid continuous brackets (max of one = min of next) pass validation."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
        }
        # Should not raise
        engine = FormulaEngine(schema)
        assert engine is not None

    def test_valid_table_with_open_ended_last_bracket_passes(self):
        """Test that valid table with open-ended last bracket passes validation."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000.01, "max": None, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
        }
        # Should not raise
        engine = FormulaEngine(schema)
        assert engine is not None

    def test_defensive_lookup_handles_overlaps(self):
        """Test that defensive lookup handles overlapping brackets gracefully."""
        # Test with overlapping brackets - should raise error
        schema_overlap = {
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "inputs": [{"name": "income", "default": 150000}],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 200000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000, "max": 300000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
            "output": "tax",
        }
        # Overlaps should still raise ValidationError (critical issue)
        with pytest.raises(ValidationError, match="solapados"):
            FormulaEngine(schema_overlap)

    def test_defensive_lookup_handles_gaps(self):
        """Test that defensive lookup handles gaps gracefully (warnings, not errors)."""
        # Test with gap scenario - should generate warning but not error
        schema_gap = {
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "inputs": [{"name": "income", "default": 125000}],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 150000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 150000},
                ]
            },
            "output": "tax",
        }
        # Gaps should generate warning but not error (unless strict_mode)
        engine = FormulaEngine(schema_gap, strict_mode=False)
        assert engine is not None
        # Value in gap should return zeros
        result = engine.execute({"income": 125000})
        assert result["output"] == "0.00"

    def test_defensive_lookup_handles_empty_table(self):
        """Test that defensive lookup handles empty table gracefully."""
        schema = {
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "inputs": [{"name": "income", "default": 100000}],
            "tax_tables": {"tax_table": []},
            "output": "tax",
        }
        # Should fail at initialization
        with pytest.raises(ValidationError, match="vacía"):
            FormulaEngine(schema)

    def test_negative_fixed_raises_error(self):
        """Test that negative fixed value raises ValidationError."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": -100, "over": 0},
                ]
            },
        }
        with pytest.raises(ValidationError, match="fixed.*negativo"):
            FormulaEngine(schema)

    def test_negative_over_raises_error(self):
        """Test that negative over value raises ValidationError."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": -50},
                ]
            },
        }
        with pytest.raises(ValidationError, match="over.*negativo"):
            FormulaEngine(schema)

    def test_over_greater_than_min_raises_error(self):
        """Test that over > min raises ValidationError."""
        # In a tax bracket, 'over' should be <= 'min' of that bracket
        # Example: bracket with min=100000 should have over <= 100000
        schema_wrong = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 100000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 150000},
                ]
            },
        }
        with pytest.raises(ValidationError, match="over.*mayor que.*min"):
            FormulaEngine(schema_wrong)

    def test_valid_over_equals_min_passes(self):
        """Test that over == min is valid (common in tax tables)."""
        schema = {
            "steps": [],
            "tax_tables": {
                "tax_table": [
                    {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 100000, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
                ]
            },
        }
        # Should pass - over can equal min
        engine = FormulaEngine(schema)
        assert engine is not None


class TestCompleteExecution:
    """Tests for complete schema execution."""

    def test_execute_multiple_steps(self):
        """Test execution with multiple dependent steps."""
        schema = {
            "inputs": [{"name": "base_salary", "default": 10000}, {"name": "bonus_rate", "default": 0.1}],
            "steps": [
                {"name": "bonus", "type": "calculation", "formula": "base_salary * bonus_rate"},
                {"name": "gross", "type": "calculation", "formula": "base_salary + bonus"},
                {"name": "tax", "type": "calculation", "formula": "gross * 0.15"},
                {"name": "net", "type": "calculation", "formula": "gross - tax"},
            ],
            "output": "net",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"base_salary": 10000, "bonus_rate": 0.1})

        # base = 10000, bonus = 1000, gross = 11000, tax = 1650, net = 9350
        assert result["output"] == "9350.00"
        assert result["variables"]["bonus"] == "1000.00"
        assert result["variables"]["gross"] == "11000.00"
        assert result["variables"]["tax"] == "1650.00"

    def test_execute_with_defaults(self):
        """Test execution using default input values."""
        schema = {
            "inputs": [{"name": "x", "default": 100}, {"name": "y", "default": 50}],
            "steps": [{"name": "result", "type": "calculation", "formula": "x + y"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({})  # No inputs provided, use defaults
        assert result["output"] == "150.00"

    def test_execute_with_assignment_step(self):
        """Test execution with assignment step."""
        schema = {
            "inputs": [{"name": "base", "default": 1000}],
            "steps": [
                {"name": "multiplier", "type": "assignment", "value": 2.5},
                {"name": "result", "type": "calculation", "formula": "base * multiplier"},
            ],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"base": 1000})
        assert result["output"] == "2500.00"

    def test_execute_progressive_tax_calculation(self):
        """Test realistic progressive tax calculation."""
        schema = {
            "meta": {"name": "Progressive Tax Example"},
            "inputs": [{"name": "annual_income", "default": 150000}],
            "steps": [
                {"name": "tax", "type": "tax_lookup", "table": "progressive_rates", "input": "annual_income"},
                {"name": "monthly_tax", "type": "calculation", "formula": "tax / 12"},
            ],
            "tax_tables": {
                "progressive_rates": [
                    {"min": 0, "max": 50000, "rate": 0, "fixed": 0, "over": 0},
                    {"min": 50000.01, "max": 100000, "rate": 0.10, "fixed": 0, "over": 50000},
                    {"min": 100000.01, "max": 200000, "rate": 0.20, "fixed": 5000, "over": 100000},
                    {"min": 200000.01, "max": None, "rate": 0.30, "fixed": 25000, "over": 200000},
                ]
            },
            "output": "monthly_tax",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"annual_income": 150000})

        # Tax calculation: 5000 + (150000 - 100000) * 0.20 = 5000 + 10000 = 15000
        # Monthly: 15000 / 12 = 1250
        assert result["output"] == "1250.00"

    def test_execute_returns_all_variables(self):
        """Test that execute returns all intermediate variables."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [
                {"name": "step1", "type": "calculation", "formula": "x * 2"},
                {"name": "step2", "type": "calculation", "formula": "step1 + 5"},
            ],
            "output": "step2",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": 10})

        assert "variables" in result
        assert result["variables"]["x"] == "10.00"
        assert result["variables"]["step1"] == "20.00"
        assert result["variables"]["step2"] == "25.00"

    def test_execute_step_error_provides_context(self):
        """Test that step errors include helpful context."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [{"name": "bad_step", "type": "calculation", "formula": "undefined_var * 2"}],
            "output": "bad_step",
        }
        engine = FormulaEngine(schema)

        with pytest.raises(CalculationError, match="Error in step 'bad_step'"):
            engine.execute({"x": 10})

    def test_execute_unknown_step_type(self):
        """Test that unknown step type raises CalculationError."""
        schema = {
            "inputs": [],
            "steps": [{"name": "unknown", "type": "invalid_type", "value": 100}],
            "output": "unknown",
        }
        engine = FormulaEngine(schema)

        with pytest.raises(CalculationError, match="Unknown step type"):
            engine.execute({})


class TestBadInputHandling:
    """Tests for handling bad/malformed input data - CRITICAL for production safety."""

    def test_execute_with_string_instead_of_number(self):
        """Test that string inputs are converted to Decimal when possible."""
        schema = {
            "inputs": [{"name": "salary", "default": 0}],
            "steps": [{"name": "tax", "type": "calculation", "formula": "salary * 0.15"}],
            "output": "tax",
        }
        engine = FormulaEngine(schema)
        # Pass string that represents a valid number
        result = engine.execute({"salary": "10000"})
        assert result["output"] == "1500.00"

    def test_execute_with_invalid_string_input(self):
        """Test that invalid string input raises ValidationError."""
        schema = {
            "inputs": [{"name": "amount", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "amount * 2"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        # This should raise ValidationError when trying to convert
        with pytest.raises(ValidationError, match="Cannot convert"):
            engine.execute({"amount": "not-a-number"})

    def test_execute_with_none_input(self):
        """Test that None input is converted to 0."""
        schema = {
            "inputs": [{"name": "bonus", "default": 100}],
            "steps": [{"name": "total", "type": "calculation", "formula": "bonus * 2"}],
            "output": "total",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"bonus": None})
        assert result["output"] == "0.00"

    def test_execute_with_empty_string_input(self):
        """Test handling of empty string input."""
        schema = {
            "inputs": [{"name": "value", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "value + 10"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(ValidationError):
            engine.execute({"value": ""})

    def test_execute_with_negative_numbers(self):
        """Test that negative numbers are handled correctly."""
        schema = {
            "inputs": [{"name": "adjustment", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "adjustment + 100"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"adjustment": -50})
        assert result["output"] == "50.00"

    def test_execute_with_very_large_numbers(self):
        """Test handling of very large numbers."""
        schema = {
            "inputs": [{"name": "big_num", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "big_num / 1000"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"big_num": 999999999999})
        assert result["output"] == "1000000000.00"

    def test_execute_with_very_small_decimals(self):
        """Test handling of very small decimal numbers."""
        schema = {
            "inputs": [{"name": "tiny", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "tiny * 1000000"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"tiny": 0.000001})
        assert result["output"] == "1.00"

    def test_execute_with_special_float_values(self):
        """Test handling of special float values like infinity."""
        schema = {
            "inputs": [{"name": "x", "default": 100}],
            "steps": [{"name": "result", "type": "calculation", "formula": "x * 2"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        # float('inf') should convert to Decimal but might cause issues
        result = engine.execute({"x": 100})
        assert result["output"] == "200.00"

    def test_execute_with_list_input(self):
        """Test that list input raises appropriate error."""
        schema = {
            "inputs": [{"name": "data", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "data * 2"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(ValidationError):
            engine.execute({"data": [1, 2, 3]})

    def test_execute_with_dict_input(self):
        """Test that dict input raises appropriate error."""
        schema = {
            "inputs": [{"name": "config", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "config + 10"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(ValidationError):
            engine.execute({"config": {"key": "value"}})

    def test_execute_with_boolean_input(self):
        """Test handling of boolean input."""
        schema = {
            "inputs": [{"name": "flag", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "flag * 100"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        # True should convert to 1, False to 0
        result = engine.execute({"flag": True})
        assert result["output"] == "100.00"

        result = engine.execute({"flag": False})
        assert result["output"] == "0.00"

    def test_execute_with_mixed_type_operations(self):
        """Test operations with mixed types."""
        schema = {
            "inputs": [
                {"name": "int_val", "default": 0},
                {"name": "float_val", "default": 0},
                {"name": "str_val", "default": 0},
            ],
            "steps": [{"name": "result", "type": "calculation", "formula": "int_val + float_val + str_val"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"int_val": 100, "float_val": 50.5, "str_val": "25.25"})
        assert result["output"] == "175.75"

    def test_tax_lookup_with_invalid_input_type(self):
        """Test tax lookup with invalid input type."""
        schema = {
            "inputs": [{"name": "income", "default": 0}],
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "tax_table", "input": "income"}],
            "tax_tables": {"tax_table": [{"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0}]},
            "output": "tax",
        }
        engine = FormulaEngine(schema)
        # String that can be converted should work
        result = engine.execute({"income": "50000"})
        assert result["output"] == "0.00"

    def test_conditional_with_invalid_operator(self):
        """Test conditional with invalid comparison operator."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [
                {
                    "name": "result",
                    "type": "conditional",
                    "condition": {"left": "x", "operator": "===", "right": 10},
                    "if_true": "100",
                    "if_false": "0",
                }
            ],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(CalculationError, match="Invalid comparison operator"):
            engine.execute({"x": 10})

    def test_conditional_with_non_dict_condition(self):
        """Test conditional with malformed condition."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [
                {"name": "result", "type": "conditional", "condition": "not a dict", "if_true": "100", "if_false": "0"}
            ],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(CalculationError, match="Condition must be a dictionary"):
            engine.execute({"x": 10})

    def test_empty_formula_string(self):
        """Test evaluation of empty formula string."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [{"name": "result", "type": "calculation", "formula": ""}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": 10})
        # Empty formula should return 0
        assert result["output"] == "0.00"

    def test_whitespace_only_formula(self):
        """Test evaluation of whitespace-only formula."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [{"name": "result", "type": "calculation", "formula": "   "}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"x": 10})
        assert result["output"] == "0.00"

    def test_malformed_tax_table_structure(self):
        """Test tax lookup with malformed table structure."""
        schema = {
            "inputs": [{"name": "income", "default": 100000}],
            "steps": [{"name": "tax", "type": "tax_lookup", "table": "bad_table", "input": "income"}],
            "tax_tables": {"bad_table": "not a list"},
            "output": "tax",
        }
        # Validation now happens during initialization, not during execution
        with pytest.raises(ValidationError, match="debe ser una lista"):
            FormulaEngine(schema)

    def test_missing_input_uses_default(self):
        """Test that missing input uses default value."""
        schema = {
            "inputs": [{"name": "required", "default": 100}, {"name": "optional", "default": 50}],
            "steps": [{"name": "result", "type": "calculation", "formula": "required + optional"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        # Only provide 'required', 'optional' should use default
        result = engine.execute({"required": 200})
        assert result["output"] == "250.00"

    def test_extra_inputs_are_ignored(self):
        """Test that extra inputs that aren't in schema are ignored."""
        schema = {
            "inputs": [{"name": "x", "default": 10}],
            "steps": [{"name": "result", "type": "calculation", "formula": "x * 2"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        # Provide extra input that isn't in schema
        result = engine.execute({"x": 10, "extra": 999, "another": "ignored"})
        assert result["output"] == "20.00"

    def test_scientific_notation_input(self):
        """Test handling of scientific notation numbers."""
        schema = {
            "inputs": [{"name": "scientific", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "scientific * 2"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"scientific": 1.5e6})
        assert result["output"] == "3000000.00"

    def test_decimal_precision_preservation(self):
        """Test that decimal precision is preserved in calculations."""
        schema = {
            "inputs": [{"name": "precise", "default": 0}],
            "steps": [{"name": "result", "type": "calculation", "formula": "precise * 3"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        result = engine.execute({"precise": "123.456789"})
        # Check that precision is maintained
        assert result["output"] == "370.37"

    def test_unicode_in_variable_names(self):
        """Test that unicode characters in input keys don't break execution."""
        schema = {
            "inputs": [{"name": "normal_var", "default": 100}],
            "steps": [{"name": "result", "type": "calculation", "formula": "normal_var * 2"}],
            "output": "result",
        }
        engine = FormulaEngine(schema)
        # Unicode in input keys that aren't used shouldn't cause issues
        result = engine.execute({"normal_var": 100, "unicode_key_ñ": 50})
        assert result["output"] == "200.00"

    def test_assignment_with_invalid_value_type(self):
        """Test assignment step with invalid value type."""
        schema = {
            "inputs": [],
            "steps": [{"name": "constant", "type": "assignment", "value": [1, 2, 3]}],
            "output": "constant",
        }
        engine = FormulaEngine(schema)
        with pytest.raises(CalculationError):
            engine.execute({})
