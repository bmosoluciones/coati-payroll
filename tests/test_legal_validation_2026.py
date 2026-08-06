# SPDX-License-Identifier: Apache-2.0
"""Independent legal-compliance checks for the 2026 jurisdiction rules.

Each test runs a jurisdiction's tax rule through the FormulaEngine with the
jurisdiction's own stress-case salary and compares the result against a value
derived by hand from the governing statute / official rate schedule (cited in
each case). The expectations are NOT derived from the JSON profiles, so these
guards fail whenever the configured rules diverge from the law.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from coati_payroll.formula_engine import FormulaEngine


pytestmark = pytest.mark.release_validation
ROOT = Path(__file__).parents[1]
CA = json.loads(
    (ROOT / "coati_payroll" / "jurisdictions" / "central_america_2026.json").read_text(encoding="utf-8")
)


def _profile(filename: str) -> dict:
    return json.loads((ROOT / "coati_payroll" / "jurisdictions" / filename).read_text(encoding="utf-8"))


def _tax_rule(profile: dict, rule: str, salary: Decimal) -> Decimal:
    engine = FormulaEngine(profile["rules"][rule]["formula"])
    return Decimal(engine.execute({"salario_bruto": str(salary)})["output"])


# ---------------------------------------------------------------------------
# Central America
# ---------------------------------------------------------------------------


def test_guatemala_isr_applies_extraordinary_deduction():
    """ISR sueldos 2026, salary Q10,000/month.

    Legal base = Q10,000 x 12 x (1 - 4.83% IGSS) - Q51,024
              = Q114,204 - Q51,024 = Q63,180 -> 5% = Q3,159.00/yr -> Q263.25/mo.
    The Q3,024 "deducción extraordinaria" (Decreto 13-2026) must be added to the
    Q48,000 annual exemption in force since the 2016 reform (Decreto 10-2012).
    """
    profile = CA["countries"]["GT"]
    expected = Decimal("263.25")
    assert _tax_rule(profile, "isr", Decimal(profile["stress_case"]["salary"])) == expected


def test_honduras_isr_2026_table():
    """ISR planilla 2026, salary L30,000/month (SAR-01-2026 table).

    Annual taxable = L30,000 x 12 x (1 - 2.5%) = L351,000.
    Bracket L348,154.11 - L809,660.75: 17,974.467 + 20% x (351,000 - 348,154.10)
      = 18,543.65 -> monthly = 1,545.30.
    """
    profile = CA["countries"]["HN"]
    expected = Decimal("1545.30")
    assert _tax_rule(profile, "isr", Decimal(profile["stress_case"]["salary"])) == expected


def test_nicaragua_ir_2026_table():
    """IR planilla 2026, salary C$30,000/month (DGI tabla 2026).

    Annual taxable = C$30,000 x 12 x (1 - 7% INSS) = C$334,800.
    Bracket C$200,000.01 - C$350,000: 15,000 + 20% x (334,800 - 200,000)
      = 41,960.00 -> monthly = 3,496.67.
    """
    profile = CA["countries"]["NI"]
    expected = Decimal("3496.67")
    assert _tax_rule(profile, "ir", Decimal(profile["stress_case"]["salary"])) == expected


@pytest.mark.parametrize(
    ("country", "rule", "months_remaining", "expected"),
    [
        ("HN", "isr", "11", "1273.99"),
        ("HN", "isr", "10", "962.64"),
        ("NI", "ir", "11", "3307.27"),
        ("NI", "ir", "10", "3080.00"),
    ],
)
def test_partial_year_withholding_matches_manual_projection(country, rule, months_remaining, expected):
    """Partial-year projections must not add the social deduction twice.

    HN: 30,000 x months x 97.5%, then the SAR table, divided by months.
    NI: 30,000 x months x 93%, then the DGI table, divided by months.
    """
    profile = CA["countries"][country]
    salary = Decimal(profile["stress_case"]["salary"])
    result = FormulaEngine(profile["rules"][rule]["formula"]).execute(
        {"salario_bruto": str(salary), "meses_restantes": months_remaining}
    )
    assert Decimal(result["output"]) == Decimal(expected)


def test_costa_rica_income_tax_uses_base_after_ccss():
    """ISR asalariado 2026, salary CRC1,000,000/month.

    CCSS empleado = 10.83% (SEM 5.50 + IVM 4.33 + Banco Popular 1.00) = CRC108,300.
    Taxable base = 1,000,000 - 108,300 = CRC891,700 <= CRC918,000 exempt band
    (Tramos Renta 2026) -> ISR = CRC0.00. Using the gross salary instead yields
    CRC8,200 and is wrong.
    """
    profile = CA["countries"]["CR"]
    expected = Decimal("0.00")
    assert _tax_rule(profile, "income_tax", Decimal(profile["stress_case"]["salary"])) == expected


def test_panama_income_tax_annualizes_by_13_with_css_and_se():
    """ISR planilla, salary B/.2,000/month (Código Fiscal Art. 700, DGI Planilla 03).

    Payroll withholding annualizes by 13 (12 months + XIII mes):
      gross annual  = 2,000 x 13 = 26,000
      CSS 9.75%     = 2,340 (on 12 monthly pays)
      CSS 7.25%     = 145   (on the décimo - special rate, not 9.75%)
      SE 1.25%      = 300   (on 12 pays only, not on the décimo)
      taxable       = 26,000 - 2,485 - 300 = 23,215
      tax           = 15% x (23,215 - 11,000) = 1,832.25
      monthly       = 1,832.25 / 12 = 152.69
    The profile still applies CSS 9.75% to all 13 pays (deducts 2,535), so this
    guard stays red until the differential décimo rate is modelled in the JSON.
    """
    profile = CA["countries"]["PA"]
    expected = Decimal("152.69")
    assert _tax_rule(profile, "income_tax", Decimal(profile["stress_case"]["salary"])) == expected


def test_el_salvador_isr_uses_base_after_isss_and_afp():
    """ISR planilla 2026, salary $1,000/month (Decreto Ejecutivo No. 10, mayo 2025).

    Base gravada = 1,000 - ISSS (3% capped at $30) - AFP (7.25%) = 1,000 - 30 - 72.50
                 = $897.50.
    Tramo III ($895.25 - $2,038.10): 60.00 + 20% x (897.50 - 895.24) = $60.45.
    The exempt band starts at $550 (not $472) and ISSS/AFP must be netted first.
    """
    profile = CA["countries"]["SV"]
    expected = Decimal("60.45")
    assert _tax_rule(profile, "isr", Decimal(profile["stress_case"]["salary"])) == expected


def test_belize_income_tax_2026_relief_and_marginal_credit():
    """Income tax 2026, salary BZ$2,500/month (Income Tax Act Cap. 56).

    Annual = BZ$30,000. Personal relief BZ$20,000 -> chargeable BZ$10,000.
    Flat 25% = BZ$2,500, reduced by the marginal relief credit
    2,250 - 0.75 x (30,000 - 29,000) = 1,500 -> BZ$1,000.00/yr -> BZ$83.33/mo.
    The first BZ$29,000 are effectively exempt; the relief is BZ$20,000 (not the
    outdated BZ$19,600).
    """
    profile = CA["countries"]["BZ"]
    expected = Decimal("83.33")
    assert _tax_rule(profile, "income_tax", Decimal(profile["stress_case"]["salary"])) == expected


# ---------------------------------------------------------------------------
# Mexico / India / Brazil
# ---------------------------------------------------------------------------


def test_mexico_income_tax_nets_employment_subsidy():
    """ISR sueldos 2026, salary MXN10,000/month.

    Tarifa mensual (Anexo 8 RMF 2026): MXN729.02.
    Subsidio para el empleo (cuota fija, DOF 01/05/2024): enero 2026
    3,439.46 (UMA 2025) x 15.59% = 536.21.
    Net ISR = 729.02 - 536.21 = MXN192.81 (feb-dic 2026: 535.65 -> 193.37).
    """
    profile = _profile("mexico_2026.json")
    expected = Decimal("192.81")
    assert _tax_rule(profile, "income_tax", Decimal(profile["stress_case"]["salary"])) == expected


def test_india_income_tax_new_regime_with_standard_deduction_and_rebate():
    """Income tax FY 2026-27 new regime (s. 115BAC), salary INR100,000/month.

    Annual = INR12,00,000. Standard deduction (s. 16(1a)) INR75,000
      -> taxable INR11,25,000. Slab tax = 20,000 + 10% x (11,25,000 - 800,000)
      = INR52,500. Rebate s. 87A (income <= INR12,00,000) -> tax = INR0.
    """
    profile = _profile("india_2026_27.json")
    expected = Decimal("0.00")
    assert _tax_rule(profile, "income_tax", Decimal(profile["stress_case"]["salary"])) == expected


def test_brazil_irrf_applies_simplified_discount():
    """IRRF 2026, salary R$5,000/month (Lei 15.270/2025).

    Desconto simplificado = 25% x 2,428.80 = R$607.20 -> base = 4,392.80.
    Base tax = 168.49875 + 22.5% x (4,392.80 - 3,751.05) = 312.89.
    Reduction (Lei 14.663/2023, updated 0.133145) = 978.62 - 0.133145 x 5,000
      = 312.90. IRRF = max(0, 312.89 - 312.90) = R$0.00.
    """
    profile = _profile("brazil_2026.json")
    expected = Decimal("0.00")
    assert _tax_rule(profile, "irrf_employee", Decimal(profile["stress_case"]["salary"])) == expected


# ---------------------------------------------------------------------------
# United States (no income-tax rule is configured; FICA is the check)
# ---------------------------------------------------------------------------


def test_us_fica_employee_contributions():
    """FICA 2026, salary USD10,000/month.

    Social Security 6.2% on the USD184,500 wage base = USD620.00.
    Medicare 1.45% = USD145.00. No cap on Medicare.
    """
    profile = _profile("us_2026.json")
    assert _tax_rule(profile, "social_security_employee", Decimal("10000.00")) == Decimal("620.00")
    assert _tax_rule(profile, "medicare_employee", Decimal("10000.00")) == Decimal("145.00")
