# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.


from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from coati_payroll.enums import NominaEstado, AdelantoEstado
from coati_payroll.liquidacion_engine import LiquidacionEngine, ejecutar_liquidacion, recalcular_liquidacion
from coati_payroll.model import (
    ConfiguracionCalculos,
    Deduccion,
    Empleado,
    Nomina,
    NominaEmpleado,
    Adelanto,
    AdelantoAbono,
    Planilla,
    TipoPlanilla,
    Moneda,
    db,
)


def _create_minimal_planilla_context(db_session, empresa_id: str):
    moneda = Moneda(codigo="USD", nombre="Dollar", simbolo="$", activo=True)
    db_session.add(moneda)
    db_session.flush()

    tipo = TipoPlanilla(codigo="MONTHLY", descripcion="Mensual", periodicidad="monthly", dias=30, activo=True)
    db_session.add(tipo)
    db_session.flush()

    planilla = Planilla(
        nombre="Planilla Test",
        descripcion="",
        tipo_planilla_id=tipo.id,
        moneda_id=moneda.id,
        empresa_id=empresa_id,
        activo=True,
    )
    db_session.add(planilla)
    db_session.flush()

    return planilla


def test_ultimo_dia_pagado_usa_nomina_aplicada(app, db_session):
    from tests.factories.company_factory import create_company

    with app.app_context():
        empresa = create_company(db_session, codigo="E1", razon_social="Empresa 1", ruc="RUC1")

        empleado = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP1",
            primer_nombre="A",
            primer_apellido="B",
            identificacion_personal="ID-EMP1",
            fecha_alta=date(2025, 1, 1),
            salario_base=Decimal("900.00"),
            activo=True,
        )
        db_session.add(empleado)
        db_session.flush()

        planilla = _create_minimal_planilla_context(db_session, empresa.id)

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 2, 1),
            periodo_fin=date(2025, 2, 15),
            estado=NominaEstado.APLICADO,
        )
        db_session.add(nomina)
        db_session.flush()

        ne = NominaEmpleado(nomina_id=nomina.id, empleado_id=empleado.id)
        db_session.add(ne)
        db_session.commit()

        engine = LiquidacionEngine(empleado=empleado, fecha_calculo=date(2025, 2, 20))
        assert engine.determinar_ultimo_dia_pagado() == date(2025, 2, 15)


def test_ultimo_dia_pagado_sin_nominas_es_fecha_alta_menos_un_dia(app, db_session):
    from tests.factories.company_factory import create_company

    with app.app_context():
        empresa = create_company(db_session, codigo="E2", razon_social="Empresa 2", ruc="RUC2")

        empleado = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP2",
            primer_nombre="A",
            primer_apellido="B",
            identificacion_personal="ID-EMP2",
            fecha_alta=date(2025, 3, 10),
            salario_base=Decimal("1000.00"),
            activo=True,
        )
        db_session.add(empleado)
        db_session.commit()

        engine = LiquidacionEngine(empleado=empleado, fecha_calculo=date(2025, 3, 15))
        assert engine.determinar_ultimo_dia_pagado() == date(2025, 3, 9)


@pytest.mark.parametrize(
    "modo,factor,expected_daily",
    [
        ("calendario", 30, Decimal("10.00")),
        ("laboral", 28, Decimal("10.71")),
    ],
)
def test_prorrateo_usa_factor_configurado(app, db_session, modo, factor, expected_daily):
    from tests.factories.company_factory import create_company

    with app.app_context():
        empresa = create_company(db_session, codigo="E3", razon_social="Empresa 3", ruc="RUC3")

        config = ConfiguracionCalculos(
            empresa_id=empresa.id,
            pais_id=None,
            activo=True,
            liquidacion_modo_dias=modo,
            liquidacion_factor_calendario=30,
            liquidacion_factor_laboral=28,
        )
        db_session.add(config)

        empleado = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP3",
            primer_nombre="A",
            primer_apellido="B",
            identificacion_personal="ID-EMP3",
            fecha_alta=date(2025, 1, 1),
            salario_base=Decimal("300.00"),
            activo=True,
        )
        db_session.add(empleado)
        db_session.commit()

        liq, errors, warnings = ejecutar_liquidacion(
            empleado_id=empleado.id,
            concepto_id=None,
            fecha_calculo=date(2025, 1, 1),
            usuario="test",
        )
        assert errors == []
        assert liq is not None
        assert liq.dias_por_pagar == 1

        # monto esperado: salario/factor * 1
        assert liq.total_bruto == expected_daily


def test_deducciones_adelantos_y_recalculo_no_duplica_abonos(app, db_session):
    from tests.factories.company_factory import create_company

    with app.app_context():
        empresa = create_company(db_session, codigo="E4", razon_social="Empresa 4", ruc="RUC4")

        config = ConfiguracionCalculos(
            empresa_id=empresa.id,
            pais_id=None,
            activo=True,
            liquidacion_modo_dias="calendar",
            liquidacion_factor_calendario=30,
            liquidacion_factor_laboral=28,
        )
        db_session.add(config)

        empleado = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP4",
            primer_nombre="A",
            primer_apellido="B",
            identificacion_personal="ID-EMP4",
            fecha_alta=date(2025, 1, 1),
            salario_base=Decimal("300.00"),
            activo=True,
        )
        db_session.add(empleado)
        db_session.flush()

        # Loan requires a Deduccion
        ded = Deduccion(
            codigo="DED1",
            nombre="Deduccion Prestamo",
            tipo="loan",
            es_impuesto=False,
            formula_tipo="fixed",
            antes_impuesto=False,
            recurrente=False,
            activo=True,
        )
        db_session.add(ded)
        db_session.flush()

        prestamo = Adelanto(
            empleado_id=empleado.id,
            deduccion_id=ded.id,
            tipo="loan",
            estado=AdelantoEstado.APROBADO,
            saldo_pendiente=Decimal("5.00"),
            monto_por_cuota=Decimal("5.00"),
        )
        db_session.add(prestamo)

        adelanto = Adelanto(
            empleado_id=empleado.id,
            deduccion_id=None,
            tipo="advance",
            estado=AdelantoEstado.APROBADO,
            saldo_pendiente=Decimal("3.00"),
            monto_por_cuota=Decimal("3.00"),
        )
        db_session.add(adelanto)
        db_session.commit()

        # Create liquidacion: 1 day => 10.00 gross; should pay 5 + 3 deductions
        liq, errors, _warnings = ejecutar_liquidacion(
            empleado_id=empleado.id,
            concepto_id=None,
            fecha_calculo=date(2025, 1, 2),
            usuario="test",
        )
        assert errors == []
        assert liq is not None

        db_session.refresh(prestamo)
        db_session.refresh(adelanto)
        assert Decimal(str(prestamo.saldo_pendiente)) == Decimal("0.00")
        assert Decimal(str(adelanto.saldo_pendiente)) == Decimal("0.00")

        abonos_1 = db_session.execute(db.select(AdelantoAbono).filter_by(liquidacion_id=liq.id)).scalars().all()
        assert len(abonos_1) == 2

        # Recalculate and ensure payments not duplicated (still 2 abonos)
        liq2, errors2, _warnings2 = recalcular_liquidacion(
            liquidacion_id=liq.id, fecha_calculo=liq.fecha_calculo, usuario="test"
        )
        assert errors2 == []
        assert liq2 is not None

        abonos_2 = db_session.execute(db.select(AdelantoAbono).filter_by(liquidacion_id=liq.id)).scalars().all()
        assert len(abonos_2) == 2

        db_session.refresh(prestamo)
        db_session.refresh(adelanto)
        assert Decimal(str(prestamo.saldo_pendiente)) == Decimal("0.00")
        assert Decimal(str(adelanto.saldo_pendiente)) == Decimal("0.00")


def test_liquidacion_deduce_saldo_total_no_una_cuota(app, db_session):
    """Liquidation must deduct the full outstanding balance, not a single installment."""
    from tests.factories.company_factory import create_company

    with app.app_context():
        empresa = create_company(db_session, codigo="E5", razon_social="Empresa 5", ruc="RUC5")

        config = ConfiguracionCalculos(
            empresa_id=empresa.id,
            pais_id=None,
            activo=True,
            liquidacion_modo_dias="calendar",
            liquidacion_factor_calendario=30,
            liquidacion_factor_laboral=28,
        )
        db_session.add(config)

        empleado = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP5",
            primer_nombre="A",
            primer_apellido="B",
            identificacion_personal="ID-EMP5",
            fecha_alta=date(2025, 1, 1),
            salario_base=Decimal("300.00"),
            activo=True,
        )
        db_session.add(empleado)
        db_session.flush()

        ded = Deduccion(
            codigo="DED2",
            nombre="Deduccion Prestamo",
            tipo="loan",
            es_impuesto=False,
            formula_tipo="fixed",
            antes_impuesto=False,
            recurrente=False,
            activo=True,
        )
        db_session.add(ded)
        db_session.flush()

        prestamo = Adelanto(
            empleado_id=empleado.id,
            deduccion_id=ded.id,
            tipo="loan",
            estado=AdelantoEstado.APROBADO,
            saldo_pendiente=Decimal("20.00"),
            monto_por_cuota=Decimal("2.00"),  # installment much smaller than balance
        )
        db_session.add(prestamo)
        db_session.commit()

        # fecha_calculo - (fecha_alta - 1) = 2 days => 300/30 * 2 = 20.00 gross.
        # The whole 20.00 balance is deducted (not just the 2.00 installment),
        # because the settlement covers the full outstanding debt.
        liq, errors, _warnings = ejecutar_liquidacion(
            empleado_id=empleado.id,
            concepto_id=None,
            fecha_calculo=date(2025, 1, 2),
            usuario="test",
        )
        assert errors == []
        assert liq is not None

        liq.estado = LiquidacionEstado.APLICADO
        engine = LiquidacionEngine(empleado=empleado, fecha_calculo=liq.fecha_calculo)
        applied = engine.calcular(liq)
        assert applied is not None
        db_session.commit()

        prestamo = db_session.get(Adelanto, prestamo.id)
        # Full 20.00 balance applied, not the 2.00 installment
        assert Decimal(str(prestamo.saldo_pendiente)) == Decimal("0.00")

        loan_deductions = [d for d in liq.detalles if d.tipo == "deduction" and d.codigo.startswith("PRESTAMO_")]
        assert len(loan_deductions) == 1
        assert loan_deductions[0].monto == Decimal("20.00")

