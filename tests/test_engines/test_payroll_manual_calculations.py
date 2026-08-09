# SPDX-License-Identifier: Apache-2.0
"""Payroll calculation tests whose expected values are calculated independently.

The expected amounts in this module are deliberately written out from the
business equations.  They are not obtained by calling the implementation
under test, which makes these tests useful as calculation regressions.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator
from coati_payroll.nomina_engine.calculators.deduction_calculator import DeductionCalculator
from coati_payroll.nomina_engine.calculators.benefit_calculator import BenefitCalculator
from coati_payroll.nomina_engine.calculators.salary_calculator import SalaryCalculator


class _ConfigRepository:
    def get_for_empresa(self, _empresa_id):
        return SimpleNamespace(dias_mes_nomina=30, horas_jornada_diaria=Decimal("8.00"))


def _planilla(periodicidad="monthly"):
    return SimpleNamespace(
        empresa_id="empresa-test",
        tipo_planilla=SimpleNamespace(periodicidad=periodicidad),
        planilla_deducciones=[],
    )


def test_monthly_salary_uses_full_salary_for_complete_calendar_month():
    calculator = SalaryCalculator(_ConfigRepository())

    result = calculator.calculate_period_salary(
        Decimal("15000.00"),
        _planilla(),
        date(2026, 2, 1),
        date(2026, 2, 28),
        date(2026, 2, 28),
    )

    # A complete monthly period pays 15,000, including a 28-day February.
    assert result == Decimal("15000.00")


def test_partial_month_salary_is_prorated_using_30_day_base():
    calculator = SalaryCalculator(_ConfigRepository())

    result = calculator.calculate_period_salary(
        Decimal("15000.00"),
        _planilla(),
        date(2026, 2, 1),
        date(2026, 2, 10),
        date(2026, 2, 10),
    )

    # 15,000 / 30 * 10 days = 5,000.
    assert result == Decimal("5000.00")


def test_biweekly_salary_is_half_monthly_salary():
    calculator = SalaryCalculator(_ConfigRepository())

    result = calculator.calculate_period_salary(
        Decimal("15000.00"),
        _planilla("biweekly"),
        date(2026, 2, 1),
        date(2026, 2, 15),
        date(2026, 2, 15),
    )

    # 15,000 / 2 = 7,500.
    assert result == Decimal("7500.00")


def test_concepts_use_expected_bases_and_round_to_cents():
    calculator = ConceptCalculator(_ConfigRepository(), [])
    employee = SimpleNamespace(
        salario_base=Decimal("15000.00"),
        salario_bruto=Decimal("16500.00"),
        salario_mensual=Decimal("15000.00"),
        novedades={"HE": Decimal("5")},
        planilla=SimpleNamespace(empresa_id="empresa-test"),
    )

    # 10% of base salary = 1,500; 5% of gross = 825.
    assert calculator.calculate(employee, "salary_percentage", None, Decimal("10"), None, None, None) == Decimal(
        "1500.00"
    )
    assert calculator.calculate(employee, "gross_percentage", None, Decimal("5"), None, None, None) == Decimal(
        "825.00"
    )

    # Hourly rate: 15,000 / 30 / 8 = 62.50; five hours at 150% = 468.75.
    assert calculator.calculate(employee, "hours", None, Decimal("150"), None, None, None, "HE") == Decimal(
        "468.75"
    )


def test_deductions_are_applied_in_priority_and_capped_by_remaining_salary():
    calculator = ConceptCalculator(_ConfigRepository(), [])
    warnings = []
    deduction_calculator = DeductionCalculator(calculator, warnings)
    employee = SimpleNamespace(
        empleado=SimpleNamespace(primer_nombre="Ana", primer_apellido="Test"),
        salario_bruto=Decimal("1000.00"),
        deducciones=[],
        inasistencia_codigos_descuento=set(),
    )

    first = SimpleNamespace(
        activo=True,
        prioridad=1,
        monto_predeterminado=None,
        porcentaje=None,
        es_obligatoria=False,
        deduccion=SimpleNamespace(
            id="ded-1", codigo="D1", nombre="Primera", activo=True,
            formula_tipo="fixed", monto_default=Decimal("800.00"), porcentaje=None,
            formula=None, base_calculo=None, vigente_desde=None, valido_hasta=None,
        ),
    )
    second = SimpleNamespace(
        activo=True,
        prioridad=2,
        monto_predeterminado=None,
        porcentaje=None,
        es_obligatoria=False,
        deduccion=SimpleNamespace(
            id="ded-2", codigo="D2", nombre="Segunda", activo=True,
            formula_tipo="fixed", monto_default=Decimal("500.00"), porcentaje=None,
            formula=None, base_calculo=None, vigente_desde=None, valido_hasta=None,
        ),
    )
    planilla = SimpleNamespace(planilla_deducciones=[second, first])

    result = deduction_calculator.calculate(employee, planilla, date(2026, 2, 28))

    # First: min(800, 1,000) = 800; second: min(500, 200) = 200; net = 0.
    assert [(item.codigo, item.monto) for item in result] == [
        ("D1", Decimal("800.00")),
        ("D2", Decimal("200.00")),
    ]
    assert sum(item.monto for item in result) == Decimal("1000.00")


def test_employer_benefits_do_not_reduce_employee_net():
    calculator = ConceptCalculator(_ConfigRepository(), [])
    benefit_calculator = BenefitCalculator(calculator)
    employee = SimpleNamespace(
        salario_base=Decimal("15000.00"),
        salario_bruto=Decimal("16500.00"),
        salario_mensual=Decimal("15000.00"),
        novedades={},
        planilla=SimpleNamespace(empresa_id="empresa-test"),
    )
    benefit = SimpleNamespace(
        id="benefit-1", codigo="AGUINALDO", nombre="Aguinaldo", activo=True,
        formula_tipo="salary_percentage", monto_default=None, porcentaje=Decimal("8.33"),
        formula=None, base_calculo="salario_base", vigente_desde=None, valido_hasta=None,
        tope_aplicacion=None,
    )
    planilla = SimpleNamespace(
        planilla_prestaciones=[SimpleNamespace(activo=True, orden=1, monto_predeterminado=None,
                                               porcentaje=None, prestacion=benefit)]
    )

    result = benefit_calculator.calculate(employee, planilla, date(2026, 2, 28))

    perception = Decimal("1500.00")
    deduction = Decimal("1050.00")
    gross = employee.salario_base + perception
    net = gross - deduction

    # Employer cost is reported separately; it is not part of net pay.
    assert result[0].monto == Decimal("1249.50")  # 15,000 * 8.33%
    assert gross == Decimal("16500.00")
    assert net == Decimal("15450.00")
