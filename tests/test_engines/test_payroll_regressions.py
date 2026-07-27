"""Regression tests for confirmed payroll calculation defects."""

from decimal import Decimal
from types import SimpleNamespace

from coati_payroll.enums import FormulaType
from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator


def test_explicit_zero_amount_override_disables_default_amount():
    """A planilla override of zero must not fall back to the concept default."""
    employee_calculation = SimpleNamespace(salario_base=Decimal("10000.00"))
    calculator = ConceptCalculator(config_repository=None, warnings=[])

    result = calculator.calculate(
        emp_calculo=employee_calculation,
        formula_tipo=FormulaType.FIJO,
        monto_default=Decimal("500.00"),
        porcentaje=None,
        formula=None,
        monto_override=Decimal("0.00"),
        porcentaje_override=None,
    )

    assert result == Decimal("0.00")


def test_explicit_zero_percentage_override_disables_percentage():
    """A planilla percentage override of zero must calculate zero."""
    employee_calculation = SimpleNamespace(salario_base=Decimal("10000.00"))
    calculator = ConceptCalculator(config_repository=None, warnings=[])

    result = calculator.calculate(
        emp_calculo=employee_calculation,
        formula_tipo=FormulaType.PORCENTAJE_SALARIO,
        monto_default=None,
        porcentaje=Decimal("10.00"),
        formula=None,
        monto_override=None,
        porcentaje_override=Decimal("0.00"),
    )

    assert result == Decimal("0.00")
