# SPDX-License-Identifier: Apache-2.0
"""Regulatory edge-case validations for jurisdiction JSON rules.

These tests intentionally target boundary and non-happy-path scenarios
for tax lookup and capped deductions defined in jurisdiction profiles.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest

from coati_payroll.formula_engine import CalculationError, FormulaEngine


pytestmark = pytest.mark.release_validation
ROOT = Path(__file__).parents[1]


def _load_profile(filename: str) -> dict:
    return json.loads((ROOT / "coati_payroll" / "jurisdictions" / filename).read_text(encoding="utf-8"))


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _mx_isr_manual(salary: Decimal, tariff: list[dict]) -> Decimal:
    for row in tariff:
        min_v = Decimal(str(row["min"]))
        max_raw = row.get("max")
        max_v = None if max_raw is None else Decimal(str(max_raw))
        if salary >= min_v and (max_v is None or salary <= max_v):
            fixed = Decimal(str(row["fixed"]))
            rate = Decimal(str(row["rate"]))
            over = Decimal(str(row["over"]))
            return _q2(fixed + (salary - over) * rate)
    raise ValueError("No matching tax bracket for salary")


def _us_ss_manual(salary: Decimal, accumulated: Decimal, wage_base: Decimal, rate: Decimal) -> Decimal:
    remaining = max(Decimal("0.00"), wage_base - accumulated)
    taxable = min(salary, remaining)
    return _q2(taxable * rate)


def _india_annual_tax_manual(annual_taxable: Decimal, slabs: list[dict]) -> Decimal:
    for row in slabs:
        min_v = Decimal(str(row["min"]))
        max_raw = row.get("max")
        max_v = None if max_raw is None else Decimal(str(max_raw))
        if annual_taxable >= min_v and (max_v is None or annual_taxable <= max_v):
            fixed = Decimal(str(row["fixed"]))
            rate = Decimal(str(row["rate"]))
            over = Decimal(str(row["over"]))
            return _q2(fixed + (annual_taxable - over) * rate)
    raise ValueError("No matching annual slab")


def test_us_social_security_wage_base_crossing_uses_remaining_base_only():
    profile = _load_profile("us_2026.json")
    schema = profile["rules"]["social_security_employee"]["formula"]
    engine = FormulaEngine(schema)

    near_cap = engine.execute({"salario_bruto": "1000.00", "salario_acumulado": "184000.00"})
    assert near_cap["output"] == "31.00"

    at_cap = engine.execute({"salario_bruto": "1000.00", "salario_acumulado": "184500.00"})
    assert at_cap["output"] == "0.00"


def test_mexico_isr_table_is_continuous_at_7168_boundary():
    profile = _load_profile("mexico_2026.json")
    schema = profile["rules"]["income_tax"]["formula"]
    engine = FormulaEngine(schema)

    left = engine.execute({"salario_bruto": "7168.51"})
    right = engine.execute({"salario_bruto": "7168.52"})

    assert left["output"] == "420.95"
    assert right["output"] == "420.95"


def test_india_annual_slab_transition_is_continuous_at_800000_boundary():
    profile = _load_profile("india_2026_27.json")
    annual_slabs = profile["rules"]["income_tax"]["formula"]["tax_tables"]["annual_slabs"]
    schema = {
        "inputs": [{"name": "annual_taxable", "type": "decimal", "default": 0}],
        "steps": [{"name": "annual_tax", "type": "tax_lookup", "table": "annual_slabs", "input": "annual_taxable"}],
        "tax_tables": {"annual_slabs": annual_slabs},
        "output": "annual_tax",
    }
    engine = FormulaEngine(schema)

    left = engine.execute({"annual_taxable": "800000.00"})
    right = engine.execute({"annual_taxable": "800000.01"})

    assert left["output"] == "20000.00"
    assert right["output"] == "20000.00"


def test_mexico_negative_income_raises_no_bracket_error():
    profile = _load_profile("mexico_2026.json")
    schema = profile["rules"]["income_tax"]["formula"]
    engine = FormulaEngine(schema)

    with pytest.raises(CalculationError, match="No tax bracket"):
        engine.execute({"salario_bruto": "-1.00"})


def test_brazil_inss_above_ceiling_must_use_capped_contribution_amount():
    profile = _load_profile("brazil_2026.json")
    schema = profile["rules"]["inss_employee"]["formula"]
    engine = FormulaEngine(schema)

    # Legal behavior: contribution should be capped at the ceiling amount when
    # salary exceeds the INSS top base, not fail due to missing bracket.
    # Max bracket amount = 411.1122 + (8475.55 - 4354.27) * 0.14 = 988.09.
    result = engine.execute({"salario_bruto": "9000.00"})
    assert Decimal(result["output"]) == Decimal("988.09")


@pytest.mark.parametrize(
    "salary,expected",
    [
        ("10000.00", "729.02"),
        ("12598.02", "1011.68"),
        ("12598.03", "1011.68"),
    ],
)
def test_mexico_manual_expected_matches_engine(salary: str, expected: str):
    profile = _load_profile("mexico_2026.json")
    schema = profile["rules"]["income_tax"]["formula"]
    tariff = schema["tax_tables"]["monthly_tariff"]
    engine = FormulaEngine(schema)

    salary_d = Decimal(salary)
    manual_expected = _mx_isr_manual(salary_d, tariff)
    assert manual_expected == Decimal(expected)

    engine_result = Decimal(engine.execute({"salario_bruto": salary})["output"])
    assert engine_result == manual_expected


@pytest.mark.parametrize(
    "salary,accumulated,expected",
    [
        ("1000.00", "184000.00", "31.00"),
        ("0.02", "184499.99", "0.00"),
        ("1000.00", "184500.00", "0.00"),
    ],
)
def test_us_social_security_manual_expected_matches_engine(salary: str, accumulated: str, expected: str):
    profile = _load_profile("us_2026.json")
    schema = profile["rules"]["social_security_employee"]["formula"]
    engine = FormulaEngine(schema)

    inputs_by_name = {item["name"]: item for item in schema["inputs"]}
    wage_base = Decimal(str(inputs_by_name["wage_base"]["default"]))
    rate = Decimal(str(inputs_by_name["employee_rate"]["default"]))
    manual_expected = _us_ss_manual(Decimal(salary), Decimal(accumulated), wage_base, rate)
    assert manual_expected == Decimal(expected)

    engine_result = Decimal(engine.execute({"salario_bruto": salary, "salario_acumulado": accumulated})["output"])
    assert engine_result == manual_expected


@pytest.mark.parametrize(
    "annual_taxable,expected",
    [
        ("400000.00", "0.00"),
        ("800000.00", "20000.00"),
        ("1200000.00", "60000.00"),
        ("2400000.00", "300000.00"),
    ],
)
def test_india_annual_tax_manual_expected_matches_engine(annual_taxable: str, expected: str):
    profile = _load_profile("india_2026_27.json")
    annual_slabs = profile["rules"]["income_tax"]["formula"]["tax_tables"]["annual_slabs"]
    schema = {
        "inputs": [{"name": "annual_taxable", "type": "decimal", "default": 0}],
        "steps": [{"name": "annual_tax", "type": "tax_lookup", "table": "annual_slabs", "input": "annual_taxable"}],
        "tax_tables": {"annual_slabs": annual_slabs},
        "output": "annual_tax",
    }
    engine = FormulaEngine(schema)

    manual_expected = _india_annual_tax_manual(Decimal(annual_taxable), annual_slabs)
    assert manual_expected == Decimal(expected)

    engine_result = Decimal(engine.execute({"annual_taxable": annual_taxable})["output"])
    assert engine_result == manual_expected


def test_us_profile_must_include_federal_income_withholding_rule():
    profile = _load_profile("us_2026.json")
    rules = profile["rules"]

    # Compliance expectation: US payroll validation scope must include federal
    # income tax withholding (W-4 / Publication 15-T), not only FICA.
    assert "federal_income_tax" in rules


def test_mexico_profile_must_include_imss_and_infonavit_employee_rules():
    profile = _load_profile("mexico_2026.json")
    rules = profile["rules"]

    # Compliance expectation: Mexico payroll profile must include employee-side
    # IMSS and INFONAVIT calculations in addition to ISR.
    assert "imss_employee" in rules
    assert "infonavit_employee" in rules


def test_india_profile_must_include_esi_employee_rule():
    profile = _load_profile("india_2026_27.json")
    rules = profile["rules"]

    # Compliance expectation: India payroll profile should include ESI when the
    # validation issue scope explicitly references EPF/ESI.
    assert "esi_employee" in rules
