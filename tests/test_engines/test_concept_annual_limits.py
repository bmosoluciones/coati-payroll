"""Regression tests for native annual concept limits."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from coati_payroll.model import Percepcion
from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator
from coati_payroll.nomina_engine.calculators.deduction_calculator import DeductionCalculator
from coati_payroll.nomina_engine.calculators.perception_calculator import PerceptionCalculator


def test_annual_limit_only_applies_the_remaining_ytd_amount():
    amount = ConceptCalculator.apply_annual_limits(
        Decimal("100.00"),
        techo_anual=Decimal("250.00"),
        tope_base_gravable=None,
        acumulado_anual=Decimal("200.00"),
    )
    assert amount == Decimal("50.00")


def test_taxable_base_limit_applies_to_before_tax_deductions():
    amount = ConceptCalculator.apply_taxable_base_limit(
        Decimal("100.00"),
        tope_base_gravable=Decimal("250.00"),
        acumulado_base=Decimal("200.00"),
    )
    assert amount == Decimal("50.00")


def test_deduction_calculator_applies_taxable_base_limit():
    calculator = ConceptCalculator(config_repository=None, warnings=[])
    deduction_calculator = DeductionCalculator(calculator, [])
    deduction = SimpleNamespace(
        id="ded-1",
        codigo="DED",
        nombre="Deduction",
        activo=True,
        formula_tipo="fixed",
        monto_default=Decimal("100.00"),
        porcentaje=None,
        formula=None,
        base_calculo=None,
        vigente_desde=None,
        valido_hasta=None,
        techo_anual=None,
        tope_base_gravable=Decimal("250.00"),
        monto_exento=Decimal("0.00"),
        antes_impuesto=True,
    )
    association = SimpleNamespace(
        activo=True,
        prioridad=1,
        monto_predeterminado=None,
        porcentaje=None,
        es_obligatoria=False,
        detener_si_insuficiente=False,
        deduccion=deduction,
    )
    employee = SimpleNamespace(
        salario_bruto=Decimal("1000.00"),
        deducciones=[],
        inasistencia_codigos_descuento=set(),
        variables_calculo={"deducciones_antes_impuesto_acumulado": Decimal("200.00")},
        empleado=SimpleNamespace(primer_nombre="Test", primer_apellido="Employee"),
    )
    planilla = SimpleNamespace(planilla_deducciones=[association])

    result = deduction_calculator.calculate(employee, planilla, date(2026, 1, 31))

    assert [item.monto for item in result] == [Decimal("50.00")]


def test_exempt_amount_is_exposed_on_perception_item():
    calculator = PerceptionCalculator(SimpleNamespace(calculate=lambda *args, **kwargs: Decimal("100.00")))
    calculator.percepciones_snapshot = {"p1": {"monto_exento": "30.00"}}
    perception = Percepcion(
        id="p1",
        codigo="BONUS",
        nombre="Bonus",
        formula_tipo="fixed",
        monto_default=Decimal("100.00"),
        activo=True,
        gravable=True,
    )
    association = SimpleNamespace(
        activo=True, percepcion=perception, monto_predeterminado=None, porcentaje=None, orden=1
    )

    item = calculator._calculate_item(association, SimpleNamespace(variables_calculo={}), None)

    assert item is not None
    assert item.monto == Decimal("100.00")
    assert item.monto_exento == Decimal("30.00")
    assert item.monto_gravable == Decimal("70.00")


def test_taxable_base_ceiling_does_not_reduce_paid_perception():
    calculator = PerceptionCalculator(SimpleNamespace(calculate=lambda *args, **kwargs: Decimal("100.00")))
    calculator.percepciones_snapshot = {"p2": {"tope_base_gravable": "250.00"}}
    perception = Percepcion(
        id="p2",
        codigo="BONUS2",
        nombre="Bonus",
        formula_tipo="fixed",
        monto_default=Decimal("100.00"),
        activo=True,
        gravable=True,
    )
    association = SimpleNamespace(
        activo=True, percepcion=perception, monto_predeterminado=None, porcentaje=None, orden=1
    )

    item = calculator._calculate_item(
        association,
        SimpleNamespace(variables_calculo={"salario_gravable_acumulado": Decimal("200.00")}),
        None,
    )

    assert item is not None
    assert item.monto == Decimal("100.00")
    assert item.monto_gravable == Decimal("50.00")


def test_taxable_base_ceiling_includes_salary_and_previous_perceptions():
    calculator = PerceptionCalculator(SimpleNamespace(calculate=lambda *args, **kwargs: Decimal("100.00")))
    calculator.percepciones_snapshot = {
        "p3": {"tope_base_gravable": "250.00"},
        "p4": {"tope_base_gravable": "250.00"},
    }
    first = Percepcion(
        id="p3",
        codigo="BONUS3",
        nombre="Bonus 3",
        formula_tipo="fixed",
        monto_default=Decimal("100.00"),
        activo=True,
        gravable=True,
    )
    second = Percepcion(
        id="p4",
        codigo="BONUS4",
        nombre="Bonus 4",
        formula_tipo="fixed",
        monto_default=Decimal("100.00"),
        activo=True,
        gravable=True,
    )
    planilla = SimpleNamespace(
        planilla_percepciones=[
            SimpleNamespace(activo=True, percepcion=first, monto_predeterminado=None, porcentaje=None, orden=1),
            SimpleNamespace(activo=True, percepcion=second, monto_predeterminado=None, porcentaje=None, orden=2),
        ]
    )
    employee = SimpleNamespace(
        variables_calculo={"salario_gravable_acumulado": Decimal("0.00")},
        salario_neto_inasistencia=Decimal("100.00"),
    )

    items = calculator.calculate(employee, planilla, None)

    assert [item.monto_gravable for item in items] == [Decimal("100.00"), Decimal("50.00")]
