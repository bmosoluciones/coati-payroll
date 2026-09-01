# SPDX-License-Identifier: Apache-2.0
"""Regression tests for loan payments across payroll currencies."""

from datetime import date
from decimal import Decimal

from coati_payroll.enums import AdelantoEstado
from coati_payroll.model import (
    Adelanto,
    AdelantoAbono,
    Deduccion,
    Empleado,
    Empresa,
    Moneda,
    Nomina,
    Planilla,
    TipoCambio,
    TipoPlanilla,
    db,
)
from coati_payroll.nomina_engine.processors.loan_processor import LoanProcessor
from coati_payroll.vistas.planilla.services.nomina_service import NominaService


def test_multicurrency_loan_payment_tracks_both_amounts_and_rolls_back(app, db_session):
    """A payroll deduction converts to the loan currency before reducing its balance."""
    with app.app_context():
        usd = Moneda(codigo="USD_LOAN", nombre="Dólar", simbolo="$", activo=True)
        nio = Moneda(codigo="NIO_PAYROLL", nombre="Córdoba", simbolo="C$", activo=True)
        empresa = Empresa(codigo="LOAN_FX", razon_social="Loan FX, S.A.", ruc="LOAN-FX-001", activo=True)
        tipo = TipoPlanilla(codigo="MONTHLY_FX", descripcion="Mensual", periodicidad="monthly", activo=True)
        db_session.add_all([usd, nio, empresa, tipo])
        db_session.flush()

        planilla = Planilla(
            nombre="Planilla en córdobas",
            tipo_planilla_id=tipo.id,
            empresa_id=empresa.id,
            moneda_id=nio.id,
            activo=True,
        )
        empleado = Empleado(
            codigo_empleado="FX-EMP-001",
            primer_nombre="Ada",
            primer_apellido="Lovelace",
            identificacion_personal="FX-IDENT-001",
            fecha_alta=date(2025, 1, 1),
            salario_base=Decimal("5000.00"),
            moneda_id=nio.id,
            empresa_id=empresa.id,
            activo=True,
        )
        deduccion = Deduccion(codigo="FX-LOAN", nombre="Préstamo FX", formula_tipo="fixed", activo=True)
        db_session.add_all([planilla, empleado, deduccion])
        db_session.flush()

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 2, 1),
            periodo_fin=date(2025, 2, 28),
            estado="generated",
        )
        loan = Adelanto(
            empleado_id=empleado.id,
            deduccion_id=deduccion.id,
            tipo="loan",
            monto_solicitado=Decimal("100.00"),
            monto_aprobado=Decimal("100.00"),
            saldo_pendiente=Decimal("100.00"),
            monto_por_cuota=Decimal("100.00"),
            moneda_id=usd.id,
            estado=AdelantoEstado.APROBADO,
        )
        rate = TipoCambio(
            fecha=date(2025, 2, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=nio.id,
            tasa=Decimal("36.5000000000"),
        )
        db_session.add_all([nomina, loan, rate])
        db_session.commit()

        processor = LoanProcessor(
            nomina=nomina,
            fecha_calculo=date(2025, 2, 28),
            periodo_inicio=date(2025, 2, 1),
            periodo_fin=date(2025, 2, 28),
            calcular_interes=False,
        )
        deductions = processor.process_loans(empleado.id, Decimal("3650.00"), True, 250)
        db_session.commit()

        assert [deduction.monto for deduction in deductions] == [Decimal("3650.00")]
        db_session.refresh(loan)
        assert loan.saldo_pendiente == Decimal("0.00")
        assert loan.monto_deducido_moneda_planilla == Decimal("3650.00")
        assert loan.monto_aplicado_moneda_prestamo == Decimal("100.00")
        abono = db_session.execute(db.select(AdelantoAbono).filter_by(adelanto_id=loan.id)).scalar_one()
        assert abono.monto_abonado == Decimal("100.00")

        NominaService._rollback_payment(abono, Adelanto)
        db_session.flush()
        assert loan.saldo_pendiente == Decimal("100.00")
        assert loan.monto_deducido_moneda_planilla == Decimal("0.00")
        assert loan.monto_aplicado_moneda_prestamo == Decimal("0.00")
