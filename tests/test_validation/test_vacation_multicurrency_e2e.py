# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""End-to-end test for vacation liability with multi-currency payroll.

This test validates that vacation liability accounting entries correctly apply
exchange rates when employees are paid in a different source currency than the
payroll currency.
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
    TipoCambio,
    TipoPlanilla,
    VacationAccount,
    VacationLedger,
    VacationPolicy,
    ComprobanteContable,
    ComprobanteContableLinea,
)
from coati_payroll.vistas.planilla.services.nomina_service import NominaService


@pytest.mark.validation
def test_vacation_liability_respects_exchange_rate(app, client, admin_user, db_session):
    """
    End-to-end test: Vacation liability uses converted salary for multi-currency employees.

    Setup:
    - Payroll currency: NIO (Córdoba)
    - Employee currency: USD
    - Exchange rate: 1 USD = 37.50 NIO
    - Employee salary: 1,000 USD monthly (37,500 NIO converted)
    - Biweekly payroll (15 days)
    - Vacation rule: 2 days per month worked (periodic accrual)

    Expected results after biweekly payroll:
    - Salary payment: 18,750 NIO (1,000 USD * 37.50 / 2)
    - Vacation days accrued: 1 day (2 days/month * 0.5 months)
    - Accounting liability: 1,250 NIO (37,500 NIO monthly / 30 dias_base * 1 day accrued)
      NOT 33.33 NIO (1,000 USD / 30 * 1 day without conversion)

    This test validates the fix for: vacation liability must use empleado.salario_base
    with tipo_cambio_aplicado (converted monthly salary) instead of raw source currency.
    """
    with app.app_context():
        # Create currencies
        nio = Moneda(codigo="NIO", nombre="Córdoba Nicaragüense", simbolo="C$", activo=True)
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True)
        db_session.add_all([nio, usd])
        db_session.commit()
        db_session.refresh(nio)
        db_session.refresh(usd)

        # Create exchange rate: 1 USD = 37.50 NIO
        exchange_rate = TipoCambio(
            fecha=date(2026, 2, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=nio.id,
            tasa=Decimal("37.50"),
            creado_por="admin-test",
        )
        db_session.add(exchange_rate)
        db_session.commit()

        # 1. Create company
        empresa = Empresa(
            codigo="TEST-MC",
            razon_social="Test MultiCurrency Company",
            ruc="J-0000000001-2026",
            activo=True,
        )
        db_session.add(empresa)
        db_session.commit()
        db_session.refresh(empresa)

        # 2. Create employee with USD salary
        empleado = Empleado(
            codigo_empleado="EMP-USD-001",
            primer_nombre="John",
            primer_apellido="Dollar",
            identificacion_personal="001-010190-0001B",
            empresa_id=empresa.id,
            salario_base=Decimal("1000.00"),  # 1,000 USD
            moneda_id=usd.id,  # Paid in USD
            activo=True,
            fecha_alta=date(2026, 1, 1),
        )
        db_session.add(empleado)
        db_session.commit()
        db_session.refresh(empleado)

        # 3. Create biweekly payroll type
        tipo_planilla = TipoPlanilla(
            codigo="QUINCENAL-MC",
            descripcion="Quincenal MultiCurrency Test",
            periodicidad="biweekly",
            dias=15,
            periodos_por_anio=24,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            activo=True,
        )
        db_session.add(tipo_planilla)
        db_session.flush()

        # 4. Create vacation policy (2 days per month, paid 100%)
        vacation_policy = VacationPolicy(
            codigo="VAC-MC-2026",
            nombre="Vacation MC Test",
            empresa_id=empresa.id,
            accrual_method="periodic",
            accrual_rate=Decimal("2.0000"),
            accrual_frequency="monthly",
            unit_type="days",
            min_service_days=0,
            allow_negative=False,
            activo=True,
            son_vacaciones_pagadas=True,
            porcentaje_pago_vacaciones=Decimal("100.00"),
            cuenta_debito_vacaciones_pagadas="5101",
            descripcion_cuenta_debito_vacaciones_pagadas="Gasto Vacaciones",
            cuenta_credito_vacaciones_pagadas="2103",
            descripcion_cuenta_credito_vacaciones_pagadas="Pasivo Vacaciones",
        )
        db_session.add(vacation_policy)
        db_session.flush()

        # 5. Create biweekly planilla linked to vacation policy
        planilla = Planilla(
            nombre="Planilla MultiCurrency Feb 2026",
            tipo_planilla_id=tipo_planilla.id,
            empresa_id=empresa.id,
            moneda_id=nio.id,  # Payroll in NIO
            activo=True,
            vacation_policy_id=vacation_policy.id,  # Link to vacation policy
            # Accounting configuration for base salary
            codigo_cuenta_debe_salario="5101",
            descripcion_cuenta_debe_salario="Gasto por Salario",
            codigo_cuenta_haber_salario="2101",
            descripcion_cuenta_haber_salario="Salario por Pagar",
        )
        db_session.add(planilla)
        db_session.flush()

        # 6. Associate employee to payroll
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        # Create vacation account for employee
        vacation_account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=vacation_policy.id,
            current_balance=Decimal("0.00"),
            activo=True,
        )
        db_session.add(vacation_account)
        db_session.commit()

        # 7. Execute payroll for Feb 1-15, 2026
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

        # Refresh session to get updated data
        db_session.refresh(nomina)

        # Apply vacation accruals (per design: deferred to apply step)
        from coati_payroll.vacation_service import VacationService

        vacation_snapshot_apply = {}
        if nomina.catalogos_snapshot:
            vacation_snapshot_apply = (nomina.catalogos_snapshot.get("vacaciones") or {}).copy()
        vacation_snapshot_apply["configuracion"] = nomina.configuracion_snapshot or {}

        vacation_service = VacationService(
            planilla=planilla,
            periodo_inicio=nomina.periodo_inicio,
            periodo_fin=nomina.periodo_fin,
            snapshot=vacation_snapshot_apply,
            apply_side_effects=True,
        )

        for ne in nomina.nomina_empleados:
            emp = ne.empleado or db_session.get(Empleado, ne.empleado_id)
            if emp and emp.activo:
                vacation_service.acumular_vacaciones_empleado(emp, ne, admin_user.usuario)

        db_session.flush()

        # Regenerate accounting voucher to include vacation liability lines
        # (now that vacation ledger entries exist after apply)
        from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService

        # Delete old comprobante
        old_comprobante = db_session.query(ComprobanteContable).filter(ComprobanteContable.nomina_id == nomina.id).first()
        if old_comprobante:
            db_session.delete(old_comprobante)
            db_session.flush()

        # Regenerate with vacation entries included
        voucher_service = AccountingVoucherService(db_session)
        voucher_service.generate_audit_voucher(nomina, planilla, fecha_calculo, admin_user.usuario)
        db_session.flush()

        # 8. Validate salary payment (converted to NIO)
        # Expected: 1,000 USD * 37.50 exchange rate = 37,500 NIO monthly
        # Biweekly (15 days out of 30): 37,500 / 2 = 18,750 NIO

        nomina_empleados = nomina.nomina_empleados
        assert len(nomina_empleados) == 1

        ne = nomina_empleados[0]
        assert ne.empleado_id == empleado.id

        # Validate currency conversion was applied
        assert ne.moneda_origen_id == usd.id
        assert ne.tipo_cambio_aplicado == Decimal("37.50")

        # Validate period salary snapshot (sueldo_base_historico stores period salary, not monthly)
        # 1,000 USD * 37.50 = 37,500 NIO monthly / 2 (biweekly) = 18,750 NIO
        assert ne.sueldo_base_historico == Decimal("18750.00")

        # Validate period salary (18,750 NIO for 15 days)
        assert ne.salario_bruto == Decimal("18750.00")

        # 9. Validate vacation accrual
        vacation_account = db_session.query(VacationAccount).filter(VacationAccount.empleado_id == empleado.id).first()
        assert vacation_account is not None

        # 1 day accrued: 2 days per month * (15 days / 30 days per month) = 1 day (rounded to 2 decimals)
        assert vacation_account.current_balance == Decimal("1.00")

        vacation_ledger = (
            db_session.query(VacationLedger).filter(VacationLedger.account_id == vacation_account.id).first()
        )
        assert vacation_ledger is not None
        assert vacation_ledger.quantity == Decimal("1.00")
        assert vacation_ledger.reference_type == "nomina_empleado"
        assert vacation_ledger.reference_id == ne.id

        # 10. Validate accounting liability uses converted salary
        comprobante = db_session.query(ComprobanteContable).filter(ComprobanteContable.nomina_id == nomina.id).first()
        assert comprobante is not None

        vacation_lines = [linea for linea in comprobante.lineas if linea.tipo_concepto == "vacation_liability"]
        assert len(vacation_lines) == 2  # Debit and credit

        # Expected liability: 37,500 NIO monthly / 30 dias_base * 1 day = 1,250 NIO
        expected_liability = Decimal("1250.00")

        debit_line = next((l for l in vacation_lines if l.codigo_cuenta == "5101"), None)
        credit_line = next((l for l in vacation_lines if l.codigo_cuenta == "2103"), None)

        assert debit_line is not None, "Debit vacation liability line not found"
        assert credit_line is not None, "Credit vacation liability line not found"

        assert (
            debit_line.debito == expected_liability
        ), f"Expected {expected_liability} NIO liability, got {debit_line.debito}"
        assert debit_line.credito == Decimal("0.00")

        assert credit_line.credito == expected_liability
        assert credit_line.debito == Decimal("0.00")

        # Validate the liability is NOT based on unconverted salary
        # If using empleado.salario_base without conversion:
        # Wrong calculation: 1,000 USD / 30 * 1 day = 33.33 (wrong!)
        wrong_liability = Decimal("33.33")
        assert debit_line.debito != wrong_liability, "Vacation liability incorrectly using unconverted USD salary!"
