# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""End-to-end validation test for prestaciones accumulation."""

from datetime import date
from decimal import Decimal

import pytest

from coati_payroll.model import (
    Empleado,
    Empresa,
    Moneda,
    Planilla,
    PlanillaEmpleado,
    PlanillaPrestacion,
    Prestacion,
    PrestacionAcumulada,
    TipoPlanilla,
)
from coati_payroll.nomina_engine import ejecutar_nomina
from coati_payroll.vistas.planilla.nomina_routes import _aplicar_prestaciones_nomina


@pytest.mark.validation
def test_prestaciones_accumulation_workflow(app, db_session):
    """
    End-to-end validation: Prestaciones accumulation across multiple payroll runs.

    This comprehensive test validates the complete prestaciones accumulation workflow:
    1. Create an employee
    2. Create an annual accumulating prestacion (e.g., aguinaldo/13th month)
    3. Create a lifetime accumulating prestacion (e.g., severance/indemnización)
    4. Create a payroll linking the employee with the prestaciones
    5. Execute multiple payroll runs
    6. Verify that accumulation works correctly for each type

    Setup:
        - Create company, currency, payroll type, and employee
        - Create two prestaciones with different accumulation types
        - Link employee and prestaciones to payroll

    Action:
        - Execute 3 consecutive monthly payrolls

    Verification:
        - Annual prestacion accumulates across the year
        - Lifetime prestacion accumulates across all payrolls
        - Transaction records are created correctly
        - Running balances are calculated properly
    """
    with app.app_context():
        # ===== SETUP PHASE =====

        # Create a company
        empresa = Empresa(
            codigo="TEST-001",
            razon_social="Test Company S.A.",
            ruc="J-12345678-9",
            activo=True,
        )
        db_session.add(empresa)
        db_session.commit()

        # Create a currency (NIO - Córdoba)
        moneda = Moneda(
            codigo="NIO",
            nombre="Córdoba",
            simbolo="C$",
            activo=True,
        )
        db_session.add(moneda)
        db_session.commit()

        # Create a payroll type (monthly)
        tipo_planilla = TipoPlanilla(
            codigo="MENSUAL",
            descripcion="Planilla Mensual",
            dias=30,
            periodicidad="monthly",
            mes_inicio_fiscal=1,  # January
            dia_inicio_fiscal=1,
            acumula_anual=True,
            periodos_por_anio=12,
            activo=True,
        )
        db_session.add(tipo_planilla)
        db_session.commit()

        # Create an employee
        empleado = Empleado(
            primer_nombre="Juan",
            primer_apellido="Pérez",
            identificacion_personal="001-010180-0001A",
            salario_base=Decimal("15000.00"),
            fecha_alta=date(2024, 1, 1),
            activo=True,
            empresa_id=empresa.id,
            moneda_id=moneda.id,
        )
        db_session.add(empleado)
        db_session.commit()

        # Create annual accumulating prestacion (Aguinaldo/13th month)
        prestacion_anual = Prestacion(
            codigo="AGUINALDO",
            nombre="Aguinaldo - Treceavo Mes",
            descripcion="Provisión mensual para aguinaldo",
            tipo="bonus",
            tipo_acumulacion="annual",  # Accumulates annually
            formula_tipo="salary_percentage",
            porcentaje=Decimal("8.33"),  # 1/12 of annual salary
            base_calculo="salario_base",
            recurrente=True,
            activo=True,
        )
        db_session.add(prestacion_anual)
        db_session.commit()

        # Create lifetime accumulating prestacion (Indemnización/severance)
        prestacion_vida = Prestacion(
            codigo="INDEMNIZACION",
            nombre="Indemnización por Antigüedad",
            descripcion="Provisión por indemnización laboral",
            tipo="severance",
            tipo_acumulacion="lifetime",  # Accumulates over employment lifetime
            formula_tipo="salary_percentage",
            porcentaje=Decimal("8.33"),  # 1/12 of annual salary
            base_calculo="salario_base",
            recurrente=True,
            activo=True,
        )
        db_session.add(prestacion_vida)
        db_session.commit()

        # Create a payroll
        planilla = Planilla(
            nombre="Planilla Mensual Test",
            descripcion="Planilla para pruebas de acumulación",
            activo=True,
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa.id,
        )
        db_session.add(planilla)
        db_session.commit()

        # Link employee to payroll
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            activo=True,
            fecha_inicio=date(2024, 1, 1),
        )
        db_session.add(planilla_empleado)
        db_session.commit()

        # Link prestaciones to payroll
        planilla_prestacion_anual = PlanillaPrestacion(
            planilla_id=planilla.id,
            prestacion_id=prestacion_anual.id,
            activo=True,
            orden=1,
        )
        db_session.add(planilla_prestacion_anual)

        planilla_prestacion_vida = PlanillaPrestacion(
            planilla_id=planilla.id,
            prestacion_id=prestacion_vida.id,
            activo=True,
            orden=2,
        )
        db_session.add(planilla_prestacion_vida)
        db_session.commit()

        # ===== ACTION PHASE: Execute multiple payrolls =====

        # Calculate expected amounts for prestaciones
        # IMPORTANT: Full calendar months (1st to last day) use the full base salary
        # WITHOUT proration, regardless of whether the month has 28, 29, 30, or 31 days.
        # Only partial periods are prorated using dias=30 as divisor.
        import calendar

        def is_full_calendar_month(inicio, fin):
            """Check if the period spans a full calendar month (1st to last day)."""
            _, last_day = calendar.monthrange(inicio.year, inicio.month)
            return inicio.day == 1 and fin.day == last_day and inicio.month == fin.month and inicio.year == fin.year

        def calculate_prestacion_amount(base_salary, percentage, inicio, fin, standard_days=30):
            """Calculate prestacion amount considering full month vs partial period logic."""
            if is_full_calendar_month(inicio, fin):
                salary_for_period = base_salary
            else:
                days_in_period = (fin - inicio).days + 1
                salary_for_period = base_salary / Decimal(str(standard_days)) * Decimal(str(days_in_period))
            return salary_for_period * (percentage / Decimal("100"))

        # Execute 3 consecutive monthly payrolls (all full calendar months)
        payroll_dates = [
            (date(2024, 1, 1), date(2024, 1, 31), 31),  # January 2024 - full month
            (date(2024, 2, 1), date(2024, 2, 29), 29),  # February 2024 - full month (leap year)
            (date(2024, 3, 1), date(2024, 3, 31), 31),  # March 2024 - full month
        ]

        # Pre-calculate expected amounts for each period
        # Full months use full salary; partial periods are prorated by configured base days.
        expected_amounts_anual = []
        expected_amounts_vida = []
        for inicio, fin, days in payroll_dates:
            amount_anual = calculate_prestacion_amount(
                empleado.salario_base, prestacion_anual.porcentaje, inicio, fin, tipo_planilla.dias
            )
            amount_vida = calculate_prestacion_amount(
                empleado.salario_base, prestacion_vida.porcentaje, inicio, fin, tipo_planilla.dias
            )
            expected_amounts_anual.append(amount_anual)
            expected_amounts_vida.append(amount_vida)

        nominas_executed = []
        for inicio, fin, days in payroll_dates:
            # Commit all pending changes to ensure data is persisted
            db_session.commit()

            # Execute payroll within the same app/db context
            nomina, errors, warnings = ejecutar_nomina(
                planilla_id=planilla.id,
                periodo_inicio=inicio,
                periodo_fin=fin,
                fecha_calculo=fin,
                usuario="test_user",
            )

            # Verify no errors occurred
            assert len(errors) == 0, f"Errors during payroll execution: {errors}"
            assert nomina is not None, "Nomina should be created"

            # Side effects for prestaciones are deferred until payroll apply.
            nomina.estado = "approved"
            db_session.flush()
            _aplicar_prestaciones_nomina(nomina, planilla, "test_user")
            nomina.estado = "applied"
            db_session.commit()

            nominas_executed.append(nomina)

        # ===== VERIFICATION PHASE =====

        # Verify that 3 payrolls were executed
        assert len(nominas_executed) == 3, "Should have executed 3 payrolls"

        from sqlalchemy import select

        # Verify transactions were created for annual prestacion (Aguinaldo)
        transacciones_anual = (
            db_session.execute(
                select(PrestacionAcumulada)
                .filter(
                    PrestacionAcumulada.empleado_id == empleado.id,
                    PrestacionAcumulada.prestacion_id == prestacion_anual.id,
                )
                .order_by(PrestacionAcumulada.fecha_transaccion)
            )
            .unique()
            .scalars()
            .all()
        )

        assert len(transacciones_anual) == 3, "Should have 3 transactions for annual prestacion"

        # Verify annual prestacion accumulation
        # Each month adds to the balance - verify exact amounts
        running_balance_anual = Decimal("0.00")

        for i, trans in enumerate(transacciones_anual):
            expected_amount = expected_amounts_anual[i]

            assert trans.tipo_transaccion == "adicion", f"Transaction {i+1} should be 'adicion'"
            assert (
                trans.monto_transaccion == expected_amount
            ), f"Transaction {i+1} amount should be {expected_amount}, got {trans.monto_transaccion}"

            # Verify running balance calculation
            assert (
                trans.saldo_anterior == running_balance_anual
            ), f"Transaction {i+1} previous balance should be {running_balance_anual}, got {trans.saldo_anterior}"

            running_balance_anual += trans.monto_transaccion
            assert (
                trans.saldo_nuevo == running_balance_anual
            ), f"Transaction {i+1} new balance should be {running_balance_anual}, got {trans.saldo_nuevo}"

        from sqlalchemy import select

        # Verify transactions were created for lifetime prestacion (Indemnización)
        transacciones_vida = (
            db_session.execute(
                select(PrestacionAcumulada)
                .filter(
                    PrestacionAcumulada.empleado_id == empleado.id,
                    PrestacionAcumulada.prestacion_id == prestacion_vida.id,
                )
                .order_by(PrestacionAcumulada.fecha_transaccion)
            )
            .unique()
            .scalars()
            .all()
        )

        assert len(transacciones_vida) == 3, "Should have 3 transactions for lifetime prestacion"

        # Verify lifetime prestacion accumulation
        # Each month adds to the balance - verify exact amounts
        running_balance_vida = Decimal("0.00")

        for i, trans in enumerate(transacciones_vida):
            expected_amount = expected_amounts_vida[i]

            assert trans.tipo_transaccion == "adicion", f"Transaction {i+1} should be 'adicion'"
            assert (
                trans.monto_transaccion == expected_amount
            ), f"Transaction {i+1} amount should be {expected_amount}, got {trans.monto_transaccion}"

            # Verify running balance calculation
            assert (
                trans.saldo_anterior == running_balance_vida
            ), f"Transaction {i+1} previous balance should be {running_balance_vida}, got {trans.saldo_anterior}"

            running_balance_vida += trans.monto_transaccion
            assert (
                trans.saldo_nuevo == running_balance_vida
            ), f"Transaction {i+1} new balance should be {running_balance_vida}, got {trans.saldo_nuevo}"

        # Verify all transactions are linked to their source nominas
        for trans in transacciones_anual + transacciones_vida:
            assert trans.nomina_id is not None, "Transaction should be linked to a nomina"
            assert trans.nomina_id in [
                n.id for n in nominas_executed
            ], "Transaction should be linked to one of the executed nominas"

        # Verify transaction immutability (no updates to existing records)
        # All transactions should have unique IDs
        all_trans_ids = [t.id for t in transacciones_anual + transacciones_vida]
        assert len(all_trans_ids) == len(set(all_trans_ids)), "All transactions should have unique IDs (no updates)"

        # Verify year and month tracking
        for i, (inicio, fin, days) in enumerate(payroll_dates):
            # Check annual prestacion
            trans = transacciones_anual[i]
            assert trans.anio == fin.year, f"Transaction year should be {fin.year}"
            assert trans.mes == fin.month, f"Transaction month should be {fin.month}"

            # Check lifetime prestacion
            trans = transacciones_vida[i]
            assert trans.anio == fin.year, f"Transaction year should be {fin.year}"
            assert trans.mes == fin.month, f"Transaction month should be {fin.month}"

        # ===== SUCCESS =====
        print("\n✅ Prestaciones accumulation validation PASSED")
        print(f"   - Created {len(transacciones_anual)} transactions for annual prestacion")
        print(f"   - Created {len(transacciones_vida)} transactions for lifetime prestacion")
        print(f"   - Final balance for Aguinaldo: {transacciones_anual[-1].saldo_nuevo}")
        print(f"   - Final balance for Indemnización: {transacciones_vida[-1].saldo_nuevo}")
        print("   - All transactions properly linked to source nominas")
        print("   - Running balances calculated correctly")


@pytest.mark.validation
def test_prestaciones_monthly_settlement(app, db_session):
    """
    End-to-end validation: Monthly settlement prestaciones (e.g., INSS, INATEC).

    This test validates that prestaciones with tipo_acumulacion='mensual'
    reset their balance each month.

    Setup:
        - Create company, currency, payroll type, and employee
        - Create a monthly settlement prestacion
        - Link employee and prestacion to payroll

    Action:
        - Execute 3 consecutive monthly payrolls

    Verification:
        - Balance resets to zero at the start of each month
        - Each month's transaction shows correct previous balance of 0
    """
    with app.app_context():
        # ===== SETUP PHASE =====

        # Create company
        empresa = Empresa(
            codigo="TEST-002",
            razon_social="Test Company 2 S.A.",
            ruc="J-98765432-1",
            activo=True,
        )
        db_session.add(empresa)
        db_session.commit()

        # Create currency
        moneda = Moneda(
            codigo="USD",
            nombre="Dólar",
            simbolo="$",
            activo=True,
        )
        db_session.add(moneda)
        db_session.commit()

        # Create payroll type
        tipo_planilla = TipoPlanilla(
            codigo="MENSUAL-2",
            descripcion="Planilla Mensual 2",
            dias=30,
            periodicidad="monthly",
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            acumula_anual=True,
            periodos_por_anio=12,
            activo=True,
        )
        db_session.add(tipo_planilla)
        db_session.commit()

        # Create employee
        empleado = Empleado(
            primer_nombre="María",
            primer_apellido="González",
            identificacion_personal="002-020190-0002B",
            salario_base=Decimal("20000.00"),
            fecha_alta=date(2024, 1, 1),
            activo=True,
            empresa_id=empresa.id,
            moneda_id=moneda.id,
        )
        db_session.add(empleado)
        db_session.commit()

        # Create monthly settlement prestacion (INSS Patronal)
        prestacion_mensual = Prestacion(
            codigo="INSS_PATRONAL",
            nombre="INSS Patronal",
            descripcion="Seguro Social Patronal - Liquidación Mensual",
            tipo="social_security",
            tipo_acumulacion="monthly",  # Settles monthly
            formula_tipo="salary_percentage",
            porcentaje=Decimal("19.00"),  # 19% employer contribution
            base_calculo="salario_base",
            recurrente=True,
            activo=True,
        )
        db_session.add(prestacion_mensual)
        db_session.commit()

        # Create payroll
        planilla = Planilla(
            nombre="Planilla Test INSS",
            descripcion="Planilla para pruebas de liquidación mensual",
            activo=True,
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa.id,
        )
        db_session.add(planilla)
        db_session.commit()

        # Link employee to payroll
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            activo=True,
            fecha_inicio=date(2024, 1, 1),
        )
        db_session.add(planilla_empleado)
        db_session.commit()

        # Link prestacion to payroll
        planilla_prestacion = PlanillaPrestacion(
            planilla_id=planilla.id,
            prestacion_id=prestacion_mensual.id,
            activo=True,
            orden=1,
        )
        db_session.add(planilla_prestacion)
        db_session.commit()

        # ===== ACTION PHASE: Execute multiple payrolls =====

        # Note: The actual calculated amounts may differ slightly from simple percentage
        # due to prorating based on days worked in the period.

        # Execute 3 consecutive monthly payrolls
        payroll_dates = [
            (date(2024, 1, 1), date(2024, 1, 31)),  # January 2024
            (date(2024, 2, 1), date(2024, 2, 29)),  # February 2024
            (date(2024, 3, 1), date(2024, 3, 31)),  # March 2024
        ]

        for inicio, fin in payroll_dates:
            # Commit all pending changes before executing nomina
            db_session.commit()

            nomina, errors, warnings = ejecutar_nomina(
                planilla_id=planilla.id,
                periodo_inicio=inicio,
                periodo_fin=fin,
                fecha_calculo=fin,
                usuario="test_user",
            )

            assert len(errors) == 0, f"Errors during payroll execution: {errors}"
            assert nomina is not None, "Nomina should be created"
            nomina.estado = "approved"
            db_session.flush()
            _aplicar_prestaciones_nomina(nomina, planilla, "test_user")
            nomina.estado = "applied"
            db_session.commit()

        # ===== VERIFICATION PHASE =====

        from sqlalchemy import select

        # Verify transactions for monthly settlement prestacion
        transacciones = (
            db_session.execute(
                select(PrestacionAcumulada)
                .filter(
                    PrestacionAcumulada.empleado_id == empleado.id,
                    PrestacionAcumulada.prestacion_id == prestacion_mensual.id,
                )
                .order_by(PrestacionAcumulada.fecha_transaccion)
            )
            .unique()
            .scalars()
            .all()
        )

        assert len(transacciones) == 3, "Should have 3 transactions"

        # Verify monthly prestacion settlement behavior
        # For monthly settlement prestaciones, balance resets to zero each month
        for i, trans in enumerate(transacciones):
            assert trans.tipo_transaccion == "adicion", f"Transaction {i+1} should be 'adicion'"
            assert trans.monto_transaccion > Decimal("0"), f"Transaction {i+1} should have positive amount"

            # Monthly prestaciones reset each month, so previous balance should always be 0
            assert trans.saldo_anterior == Decimal("0.00"), f"Transaction {i+1} previous balance should be 0.00 (monthly reset)"

            # New balance equals the transaction amount (no accumulation from previous months)
            assert trans.saldo_nuevo == trans.monto_transaccion, f"Transaction {i+1} new balance should equal transaction amount"

        # ===== SUCCESS =====
        print("\n✅ Monthly prestacion settlement validation PASSED")
        print(f"   - Created {len(transacciones)} transactions")
        print(f"   - Each month resets to zero as expected")
        print(f"   - All transactions have correct settlement behavior")
