# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""End-to-end test for vacation accrual during payroll execution.

This test simulates a complete user workflow:
1. Create a company
2. Create an employee with specific salary
3. Create a biweekly payroll
4. Associate payroll and employee to company
5. Create a vacation accrual rule
6. Associate vacation rule to payroll
7. Execute payroll
8. Validate salary payment, vacation accrual, and accounting liability
"""

from datetime import date
from decimal import Decimal

import pytest

from coati_payroll.model import (
    Empleado,
    Empresa,
    Moneda,
    Planilla,
    PlanillaEmpleado,
    TipoPlanilla,
    VacationAccount,
    VacationLedger,
    VacationPolicy,
    ComprobanteContable,
    ComprobanteContableLinea,
)
from coati_payroll.vistas.planilla.services.nomina_service import NominaService
from tests.helpers.auth import login_user


@pytest.mark.validation
def test_vacation_accrual_during_biweekly_payroll_execution(app, client, admin_user, db_session):
    """
    End-to-end test: Employee receives salary and accrues vacation days during payroll.

    Setup:
    - Employee salary: 30,000 monthly (1,000 daily)
    - Biweekly payroll (15 days)
    - Vacation rule: 2 days per month worked (periodic accrual)

    Expected results after biweekly payroll:
    - Salary payment: 15,000
    - Vacation days accrued: 1 day (2 days/month * 0.5 months)
    - Accounting liability: 1,000 (monthly salary 30,000 / 30 dias_base * 1 day accrued)
    """
    with app.app_context():
        # Step 1: Create company (empresa)
        empresa = Empresa(
            codigo="COMP001",
            razon_social="Empresa de Prueba S.A.",
            ruc="J-98765432-1",
            activo=True,
        )
        db_session.add(empresa)
        db_session.flush()

        # Create currency
        moneda = Moneda(
            codigo="NIO",
            nombre="Córdoba",
            simbolo="C$",
            activo=True,
        )
        db_session.add(moneda)
        db_session.flush()

        # Step 2: Create employee with 30,000 salary and 1,000 daily salary
        empleado = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP001",
            primer_nombre="Juan",
            primer_apellido="Pérez",
            identificacion_personal="001-010190-0001A",
            salario_base=Decimal("30000.00"),
            moneda_id=moneda.id,
            fecha_alta=date(2025, 1, 1),  # Employee started working in January
            activo=True,
        )
        db_session.add(empleado)
        db_session.flush()

        # Step 3: Create biweekly payroll (planilla quincenal)
        tipo_planilla = TipoPlanilla(
            codigo="QUINCENAL",
            descripcion="Planilla Quincenal",
            periodicidad="biweekly",
            dias=15,
            periodos_por_anio=24,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            activo=True,
        )
        db_session.add(tipo_planilla)
        db_session.flush()

        planilla = Planilla(
            nombre="Planilla Quincenal Prueba",
            tipo_planilla_id=tipo_planilla.id,
            empresa_id=empresa.id,
            moneda_id=moneda.id,
            activo=True,
            # Accounting configuration for base salary
            codigo_cuenta_debe_salario="5101",
            descripcion_cuenta_debe_salario="Gasto por Salario",
            codigo_cuenta_haber_salario="2101",
            descripcion_cuenta_haber_salario="Salario por Pagar",
        )
        db_session.add(planilla)
        db_session.flush()

        # Step 4: Associate payroll and employee to company
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        # Step 5: Create vacation accrual rule (2 paid vacation days per month worked)
        # For biweekly (15 days / 30 days per month = 0.5 months)
        # Expected accrual: 2 days/month * 0.5 = 1 day
        vacation_policy = VacationPolicy(
            codigo="VAC-POLICY-001",
            nombre="Vacaciones Pagadas - 2 días por mes",
            planilla_id=planilla.id,
            empresa_id=empresa.id,
            accrual_method="periodic",
            accrual_rate=Decimal("2.0000"),  # 2 days per period
            accrual_frequency="monthly",
            unit_type="days",
            min_service_days=0,
            allow_negative=False,
            son_vacaciones_pagadas=True,  # Mark as paid vacation for accounting
            porcentaje_pago_vacaciones=Decimal("100.00"),  # 100% of daily salary
            cuenta_debito_vacaciones_pagadas="5201",
            descripcion_cuenta_debito_vacaciones_pagadas="Gasto Vacaciones Pagadas",
            cuenta_credito_vacaciones_pagadas="2205",
            descripcion_cuenta_credito_vacaciones_pagadas="Pasivo Vacaciones por Pagar",
            activo=True,
        )
        db_session.add(vacation_policy)
        db_session.flush()

        # Step 6: Associate vacation rule to payroll (already done via planilla_id)
        # Create vacation account for employee
        vacation_account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=vacation_policy.id,
            current_balance=Decimal("0.00"),
            activo=True,
        )
        db_session.add(vacation_account)
        db_session.commit()

        # Step 7: Execute biweekly payroll
        periodo_inicio = date(2026, 2, 1)
        periodo_fin = date(2026, 2, 15)
        fecha_calculo = date(2026, 2, 15)

        nomina, errors, _warnings = NominaService.ejecutar_nomina(
            planilla=planilla,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            fecha_calculo=fecha_calculo,
            usuario=admin_user.usuario,
        )

        # Ensure nomina was created successfully
        assert nomina is not None, f"Nomina creation failed with errors: {errors}"
        assert len(errors) == 0, f"Unexpected errors: {errors}"

        # Step 8: Validate results
        db_session.refresh(nomina)

        # Validate 8.1: Salary payment of 15,000
        # Biweekly salary = 30,000 / 2 = 15,000
        assert nomina.total_bruto == Decimal("15000.00"), f"Expected total_bruto of 15,000.00, got {nomina.total_bruto}"
        assert nomina.total_neto == Decimal("15000.00"), f"Expected total_neto of 15,000.00, got {nomina.total_neto}"

        # Get NominaEmpleado record
        nomina_empleado = nomina.nomina_empleados[0]
        assert nomina_empleado.salario_bruto == Decimal(
            "15000.00"
        ), f"Expected employee salario_bruto of 15,000.00, got {nomina_empleado.salario_bruto}"

        # Apply nomina via route to persist side effects and regenerate voucher in one transaction
        nomina.estado = "approved"
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")
        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aplicar", follow_redirects=False)
        assert response.status_code == 302

        db_session.refresh(nomina)
        assert nomina.estado == "applied"

        # Validate 8.2: 1 vacation day accrued
        # Check VacationLedger for accrual entry
        accrual_entries = (
            db_session.query(VacationLedger)
            .filter(
                VacationLedger.account_id == vacation_account.id,
                VacationLedger.entry_type == "accrual",
                VacationLedger.source == "payroll",
                VacationLedger.reference_type == "nomina_empleado",
                VacationLedger.reference_id == nomina_empleado.id,
            )
            .all()
        )

        assert len(accrual_entries) == 1, f"Expected 1 vacation accrual entry, found {len(accrual_entries)}"

        accrual_entry = accrual_entries[0]
        expected_accrual = Decimal("1.0000")  # 2 days/month * 0.5 months
        assert (
            accrual_entry.quantity == expected_accrual
        ), f"Expected vacation accrual of {expected_accrual} days, got {accrual_entry.quantity}"

        # Validate vacation account balance
        db_session.refresh(vacation_account)
        assert (
            vacation_account.current_balance == expected_accrual
        ), f"Expected vacation balance of {expected_accrual} days, got {vacation_account.current_balance}"

        # Validate 8.3: Accounting liability created based on monthly salary
        # Monthly salary: 30,000
        # dias_base (default): 30
        # Daily rate = 30,000 / 30 = 1,000
        # Liability = 1 day * 1,000 = 1,000
        expected_monthly_salary = Decimal("30000.00")
        expected_dias_base = Decimal("30.00")
        expected_daily_rate = expected_monthly_salary / expected_dias_base
        expected_liability = expected_accrual * expected_daily_rate

        # Check if accounting voucher was created
        comprobante = db_session.query(ComprobanteContable).filter(ComprobanteContable.nomina_id == nomina.id).first()

        assert comprobante is not None, "No accounting voucher (ComprobanteContable) was created"

        # Check for vacation liability accounting lines
        vacation_lines = (
            db_session.query(ComprobanteContableLinea)
            .filter(
                ComprobanteContableLinea.comprobante_id == comprobante.id,
                ComprobanteContableLinea.tipo_concepto == "vacation_liability",
            )
            .all()
        )

        assert (
            len(vacation_lines) == 2
        ), f"Expected 2 vacation liability accounting lines (debit and credit), found {len(vacation_lines)}"

        # Find debit (expense) and credit (liability) lines
        debit_line = next((line for line in vacation_lines if line.debito > 0), None)
        credit_line = next((line for line in vacation_lines if line.credito > 0), None)

        assert debit_line is not None, "No debit line found for vacation expense"
        assert credit_line is not None, "No credit line found for vacation liability"

        # Validate amounts
        assert (
            debit_line.debito == expected_liability
        ), f"Expected debit (expense) of {expected_liability}, got {debit_line.debito}"
        assert (
            credit_line.credito == expected_liability
        ), f"Expected credit (liability) of {expected_liability}, got {credit_line.credito}"

        # Validate accounts used
        assert (
            debit_line.codigo_cuenta == "5201"
        ), f"Expected debit account 5201 (expense), got {debit_line.codigo_cuenta}"
        assert (
            credit_line.codigo_cuenta == "2205"
        ), f"Expected credit account 2205 (liability), got {credit_line.codigo_cuenta}"

        # Validate detailed-by-employee data source includes vacation liability without manual regeneration
        from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService

        detailed_entries = AccountingVoucherService(db_session).get_detailed_voucher_by_employee(comprobante)
        assert detailed_entries, "Expected detailed voucher entries by employee"
        assert any(
            linea["tipo_concepto"] == "vacation_liability"
            for entry in detailed_entries
            for linea in entry["lineas"]
        ), "Expected vacation liability in detailed voucher entries"
