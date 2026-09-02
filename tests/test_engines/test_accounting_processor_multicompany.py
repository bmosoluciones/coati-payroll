# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests to verify benefit isolation across multiple companies."""

from datetime import date
from decimal import Decimal

from coati_payroll.model import (
    Empresa,
    Empleado,
    Moneda,
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    Prestacion,
    PrestacionAcumulada,
    Planilla,
    TipoPlanilla,
    db,
)
from coati_payroll.nomina_engine.processors.accounting_processor import AccountingProcessor


def test_benefit_accumulation_multi_company_isolation(app, db_session):
    """Verify that benefit balances accumulate strictly within each company."""
    with app.app_context():
        # Setup currency
        moneda = Moneda(codigo="NIO", nombre="Cordoba", simbolo="C$", activo=True)
        db_session.add(moneda)
        db_session.commit()

        # Setup Company A
        empresa_a = Empresa(
            codigo="COMP_A",
            razon_social="Company A S.A.",
            ruc="J123456781",
            activo=True,
        )
        db_session.add(empresa_a)

        # Setup Company B
        empresa_b = Empresa(
            codigo="COMP_B",
            razon_social="Company B S.A.",
            ruc="J123456782",
            activo=True,
        )
        db_session.add(empresa_b)
        db_session.commit()

        # Setup Payroll Type
        tipo_planilla = TipoPlanilla(
            codigo="MENSUAL",
            descripcion="Planilla Mensual",
            periodicidad="monthly",
            dias=30,
            periodos_por_anio=12,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            activo=True,
        )
        db_session.add(tipo_planilla)
        db_session.commit()

        # Setup Employee
        empleado = Empleado(
            codigo_empleado="EMP001",
            primer_nombre="Juan",
            primer_apellido="Pérez",
            identificacion_personal="001-010180-0001A",
            fecha_alta=date(2024, 1, 1),
            salario_base=Decimal("15000.00"),
            moneda_id=moneda.id,
            empresa_id=empresa_a.id,  # Initially in Company A
            activo=True,
        )
        db_session.add(empleado)
        db_session.commit()

        # Setup Prestacion (Annual)
        prestacion = Prestacion(
            codigo="AGUINALDO",
            nombre="Aguinaldo - Treceavo Mes",
            descripcion="Provisión mensual para aguinaldo",
            tipo="bonus",
            tipo_acumulacion="annual",
            formula_tipo="salary_percentage",
            porcentaje=Decimal("8.33"),
            base_calculo="salario_base",
            recurrente=True,
            activo=True,
        )
        db_session.add(prestacion)
        db_session.commit()

        # Setup Planilla for Company A
        planilla_a = Planilla(
            nombre="Planilla Company A",
            descripcion="Planilla para Company A",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa_a.id,
            activo=True,
        )
        db_session.add(planilla_a)

        # Setup Planilla for Company B
        planilla_b = Planilla(
            nombre="Planilla Company B",
            descripcion="Planilla para Company B",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa_b.id,
            activo=True,
        )
        db_session.add(planilla_b)
        db_session.commit()

        # Create a Nomina for Company A
        nomina_a = Nomina(
            planilla_id=planilla_a.id,
            periodo_inicio=date(2024, 1, 1),
            periodo_fin=date(2024, 1, 31),
            generado_por="test_user",
            estado="applied",
            total_bruto=Decimal("15000.00"),
            total_deducciones=Decimal("0.00"),
            total_neto=Decimal("15000.00"),
        )
        db_session.add(nomina_a)
        db_session.commit()

        # Create NominaEmpleado and NominaDetalle for Company A
        ne_a = NominaEmpleado(
            nomina_id=nomina_a.id,
            empleado_id=empleado.id,
            salario_bruto=Decimal("15000.00"),
            total_ingresos=Decimal("15000.00"),
            total_deducciones=Decimal("0.00"),
            salario_neto=Decimal("15000.00"),
            sueldo_base_historico=Decimal("15000.00"),
        )
        db_session.add(ne_a)
        db_session.commit()

        nd_a = NominaDetalle(
            nomina_empleado_id=ne_a.id,
            tipo="benefit",
            codigo="AGUINALDO",
            descripcion="Aguinaldo - Treceavo Mes",
            monto=Decimal("1249.50"),
            orden=1,
            prestacion_id=prestacion.id,
        )
        db_session.add(nd_a)
        db_session.commit()

        # Run accounting processor to create Company A benefit transaction
        processor = AccountingProcessor()
        processor.create_prestacion_transactions_for_nomina(
            nomina=nomina_a,
            planilla=planilla_a,
            usuario="test_user",
        )
        db_session.commit()

        # Verify transaction created under Company A
        trans_a = db_session.execute(
            db.select(PrestacionAcumulada).filter_by(
                empleado_id=empleado.id,
                prestacion_id=prestacion.id,
                empresa_id=empresa_a.id,
            )
        ).scalar_one()

        assert trans_a.monto_transaccion == Decimal("1249.50")
        assert trans_a.saldo_anterior == Decimal("0.00")
        assert trans_a.saldo_nuevo == Decimal("1249.50")

        # Now, create a Nomina for Company B
        nomina_b = Nomina(
            planilla_id=planilla_b.id,
            periodo_inicio=date(2024, 2, 1),
            periodo_fin=date(2024, 2, 29),
            generado_por="test_user",
            estado="applied",
            total_bruto=Decimal("15000.00"),
            total_deducciones=Decimal("0.00"),
            total_neto=Decimal("15000.00"),
        )
        db_session.add(nomina_b)
        db_session.commit()

        # Create NominaEmpleado and NominaDetalle for Company B
        ne_b = NominaEmpleado(
            nomina_id=nomina_b.id,
            empleado_id=empleado.id,
            salario_bruto=Decimal("15000.00"),
            total_ingresos=Decimal("15000.00"),
            total_deducciones=Decimal("0.00"),
            salario_neto=Decimal("15000.00"),
            sueldo_base_historico=Decimal("15000.00"),
        )
        db_session.add(ne_b)
        db_session.commit()

        nd_b = NominaDetalle(
            nomina_empleado_id=ne_b.id,
            tipo="benefit",
            codigo="AGUINALDO",
            descripcion="Aguinaldo - Treceavo Mes",
            monto=Decimal("1249.50"),
            orden=1,
            prestacion_id=prestacion.id,
        )
        db_session.add(nd_b)
        db_session.commit()

        # Run accounting processor to create Company B benefit transaction
        processor.create_prestacion_transactions_for_nomina(
            nomina=nomina_b,
            planilla=planilla_b,
            usuario="test_user",
        )
        db_session.commit()

        # Verify transaction created under Company B
        # Crucial check: Since it belongs to Company B, previous balance must be 0.00
        # instead of 1249.50 (which was accumulated under Company A).
        trans_b = db_session.execute(
            db.select(PrestacionAcumulada).filter_by(
                empleado_id=empleado.id,
                prestacion_id=prestacion.id,
                empresa_id=empresa_b.id,
            )
        ).scalar_one()

        assert trans_b.monto_transaccion == Decimal("1249.50")
        assert trans_b.saldo_anterior == Decimal("0.00")  # Isolated from Company A
        assert trans_b.saldo_nuevo == Decimal("1249.50")  # Isolated from Company A
