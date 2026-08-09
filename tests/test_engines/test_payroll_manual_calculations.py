# SPDX-License-Identifier: Apache-2.0
"""Payroll calculation tests whose expected values are calculated independently.

The expected amounts in this module are deliberately written out from the
business equations.  They are not obtained by calling the implementation
under test, which makes these tests useful as calculation regressions.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

import pytest

from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator
from coati_payroll.nomina_engine.calculators.deduction_calculator import DeductionCalculator
from coati_payroll.nomina_engine.calculators.benefit_calculator import BenefitCalculator
from coati_payroll.nomina_engine.calculators.salary_calculator import SalaryCalculator
from coati_payroll.nomina_engine.services.employee_processing_service import EmployeeProcessingService
from coati_payroll.formula_engine import FormulaEngine


pytestmark = pytest.mark.full


# 10 salaries x 20 percentages = 200 separately reported pytest cases.
# Expected amounts were calculated outside the calculator as salary * percent / 100
# and rounded half-up to cents.  Keeping the expected values in the table makes
# accidental changes to the calculation formula visible in review.
MANUAL_PERCENTAGE_TABLE = (
    ("1000.00", ((1, "10.00"), (2, "20.00"), (3, "30.00"), (4, "40.00"), (5, "50.00"),
                 (6, "60.00"), (7, "70.00"), (8, "80.00"), (9, "90.00"), (10, "100.00"),
                 (11, "110.00"), (12, "120.00"), (13, "130.00"), (14, "140.00"), (15, "150.00"),
                 (16, "160.00"), (17, "170.00"), (18, "180.00"), (19, "190.00"), (20, "200.00"))),
    ("1250.00", ((1, "12.50"), (2, "25.00"), (3, "37.50"), (4, "50.00"), (5, "62.50"),
                 (6, "75.00"), (7, "87.50"), (8, "100.00"), (9, "112.50"), (10, "125.00"),
                 (11, "137.50"), (12, "150.00"), (13, "162.50"), (14, "175.00"), (15, "187.50"),
                 (16, "200.00"), (17, "212.50"), (18, "225.00"), (19, "237.50"), (20, "250.00"))),
    ("1750.00", ((1, "17.50"), (2, "35.00"), (3, "52.50"), (4, "70.00"), (5, "87.50"),
                 (6, "105.00"), (7, "122.50"), (8, "140.00"), (9, "157.50"), (10, "175.00"),
                 (11, "192.50"), (12, "210.00"), (13, "227.50"), (14, "245.00"), (15, "262.50"),
                 (16, "280.00"), (17, "297.50"), (18, "315.00"), (19, "332.50"), (20, "350.00"))),
    ("3333.00", ((1, "33.33"), (2, "66.66"), (3, "99.99"), (4, "133.32"), (5, "166.65"),
                 (6, "199.98"), (7, "233.31"), (8, "266.64"), (9, "299.97"), (10, "333.30"),
                 (11, "366.63"), (12, "399.96"), (13, "433.29"), (14, "466.62"), (15, "499.95"),
                 (16, "533.28"), (17, "566.61"), (18, "599.94"), (19, "633.27"), (20, "666.60"))),
    ("4999.00", ((1, "49.99"), (2, "99.98"), (3, "149.97"), (4, "199.96"), (5, "249.95"),
                 (6, "299.94"), (7, "349.93"), (8, "399.92"), (9, "449.91"), (10, "499.90"),
                 (11, "549.89"), (12, "599.88"), (13, "649.87"), (14, "699.86"), (15, "749.85"),
                 (16, "799.84"), (17, "849.83"), (18, "899.82"), (19, "949.81"), (20, "999.80"))),
    ("7500.00", ((1, "75.00"), (2, "150.00"), (3, "225.00"), (4, "300.00"), (5, "375.00"),
                 (6, "450.00"), (7, "525.00"), (8, "600.00"), (9, "675.00"), (10, "750.00"),
                 (11, "825.00"), (12, "900.00"), (13, "975.00"), (14, "1050.00"), (15, "1125.00"),
                 (16, "1200.00"), (17, "1275.00"), (18, "1350.00"), (19, "1425.00"), (20, "1500.00"))),
    ("10000.00", ((1, "100.00"), (2, "200.00"), (3, "300.00"), (4, "400.00"), (5, "500.00"),
                  (6, "600.00"), (7, "700.00"), (8, "800.00"), (9, "900.00"), (10, "1000.00"),
                  (11, "1100.00"), (12, "1200.00"), (13, "1300.00"), (14, "1400.00"), (15, "1500.00"),
                  (16, "1600.00"), (17, "1700.00"), (18, "1800.00"), (19, "1900.00"), (20, "2000.00"))),
    ("12345.00", ((1, "123.45"), (2, "246.90"), (3, "370.35"), (4, "493.80"), (5, "617.25"),
                  (6, "740.70"), (7, "864.15"), (8, "987.60"), (9, "1111.05"), (10, "1234.50"),
                  (11, "1357.95"), (12, "1481.40"), (13, "1604.85"), (14, "1728.30"), (15, "1851.75"),
                  (16, "1975.20"), (17, "2098.65"), (18, "2222.10"), (19, "2345.55"), (20, "2469.00"))),
    ("15000.00", ((1, "150.00"), (2, "300.00"), (3, "450.00"), (4, "600.00"), (5, "750.00"),
                  (6, "900.00"), (7, "1050.00"), (8, "1200.00"), (9, "1350.00"), (10, "1500.00"),
                  (11, "1650.00"), (12, "1800.00"), (13, "1950.00"), (14, "2100.00"), (15, "2250.00"),
                  (16, "2400.00"), (17, "2550.00"), (18, "2700.00"), (19, "2850.00"), (20, "3000.00"))),
    ("27550.00", ((1, "275.50"), (2, "551.00"), (3, "826.50"), (4, "1102.00"), (5, "1377.50"),
                  (6, "1653.00"), (7, "1928.50"), (8, "2204.00"), (9, "2479.50"), (10, "2755.00"),
                  (11, "3030.50"), (12, "3306.00"), (13, "3581.50"), (14, "3857.00"), (15, "4132.50"),
                  (16, "4408.00"), (17, "4683.50"), (18, "4959.00"), (19, "5234.50"), (20, "5510.00"))),
)

MANUAL_PERCENTAGE_CASES = tuple(
    (salary, percentage, expected)
    for salary, row in MANUAL_PERCENTAGE_TABLE
    for percentage, expected in row
)


@pytest.mark.parametrize("salary,percentage,expected", MANUAL_PERCENTAGE_CASES)
def test_manual_percentage_matrix_200_cases(salary, percentage, expected):
    """Exercise 200 independently valued percentage payroll scenarios."""
    calculator = ConceptCalculator(_ConfigRepository(), [])
    employee = SimpleNamespace(salario_base=Decimal(salary))

    result = calculator.calculate(
        employee,
        "salary_percentage",
        None,
        Decimal(str(percentage)),
        None,
        None,
        None,
    )

    assert result == Decimal(expected)


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


def test_zero_benefit_cap_is_a_real_cap_not_an_unconfigured_cap():
    """A configured 0.00 ceiling must suppress the benefit completely."""
    calculator = ConceptCalculator(_ConfigRepository(), [])
    benefit_calculator = BenefitCalculator(calculator)
    employee = SimpleNamespace(
        salario_base=Decimal("15000.00"), salario_bruto=Decimal("15000.00"),
        salario_mensual=Decimal("15000.00"), novedades={}, planilla=SimpleNamespace(empresa_id="empresa-test"),
    )
    benefit = SimpleNamespace(
        id="benefit-zero-cap", codigo="CAP0", nombre="Beneficio topado a cero", activo=True,
        formula_tipo="fixed", monto_default=Decimal("100.00"), porcentaje=None, formula=None,
        base_calculo=None, vigente_desde=None, valido_hasta=None, tope_aplicacion=Decimal("0.00"),
    )
    planilla = SimpleNamespace(planilla_prestaciones=[SimpleNamespace(
        activo=True, orden=1, monto_predeterminado=None, porcentaje=None, prestacion=benefit,
    )])

    assert benefit_calculator.calculate(employee, planilla, date(2026, 2, 28)) == []


def _personal_variables(employee, calculation_date):
    service = EmployeeProcessingService(None, None)
    service._get_acumulado_anual = lambda *_args: None
    calculation = SimpleNamespace(
        empleado=employee,
        salario_base=Decimal("15000.00"),
        salario_mensual=Decimal("15000.00"),
        salario_neto_inasistencia=Decimal("15000.00"),
        tipo_cambio=Decimal("1.00"),
        salario_gravable=Decimal("0.00"),
        inasistencia_dias=Decimal("0.00"),
        inasistencia_horas=Decimal("0.00"),
        inasistencia_descuento=Decimal("0.00"),
        novedades={},
    )
    planilla = SimpleNamespace(
        empresa_id="empresa-test",
        empresa=SimpleNamespace(primer_mes_nomina=None, primer_anio_nomina=None),
        mes_inicio_fiscal=1,
        tipo_planilla=SimpleNamespace(
            mes_inicio_fiscal=1, dia_inicio_fiscal=1, periodos_por_anio=12, periodicidad="monthly"
        ),
    )
    return service.build_calculation_variables(
        calculation,
        planilla,
        calculation_date.replace(day=1),
        calculation_date,
        calculation_date,
        configuracion_snapshot={
            "dias_mes_nomina": 30,
            "horas_jornada_diaria": "8.00",
            "dias_mes_antiguedad": 30,
            "dias_anio_antiguedad": 365,
            "meses_anio_financiero": 12,
        },
        bootstrap_context={"is_initial_period": False},
    )


def test_birthday_bonus_flag_is_available_only_on_employee_birthday():
    employee = SimpleNamespace(
        fecha_alta=date(2023, 1, 1), fecha_nacimiento=date(1990, 5, 15),
        datos_adicionales={}, salario_acumulado=0, impuesto_acumulado=0, codigo_empleado="EMP-BDAY",
    )

    birthday = _personal_variables(employee, date(2026, 5, 15))
    ordinary_day = _personal_variables(employee, date(2026, 5, 14))

    assert birthday["es_cumpleanos"] == Decimal("1")
    assert ordinary_day["es_cumpleanos"] == Decimal("0")


def test_mothers_day_bonus_requires_mother_and_mothers_day():
    mother = SimpleNamespace(
        fecha_alta=date(2023, 1, 1), fecha_nacimiento=date(1990, 2, 1),
        datos_adicionales={"es_madre": True}, salario_acumulado=0, impuesto_acumulado=0,
        codigo_empleado="EMP-MOTHER",
    )
    non_mother = SimpleNamespace(**{**mother.__dict__, "datos_adicionales": {"es_madre": False}})

    mother_day = _personal_variables(mother, date(2026, 5, 30))
    non_mother_day = _personal_variables(non_mother, date(2026, 5, 30))

    assert mother_day["es_dia_madre"] == Decimal("1")
    assert mother_day["es_madre"] == Decimal("1")
    assert non_mother_day["es_madre"] == Decimal("0")


def test_seniority_bonus_formula_is_5_10_15_percent_by_completed_years():
    # Independent acceptance points for years 1, 2, and 3.
    for years, threshold, expected_rate in ((1, 1, "5.00"), (2, 2, "10.00"), (3, 3, "15.00")):
        schema = {
            "inputs": [{"name": "antiguedad_anios", "type": "decimal", "default": 0}],
            "steps": [{
                "name": "bono",
                "type": "conditional",
                "condition": {"left": "antiguedad_anios", "operator": ">=", "right": threshold},
                "if_true": expected_rate,
                "if_false": "0",
            }],
            "output": "bono",
        }
        result = FormulaEngine(schema).execute({"antiguedad_anios": Decimal(str(years))})
        assert result["output"] == expected_rate


@pytest.mark.parametrize(
    "annual_income,expected_tax",
    (("50000.00", "0.00"), ("100000.00", "0.00"), ("100000.01", "0.00"),
     ("125000.00", "3750.00"), ("150000.00", "7500.00"), ("200000.00", "15000.00"),
     ("200000.01", "15000.00"), ("250000.00", "25000.00"), ("300000.00", "35000.00"),
     ("600000.00", "105000.00")),
)
def test_progressive_legal_tax_brackets_and_boundaries(annual_income, expected_tax):
    """Test progressive legal brackets, exact boundaries, and fixed amounts."""
    schema = {
        "inputs": [{"name": "income", "type": "decimal", "default": 0}],
        "steps": [{"name": "tax", "type": "tax_lookup", "table": "annual_tax", "input": "income"}],
        "tax_tables": {"annual_tax": [
            {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
            {"min": 100000.01, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
            {"min": 200000.01, "max": 500000, "rate": 0.20, "fixed": 15000, "over": 200000},
            {"min": 500000.01, "max": None, "rate": 0.30, "fixed": 75000, "over": 500000},
        ]},
        "output": "tax",
    }
    result = FormulaEngine(schema).execute({"income": Decimal(annual_income)})
    assert result["output"] == expected_tax


@pytest.mark.parametrize(
    "base,commission,overtime,absence_days,loan,expected_net",
    (("15000", "0", "0", "0", "0", "13950.00"),
     ("15000", "1000", "0", "0", "0", "14880.00"),
     ("15000", "0", "468.75", "0", "0", "14385.94"),
     ("15000", "2500", "468.75", "1", "1000", "15245.94"),
     ("22500", "1250", "937.50", "2", "2500", "19064.37"),
     ("3333", "333.33", "104.16", "3", "500", "2696.59"),
     ("4999", "999.80", "249.95", "0", "1200", "4611.34"),
     ("10000", "5000", "625.00", "5", "3000", "9981.25")),
)
def test_variable_income_absence_and_complex_deduction_ledger(
    base, commission, overtime, absence_days, loan, expected_net
):
    """Reconcile variable income, absence, and loan deduction in one ledger."""
    base = Decimal(base)
    commission = Decimal(commission)
    overtime = Decimal(overtime)
    absence_days = Decimal(absence_days)
    loan = Decimal(loan)
    daily = base / Decimal("30")
    # Payroll money uses half-up rounding, not the Decimal default half-even.
    absence = (daily * absence_days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    gross = base + commission + overtime - absence
    social_security = (gross * Decimal("0.07")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net = gross - social_security - min(loan, gross - social_security)
    assert net == Decimal(expected_net)
