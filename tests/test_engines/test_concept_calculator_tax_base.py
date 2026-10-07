# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Regression tests for taxable-base deduction classification."""

from decimal import Decimal
from types import SimpleNamespace

from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator
from coati_payroll.nomina_engine.domain.calculation_items import DeduccionItem


def test_tax_with_before_tax_flag_does_not_reduce_the_taxable_base_again():
    """A retained tax is not a pre-tax deduction even when its default flag is true."""
    calculator = ConceptCalculator(config_repository=None, warnings=[])
    calculator.deducciones_snapshot = {
        "seguro": {"antes_impuesto": True, "es_impuesto": False},
        "impuesto": {"antes_impuesto": True, "es_impuesto": True},
    }
    employee_calculation = SimpleNamespace(
        deducciones=[
            DeduccionItem(
                codigo="SEGURO",
                nombre="Seguro social",
                monto=Decimal("100.00"),
                prioridad=1,
                es_obligatoria=True,
                deduccion_id="seguro",
            ),
            DeduccionItem(
                codigo="IR",
                nombre="Impuesto",
                monto=Decimal("50.00"),
                prioridad=2,
                es_obligatoria=True,
                deduccion_id="impuesto",
            ),
        ]
    )

    assert calculator._calculate_pre_tax_deductions(employee_calculation) == Decimal("100.00")


def test_percentage_with_salario_gravable_base_calculo():
    """ConceptCalculator calculates percentage on salario_gravable when base_calculo is specified."""
    calculator = ConceptCalculator(config_repository=None, warnings=[])
    emp = SimpleNamespace(
        salario_base=Decimal("10000.00"),
        salario_gravable=Decimal("15000.00"),
        salario_bruto=Decimal("18000.00"),
        salario_neto=Decimal("12000.00"),
        novedades={},
    )
    # INSS Laboral (7%) on salario_gravable (15,000 * 0.07 = 1,050.00)
    result = calculator.calculate(
        emp_calculo=emp,
        formula_tipo="PORCENTAJE",
        monto_default=None,
        porcentaje=Decimal("7.00"),
        formula=None,
        monto_override=None,
        porcentaje_override=None,
        codigo_concepto="INSS_LABORAL",
        base_calculo="salario_gravable",
    )
    assert result == Decimal("1050.00")


def test_percentage_with_salario_bruto_base_calculo():
    """ConceptCalculator calculates percentage on salario_bruto when base_calculo is specified."""
    calculator = ConceptCalculator(config_repository=None, warnings=[])
    emp = SimpleNamespace(
        salario_base=Decimal("10000.00"),
        salario_gravable=Decimal("15000.00"),
        salario_bruto=Decimal("20000.00"),
        salario_neto=Decimal("12000.00"),
        novedades={},
    )
    result = calculator.calculate(
        emp_calculo=emp,
        formula_tipo="PORCENTAJE",
        monto_default=None,
        porcentaje=Decimal("10.00"),
        formula=None,
        monto_override=None,
        porcentaje_override=None,
        codigo_concepto="DED_BRUTO",
        base_calculo="salario_bruto",
    )
    assert result == Decimal("2000.00")


def test_fixed_concept_uses_period_novelty():
    """ConceptCalculator with FormulaType.FIJO returns the registered novelty amount."""
    calculator = ConceptCalculator(config_repository=None, warnings=[])
    emp = SimpleNamespace(
        salario_base=Decimal("10000.00"),
        salario_gravable=Decimal("10000.00"),
        salario_bruto=Decimal("10000.00"),
        novedades={"COMISIONES": Decimal("2500.50")},
    )
    result = calculator.calculate(
        emp_calculo=emp,
        formula_tipo="FIJO",
        monto_default=Decimal("0.00"),
        porcentaje=None,
        formula=None,
        monto_override=None,
        porcentaje_override=None,
        codigo_concepto="COMISIONES",
    )
    assert result == Decimal("2500.50")
