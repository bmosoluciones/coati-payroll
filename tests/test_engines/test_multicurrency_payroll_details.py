# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive test suite for multi-currency payroll calculations.

This module validates that the payroll engine correctly handles payrolls where
employees are paid in a different currency than the payroll currency.
It tests basic conversion, missing exchange rate errors, multiple coexistence
currencies, snapshot rate usage, and multi-currency interactions with absences and deductions.
"""

from datetime import date
from decimal import Decimal

from coati_payroll.enums import NominaEstado
from coati_payroll.model import (
    Empleado,
    Empresa,
    Moneda,
    Planilla,
    PlanillaEmpleado,
    TipoCambio,
    TipoPlanilla,
    Deduccion,
    PlanillaDeduccion,
)
from coati_payroll.vistas.planilla.services.nomina_service import NominaService


def setup_multicurrency_base(db_session):
    """Helper to setup basic company, currencies and payroll type."""
    # Create currencies
    nio = Moneda(codigo="NIO", nombre="Córdoba Nicaragüense", simbolo="C$", activo=True)
    usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True)
    eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True)
    db_session.add_all([nio, usd, eur])
    db_session.flush()

    # Create company
    empresa = Empresa(
        codigo="TEST-MC-CORP",
        razon_social="MultiCurrency Test Corporation",
        ruc="J-9999999999-2026",
        activo=True,
    )
    db_session.add(empresa)
    db_session.flush()

    # Create monthly payroll type
    tipo_planilla = TipoPlanilla(
        codigo="MENSUAL-MC",
        descripcion="Mensual MultiCurrency",
        periodicidad="monthly",
        dias=30,
        periodos_por_anio=12,
        mes_inicio_fiscal=1,
        dia_inicio_fiscal=1,
        activo=True,
    )
    db_session.add(tipo_planilla)
    db_session.flush()

    return empresa, nio, usd, eur, tipo_planilla


def test_multicurrency_basic_conversion(app, db_session):
    """Test normal conversion: Employee in USD, Payroll in NIO."""
    with app.app_context():
        empresa, nio, usd, _, tipo_planilla = setup_multicurrency_base(db_session)

        # Exchange rate: 1 USD = 36.50 NIO
        exchange_rate = TipoCambio(
            fecha=date(2026, 3, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=nio.id,
            tasa=Decimal("36.50"),
            creado_por="admin-test",
        )
        db_session.add(exchange_rate)

        # Create employee with USD salary (1,500 USD monthly)
        empleado = Empleado(
            codigo_empleado="EMP-USD-BASE",
            primer_nombre="Alice",
            primer_apellido="Smith",
            identificacion_personal="001-010191-0001X",
            empresa_id=empresa.id,
            salario_base=Decimal("1500.00"),
            moneda_id=usd.id,
            activo=True,
            fecha_alta=date(2026, 1, 1),
        )
        db_session.add(empleado)
        db_session.flush()

        # Create planilla in NIO (payroll currency is NIO)
        planilla = Planilla(
            nombre="Planilla NIO Alice",
            tipo_planilla_id=tipo_planilla.id,
            empresa_id=empresa.id,
            moneda_id=nio.id,
            activo=True,
        )
        db_session.add(planilla)
        db_session.flush()

        # Associate employee to payroll
        pe = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
        db_session.add(pe)
        db_session.commit()

        # Execute payroll
        nomina, errors, _warnings = NominaService.ejecutar_nomina(
            planilla=planilla,
            periodo_inicio=date(2026, 3, 1),
            periodo_fin=date(2026, 3, 31),
            fecha_calculo=date(2026, 3, 31),
            usuario="admin-test",
        )

        assert nomina is not None
        assert len(errors) == 0

        # Verify converted values
        assert len(nomina.nomina_empleados) == 1
        ne = nomina.nomina_empleados[0]
        assert ne.empleado_id == empleado.id
        assert ne.moneda_origen_id == usd.id
        assert ne.tipo_cambio_aplicado == Decimal("36.50")

        # Converted monthly base: 1,500 USD * 36.50 = 54,750.00 NIO
        assert ne.sueldo_base_historico == Decimal("54750.00")
        assert ne.salario_bruto == Decimal("54750.00")
        assert ne.salario_neto == Decimal("54750.00")


def test_multicurrency_missing_rate_fails(app, db_session):
    """Test that missing exchange rate raises a validation/calculation error."""
    with app.app_context():
        empresa, nio, usd, _, tipo_planilla = setup_multicurrency_base(db_session)

        # Do NOT add exchange rate in the DB!

        # Create employee with USD salary
        empleado = Empleado(
            codigo_empleado="EMP-USD-ERROR",
            primer_nombre="Bob",
            primer_apellido="NoRate",
            identificacion_personal="001-010191-0002Y",
            empresa_id=empresa.id,
            salario_base=Decimal("1000.00"),
            moneda_id=usd.id,
            activo=True,
            fecha_alta=date(2026, 1, 1),
        )
        db_session.add(empleado)
        db_session.flush()

        # Create planilla in NIO
        planilla = Planilla(
            nombre="Planilla NIO Bob",
            tipo_planilla_id=tipo_planilla.id,
            empresa_id=empresa.id,
            moneda_id=nio.id,
            activo=True,
        )
        db_session.add(planilla)
        db_session.flush()

        pe = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
        db_session.add(pe)
        db_session.commit()

        # Execute payroll
        nomina, errors, _warnings = NominaService.ejecutar_nomina(
            planilla=planilla,
            periodo_inicio=date(2026, 3, 1),
            periodo_fin=date(2026, 3, 31),
            fecha_calculo=date(2026, 3, 31),
            usuario="admin-test",
        )

        # Execution should catch the error and log it in `errors`
        assert nomina is not None
        assert nomina.estado == NominaEstado.ERROR
        assert len(errors) > 0
        assert any("No se encontró tipo de cambio" in err for err in errors)


def test_multicurrency_multiple_employees(app, db_session):
    """Test coexistence of multiple currencies in a single payroll run."""
    with app.app_context():
        empresa, nio, usd, eur, tipo_planilla = setup_multicurrency_base(db_session)

        # Exchange rates:
        # 1 USD = 36.50 NIO
        rate_usd = TipoCambio(
            fecha=date(2026, 3, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=nio.id,
            tasa=Decimal("36.50"),
            creado_por="admin-test",
        )
        # 1 EUR = 40.00 NIO
        rate_eur = TipoCambio(
            fecha=date(2026, 3, 1),
            moneda_origen_id=eur.id,
            moneda_destino_id=nio.id,
            tasa=Decimal("40.00"),
            creado_por="admin-test",
        )
        db_session.add_all([rate_usd, rate_eur])

        # Alice: USD
        emp_usd = Empleado(
            codigo_empleado="EMP-COEX-USD",
            primer_nombre="Alice",
            primer_apellido="USD",
            identificacion_personal="001-010191-0003Z",
            empresa_id=empresa.id,
            salario_base=Decimal("1000.00"),  # 1,000 USD
            moneda_id=usd.id,
            activo=True,
            fecha_alta=date(2026, 1, 1),
        )
        # Charles: EUR
        emp_eur = Empleado(
            codigo_empleado="EMP-COEX-EUR",
            primer_nombre="Charles",
            primer_apellido="EUR",
            identificacion_personal="001-010191-0004A",
            empresa_id=empresa.id,
            salario_base=Decimal("800.00"),  # 800 EUR
            moneda_id=eur.id,
            activo=True,
            fecha_alta=date(2026, 1, 1),
        )
        # Daniel: NIO
        emp_nio = Empleado(
            codigo_empleado="EMP-COEX-NIO",
            primer_nombre="Daniel",
            primer_apellido="NIO",
            identificacion_personal="001-010191-0005B",
            empresa_id=empresa.id,
            salario_base=Decimal("20000.00"),  # 20,000 NIO
            moneda_id=nio.id,
            activo=True,
            fecha_alta=date(2026, 1, 1),
        )
        db_session.add_all([emp_usd, emp_eur, emp_nio])
        db_session.flush()

        # Create planilla in NIO
        planilla = Planilla(
            nombre="Planilla NIO Coexistence",
            tipo_planilla_id=tipo_planilla.id,
            empresa_id=empresa.id,
            moneda_id=nio.id,
            activo=True,
        )
        db_session.add(planilla)
        db_session.flush()

        # Associate all three
        db_session.add(PlanillaEmpleado(planilla_id=planilla.id, empleado_id=emp_usd.id, activo=True))
        db_session.add(PlanillaEmpleado(planilla_id=planilla.id, empleado_id=emp_eur.id, activo=True))
        db_session.add(PlanillaEmpleado(planilla_id=planilla.id, empleado_id=emp_nio.id, activo=True))
        db_session.commit()

        # Execute
        nomina, errors, _warnings = NominaService.ejecutar_nomina(
            planilla=planilla,
            periodo_inicio=date(2026, 3, 1),
            periodo_fin=date(2026, 3, 31),
            fecha_calculo=date(2026, 3, 31),
            usuario="admin-test",
        )

        assert nomina is not None
        assert len(errors) == 0

        # Verify employees
        ne_map = {ne.empleado_id: ne for ne in nomina.nomina_empleados}
        assert len(ne_map) == 3

        # Alice (USD): 1,000 USD * 36.50 = 36,500.00 NIO
        ne_usd = ne_map[emp_usd.id]
        assert ne_usd.tipo_cambio_aplicado == Decimal("36.50")
        assert ne_usd.salario_bruto == Decimal("36500.00")

        # Charles (EUR): 800 EUR * 40.00 = 32,000.00 NIO
        ne_eur = ne_map[emp_eur.id]
        assert ne_eur.tipo_cambio_aplicado == Decimal("40.00")
        assert ne_eur.salario_bruto == Decimal("32000.00")

        # Daniel (NIO): 20,000 NIO * 1.00 = 20,000.00 NIO
        ne_nio = ne_map[emp_nio.id]
        assert ne_nio.tipo_cambio_aplicado == Decimal("1.00")
        assert ne_nio.salario_bruto == Decimal("20000.00")

        # Verify Nomina grand totals: 36,500 + 32,000 + 20,000 = 88,500.00 NIO
        assert nomina.total_bruto == Decimal("88500.00")
        assert nomina.total_neto == Decimal("88500.00")


def test_multicurrency_uses_snapshot_rates(app, db_session):
    """Test that engine prefers rates stored in snapshot for calculation immutability."""
    with app.app_context():
        empresa, nio, usd, _, tipo_planilla = setup_multicurrency_base(db_session)

        # Exchange rate in DB: 1 USD = 36.50 NIO
        exchange_rate = TipoCambio(
            fecha=date(2026, 3, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=nio.id,
            tasa=Decimal("36.50"),
            creado_por="admin-test",
        )
        db_session.add(exchange_rate)

        # Create employee with USD salary
        empleado = Empleado(
            codigo_empleado="EMP-USD-SNAP",
            primer_nombre="Eve",
            primer_apellido="Snapshot",
            identificacion_personal="001-010191-0006C",
            empresa_id=empresa.id,
            salario_base=Decimal("1000.00"),
            moneda_id=usd.id,
            activo=True,
            fecha_alta=date(2026, 1, 1),
        )
        db_session.add(empleado)
        db_session.flush()

        # Create planilla in NIO
        planilla = Planilla(
            nombre="Planilla NIO Eve",
            tipo_planilla_id=tipo_planilla.id,
            empresa_id=empresa.id,
            moneda_id=nio.id,
            activo=True,
        )
        db_session.add(planilla)
        db_session.flush()

        pe = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
        db_session.add(pe)
        db_session.commit()

        # 1. Execute initial payroll to capture snapshot
        nomina, errors, _warnings = NominaService.ejecutar_nomina(
            planilla=planilla,
            periodo_inicio=date(2026, 3, 1),
            periodo_fin=date(2026, 3, 31),
            fecha_calculo=date(2026, 3, 31),
            usuario="admin-test",
        )
        assert nomina is not None
        assert len(errors) == 0

        ne = nomina.nomina_empleados[0]
        assert ne.tipo_cambio_aplicado == Decimal("36.50")
        assert ne.salario_bruto == Decimal("36500.00")

        # Now, modify the exchange rate in the DB to 37.00
        exchange_rate.tasa = Decimal("37.00")
        db_session.commit()

        # 2. Recalculate using the previous payroll's snapshots
        # Force use of snapshot captured previously
        db_session.refresh(nomina)
        assert nomina.tipos_cambio_snapshot is not None
        assert usd.id in nomina.tipos_cambio_snapshot

        # Verify get_exchange_rate returns 36.50 from snapshot, not 37.00 from modified DB
        from coati_payroll.nomina_engine.calculators.exchange_rate_calculator import ExchangeRateCalculator
        from coati_payroll.nomina_engine.repositories.exchange_rate_repository import ExchangeRateRepository

        rate_repo = ExchangeRateRepository(db_session)
        calc = ExchangeRateCalculator(rate_repo)

        resolved_rate = calc.get_exchange_rate(
            empleado=empleado,
            planilla=planilla,
            fecha_calculo=date(2026, 3, 31),
            tipos_cambio_snapshot=nomina.tipos_cambio_snapshot,
        )

        assert resolved_rate == Decimal("36.50")


def test_multicurrency_with_absences_and_deductions(app, db_session):
    """Test multi-currency with absences (prorated) and percentage deductions."""
    with app.app_context():
        empresa, nio, usd, _, tipo_planilla = setup_multicurrency_base(db_session)

        # Exchange rate: 1 USD = 36.50 NIO
        exchange_rate = TipoCambio(
            fecha=date(2026, 3, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=nio.id,
            tasa=Decimal("36.50"),
            creado_por="admin-test",
        )
        db_session.add(exchange_rate)

        # Create percentage deduction (10% on salary_base)
        deduccion = Deduccion(
            codigo="DED-PCT",
            nombre="Deducción 10%",
            formula_tipo="percentage",
            porcentaje=Decimal("10.00"),
            activo=True,
        )
        db_session.add(deduccion)
        db_session.flush()

        # Alice: 1,000 USD monthly. Starts mid-month (March 16), so has 16 days worked out of 31.
        empleado = Empleado(
            codigo_empleado="EMP-USD-ABS",
            primer_nombre="Alice",
            primer_apellido="Prorated",
            identificacion_personal="001-010191-0007D",
            empresa_id=empresa.id,
            salario_base=Decimal("1000.00"),
            moneda_id=usd.id,
            activo=True,
            fecha_alta=date(2026, 3, 16),  # Prorated!
        )
        db_session.add(empleado)
        db_session.flush()

        # Planilla with the deduction in NIO
        planilla = Planilla(
            nombre="Planilla NIO Alice Deductions",
            tipo_planilla_id=tipo_planilla.id,
            empresa_id=empresa.id,
            moneda_id=nio.id,
            activo=True,
        )
        db_session.add(planilla)
        db_session.flush()

        pd = PlanillaDeduccion(planilla_id=planilla.id, deduccion_id=deduccion.id, prioridad=1, activo=True)
        db_session.add(pd)

        pe = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
        db_session.add(pe)
        db_session.commit()

        # Execute
        nomina, errors, _warnings = NominaService.ejecutar_nomina(
            planilla=planilla,
            periodo_inicio=date(2026, 3, 1),
            periodo_fin=date(2026, 3, 31),
            fecha_calculo=date(2026, 3, 31),
            usuario="admin-test",
        )

        assert nomina is not None
        assert len(errors) == 0

        # Verify details
        ne = nomina.nomina_empleados[0]
        # Base conversion: 1,000 USD * 36.50 = 36,500.00 NIO monthly
        # Proration: starts March 16 -> 16 days worked. Total days in period = 31.
        # Monthly payroll base salary in period = 36,500.00 * (16 / 31) = 18,838.71 NIO
        expected_base = (Decimal("36500.00") * Decimal("16") / Decimal("31")).quantize(Decimal("0.01"))
        assert ne.sueldo_base_historico == expected_base

        # Deductions: 10% of 18,838.71 = 1,883.87 NIO
        expected_deductions = (expected_base * Decimal("0.10")).quantize(Decimal("0.01"))
        assert ne.total_deducciones == expected_deductions

        # Net salary = 18,838.71 - 1,883.87 = 16,954.84 NIO
        assert ne.salario_neto == expected_base - expected_deductions
