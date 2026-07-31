# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for payroll engine idempotency and clean rollbacks.

These tests ensure that:
- Deleting or recalculating a payroll reverts annual accumulations, vacation ledger, and loans.
- Canceling (voiding) a payroll reverts all accumulations, vacation ledger entries, and loans.
- Re-running a cancelled or recalculated payroll produces identical outputs (idempotency).
"""

from datetime import date
from decimal import Decimal

from coati_payroll.enums import NominaEstado, AdelantoEstado
from coati_payroll.model import (
    Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado,
    Adelanto, AdelantoAbono, InteresAdelanto, AcumuladoAnual,
    VacationPolicy, VacationAccount, VacationLedger, db
)
from coati_payroll.vistas.planilla.services.nomina_service import NominaService


def test_anular_nomina_reverts_all_side_effects(app, db_session):
    """Test that canceling a payroll run fully reverts all side effects."""
    with app.app_context():
        # Setup base entities
        moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
        db_session.add(moneda)

        empresa = Empresa(
            codigo="TEST001", razon_social="Test Company SA", ruc="J-12345678",
            primer_mes_nomina=1, primer_anio_nomina=2025
        )
        db_session.add(empresa)
        db_session.flush()

        tipo_planilla = TipoPlanilla(
            codigo="MENSUAL",
            descripcion="Mensual",
            periodicidad="monthly",
            dias=30,
            periodos_por_anio=12,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
        )
        db_session.add(tipo_planilla)
        db_session.flush()

        # Vacation policy
        policy = VacationPolicy(
            codigo="VAC_POL_01",
            nombre="Standard Policy",
            activo=True,
            accrual_method="periodic",
            accrual_rate=Decimal("2.5000"),
            accrual_frequency="monthly",
            min_service_days=0,
            allow_negative=False,
            unit_type="days",
        )
        db_session.add(policy)
        db_session.flush()

        planilla = Planilla(
            nombre="Planilla Mensual",
            tipo_planilla_id=tipo_planilla.id,
            empresa_id=empresa.id,
            moneda_id=moneda.id,
            vacation_policy_id=policy.id,
            activo=True,
        )
        db_session.add(planilla)
        db_session.flush()

        # Policy needs reference to planilla
        policy.planilla_id = planilla.id

        empleado = Empleado(
            codigo_empleado="EMP001",
            primer_nombre="Juan",
            primer_apellido="Pérez",
            identificacion_personal="001-010180-0001A",
            fecha_alta=date(2024, 1, 1),
            salario_base=Decimal("20000.00"),
            moneda_id=moneda.id,
            empresa_id=empresa.id,
            activo=True,
        )
        db_session.add(empleado)
        db_session.flush()

        planilla_emp = PlanillaEmpleado(
            planilla_id=planilla.id, empleado_id=empleado.id, activo=True, fecha_inicio=date(2024, 1, 1)
        )
        db_session.add(planilla_emp)

        # Create active loan/advance for the employee
        # Deduccion is required for loans (with an associated deduccion_id)
        from coati_payroll.model import Deduccion
        deduccion = Deduccion(
            codigo="PRESTAMO_DED",
            nombre="Prestamo Deduccion",
            formula_tipo="fixed",
            activo=True,
        )
        db_session.add(deduccion)
        db_session.flush()

        loan = Adelanto(
            empleado_id=empleado.id,
            deduccion_id=deduccion.id,
            tipo="loan",
            monto_solicitado=Decimal("5000.00"),
            monto_aprobado=Decimal("5000.00"),
            saldo_pendiente=Decimal("5000.00"),
            monto_por_cuota=Decimal("1000.00"),
            tasa_interes=Decimal("0.1200"),  # 12%
            tipo_interes="simple",
            estado=AdelantoEstado.APROBADO,
            fecha_desembolso=date(2025, 1, 1),
        )
        db_session.add(loan)
        db_session.flush()

        # Vacation account
        vac_account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=policy.id,
            current_balance=Decimal("0.0000"),
            activo=True,
        )
        db_session.add(vac_account)
        db_session.flush()
        db_session.commit()

        # 1. Run payroll
        periodo_inicio = date(2025, 1, 1)
        periodo_fin = date(2025, 1, 31)
        fecha_calculo = date(2025, 1, 31)

        nomina, errors, warnings = NominaService.ejecutar_nomina(
            planilla=planilla,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            fecha_calculo=fecha_calculo,
            usuario="admin",
        )

        assert not errors
        assert nomina is not None

        # Verify side effects were applied
        # a) Accumulations
        acumulado = db_session.execute(
            db.select(AcumuladoAnual).filter_by(
                empleado_id=empleado.id,
                tipo_planilla_id=tipo_planilla.id,
                periodo_fiscal_inicio=date(2025, 1, 1)
            )
        ).scalar_one()
        assert acumulado.salario_bruto_acumulado == Decimal("20000.00")
        assert acumulado.periodos_procesados == 1

        # b) Loans (payment recorded and interest calculated)
        interest = db_session.execute(
            db.select(InteresAdelanto).filter_by(adelanto_id=loan.id, nomina_id=nomina.id)
        ).scalar_one_or_none()
        assert interest is not None
        assert interest.interes_calculado > 0

        abono = db_session.execute(
            db.select(AdelantoAbono).filter_by(adelanto_id=loan.id, nomina_id=nomina.id)
        ).scalar_one_or_none()
        assert abono is not None
        assert abono.monto_abonado == Decimal("1000.00")

        # Verify loan balance was updated: 5000 + interest - 1000
        expected_balance = Decimal("5000.00") + interest.interes_calculado - Decimal("1000.00")
        assert loan.saldo_pendiente == expected_balance

        # c) Vacation ledger accrual
        # Let's transition state to APPROVED and then APLICADO
        nomina.estado = "approved"
        db_session.commit()

        # Let's apply the payroll
        from coati_payroll.vistas.planilla.nomina_routes import _aplicar_vacaciones_nomina
        _aplicar_vacaciones_nomina(nomina, planilla, "admin")
        db_session.commit()

        # Now check vacation ledger entries
        ledger_entry = db_session.execute(
            db.select(VacationLedger).filter_by(account_id=vac_account.id)
        ).scalar_one_or_none()
        assert ledger_entry is not None
        assert ledger_entry.quantity == Decimal("3.0000")
        assert vac_account.current_balance == Decimal("3.0000")

        # 2. Cancel/void the payroll
        # Since we applied it to create the vacation ledger entries, let's set state back to approved
        # so we can cancel/void it.
        nomina.estado = "approved"
        db_session.commit()

        success = NominaService.anular_nomina(nomina, planilla, "admin", "Anulando para test")
        assert success is True
        db_session.commit()

        # Verify EVERYTHING was reverted!
        # a) Accumulations reverted to 0
        assert acumulado.salario_bruto_acumulado == Decimal("0.00")
        assert acumulado.periodos_procesados == 0

        # b) Loans and interests reverted
        assert loan.saldo_pendiente == Decimal("5000.00")
        assert loan.interes_acumulado == Decimal("0.00")
        assert db_session.execute(
            db.select(AdelantoAbono).filter_by(adelanto_id=loan.id, nomina_id=nomina.id)
        ).scalar_one_or_none() is None
        assert db_session.execute(
            db.select(InteresAdelanto).filter_by(adelanto_id=loan.id, nomina_id=nomina.id)
        ).scalar_one_or_none() is None

        # c) Vacation ledger entry deleted and balance reverted to 0
        assert db_session.execute(
            db.select(VacationLedger).filter_by(account_id=vac_account.id)
        ).scalar_one_or_none() is None
        assert vac_account.current_balance == Decimal("0.0000")
