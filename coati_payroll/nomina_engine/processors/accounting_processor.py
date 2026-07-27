# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Accounting processor for creating payroll records."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from coati_payroll.enums import TipoAcumulacionPrestacion, TipoDetalle
from coati_payroll.model import db, Nomina, NominaEmpleado, NominaDetalle, Prestacion, PrestacionAcumulada
from ..domain.employee_calculation import EmpleadoCalculo
from ..utils.rounding import round_money


class AccountingProcessor:
    """Processor for creating accounting records (NominaEmpleado, NominaDetalle, PrestacionAcumulada)."""

    def create_nomina_empleado(self, emp_calculo: EmpleadoCalculo, nomina: Nomina) -> NominaEmpleado:
        """Create NominaEmpleado record with all details."""
        empleado = emp_calculo.empleado

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado.id,
            salario_bruto=round_money(emp_calculo.salario_bruto),
            total_ingresos=round_money(emp_calculo.total_percepciones),
            total_deducciones=round_money(emp_calculo.total_deducciones),
            salario_neto=round_money(emp_calculo.salario_neto),
            moneda_origen_id=emp_calculo.moneda_origen_id,
            tipo_cambio_aplicado=emp_calculo.tipo_cambio,
            cargo_snapshot=empleado.cargo,
            area_snapshot=empleado.area,
            centro_costos_snapshot=empleado.centro_costos,
            sueldo_base_historico=round_money(emp_calculo.salario_base),
            inasistencia_dias=emp_calculo.inasistencia_dias,
            inasistencia_horas=emp_calculo.inasistencia_horas,
            inasistencia_descuento=round_money(emp_calculo.inasistencia_descuento),
        )
        db.session.add(nomina_empleado)
        db.session.flush()

        # Create detail records for perceptions
        orden = 0
        for percepcion in emp_calculo.percepciones:
            orden += 1
            detalle = NominaDetalle(
                nomina_empleado_id=nomina_empleado.id,
                tipo=TipoDetalle.INGRESO,
                codigo=percepcion.codigo,
                descripcion=percepcion.nombre,
                monto=round_money(percepcion.monto),
                orden=orden,
                percepcion_id=percepcion.percepcion_id,
            )
            db.session.add(detalle)

        # Create detail records for deductions
        for deduccion in emp_calculo.deducciones:
            orden += 1
            detalle = NominaDetalle(
                nomina_empleado_id=nomina_empleado.id,
                tipo=TipoDetalle.DEDUCCION,
                codigo=deduccion.codigo,
                descripcion=deduccion.nombre,
                monto=round_money(deduccion.monto),
                orden=orden,
                deduccion_id=deduccion.deduccion_id,
            )
            db.session.add(detalle)

        # Create detail records for benefits
        for prestacion in emp_calculo.prestaciones:
            orden += 1
            detalle = NominaDetalle(
                nomina_empleado_id=nomina_empleado.id,
                tipo=TipoDetalle.PRESTACION,
                codigo=prestacion.codigo,
                descripcion=prestacion.nombre,
                monto=round_money(prestacion.monto),
                orden=orden,
                prestacion_id=prestacion.prestacion_id,
            )
            db.session.add(detalle)

        return nomina_empleado

    def create_prestacion_transactions(
        self,
        emp_calculo: EmpleadoCalculo,
        nomina: Nomina,
        planilla,
        periodo_fin: date,
        fecha_calculo: date,
    ) -> None:
        """Create transactional records for accumulated benefits."""
        empleado = emp_calculo.empleado
        periodo_anio = periodo_fin.year
        periodo_mes = periodo_fin.month
        moneda_id = planilla.moneda_id

        for prestacion_item in emp_calculo.prestaciones:
            if not prestacion_item.prestacion_id:
                continue

            prestacion = db.session.get(Prestacion, prestacion_item.prestacion_id)
            if not prestacion:
                continue

            # Get the previous balance
            from sqlalchemy import select

            ultima_transaccion = (
                db.session.execute(
                    select(PrestacionAcumulada)
                    .filter(
                        PrestacionAcumulada.empleado_id == empleado.id,
                        PrestacionAcumulada.prestacion_id == prestacion.id,
                        PrestacionAcumulada.empresa_id == planilla.empresa_id,
                    )
                    .order_by(
                        PrestacionAcumulada.fecha_transaccion.desc(),
                        PrestacionAcumulada.creado.desc(),
                    )
                    .limit(1)
                )
                .unique()
                .scalars()
                .first()
            )

            saldo_anterior = ultima_transaccion.saldo_nuevo if ultima_transaccion else Decimal("0.00")

            # For monthly settlement benefits, reset balance if new month
            if prestacion.tipo_acumulacion == TipoAcumulacionPrestacion.MENSUAL:
                if ultima_transaccion and (
                    ultima_transaccion.anio != periodo_anio or ultima_transaccion.mes != periodo_mes
                ):
                    saldo_anterior = Decimal("0.00")

            # Calculate new balance
            monto_transaccion = round_money(prestacion_item.monto)
            saldo_nuevo = round_money(saldo_anterior + monto_transaccion)

            # Create the transaction record
            transaccion = PrestacionAcumulada(
                empleado_id=empleado.id,
                prestacion_id=prestacion.id,
                fecha_transaccion=fecha_calculo,
                tipo_transaccion="adicion",
                anio=periodo_anio,
                mes=periodo_mes,
                moneda_id=moneda_id,
                empresa_id=planilla.empresa_id,
                monto_transaccion=monto_transaccion,
                saldo_anterior=saldo_anterior,
                saldo_nuevo=saldo_nuevo,
                nomina_id=nomina.id,
                observaciones=(
                    f"Provisión nómina {nomina.periodo_inicio.strftime('%Y-%m-%d')} - "
                    f"{nomina.periodo_fin.strftime('%Y-%m-%d')}"
                ),
                procesado_por=nomina.generado_por,
                creado_por=nomina.generado_por,
            )

            db.session.add(transaccion)

    def create_prestacion_transactions_for_nomina(self, nomina: Nomina, planilla, usuario: str | None = None) -> int:
        """Create benefit accumulation transactions for an applied/paid payroll.

        This method is idempotent: for each (nomina, empleado, prestacion) tuple it
        creates at most one transaction of type ``adicion``.
        """
        from sqlalchemy import func, select

        periodo_anio = nomina.periodo_fin.year
        periodo_mes = nomina.periodo_fin.month
        fecha_transaccion = nomina.fecha_calculo_original or nomina.periodo_fin
        moneda_id = planilla.moneda_id
        procesado_por = usuario or nomina.aplicado_por or nomina.generado_por
        creado_por = procesado_por or nomina.generado_por

        rows = db.session.execute(
            select(
                NominaEmpleado.empleado_id,
                NominaDetalle.prestacion_id,
                func.coalesce(func.sum(NominaDetalle.monto), 0),
            )
            .join(NominaDetalle, NominaDetalle.nomina_empleado_id == NominaEmpleado.id)
            .where(
                NominaEmpleado.nomina_id == nomina.id,
                NominaDetalle.tipo == TipoDetalle.PRESTACION,
                NominaDetalle.prestacion_id.is_not(None),
            )
            .group_by(NominaEmpleado.empleado_id, NominaDetalle.prestacion_id)
            .order_by(NominaEmpleado.empleado_id, NominaDetalle.prestacion_id)
        ).all()

        created_count = 0
        for empleado_id, prestacion_id, monto_total in rows:
            created_count += self._create_nomina_benefit_transaction(
                nomina=nomina,
                planilla=planilla,
                select=select,
                empleado_id=empleado_id,
                prestacion_id=prestacion_id,
                monto_total=monto_total,
                periodo_anio=periodo_anio,
                periodo_mes=periodo_mes,
                fecha_transaccion=fecha_transaccion,
                moneda_id=moneda_id,
                procesado_por=procesado_por,
                creado_por=creado_por,
            )

        return created_count

    def _create_nomina_benefit_transaction(
        self,
        *,
        nomina,
        planilla,
        select,
        empleado_id,
        prestacion_id,
        monto_total,
        periodo_anio,
        periodo_mes,
        fecha_transaccion,
        moneda_id,
        procesado_por,
        creado_por,
    ) -> int:
        """Create one idempotent benefit transaction when its source is valid."""
        if not prestacion_id:
            return 0
        existing = db.session.execute(
            select(PrestacionAcumulada.id)
            .where(
                PrestacionAcumulada.nomina_id == nomina.id,
                PrestacionAcumulada.empleado_id == empleado_id,
                PrestacionAcumulada.prestacion_id == prestacion_id,
                PrestacionAcumulada.tipo_transaccion == "adicion",
            )
            .limit(1)
        ).scalar_one_or_none()
        prestacion = db.session.get(Prestacion, prestacion_id)
        if existing or not prestacion:
            return 0

        ultima_transaccion = (
            db.session.execute(
                select(PrestacionAcumulada)
                .where(
                    PrestacionAcumulada.empleado_id == empleado_id,
                    PrestacionAcumulada.prestacion_id == prestacion_id,
                    PrestacionAcumulada.empresa_id == planilla.empresa_id,
                )
                .order_by(PrestacionAcumulada.fecha_transaccion.desc(), PrestacionAcumulada.creado.desc())
                .limit(1)
            )
            .unique()
            .scalars()
            .first()
        )
        saldo_anterior = ultima_transaccion.saldo_nuevo if ultima_transaccion else Decimal("0.00")
        if (
            prestacion.tipo_acumulacion == TipoAcumulacionPrestacion.MENSUAL
            and ultima_transaccion
            and (ultima_transaccion.anio != periodo_anio or ultima_transaccion.mes != periodo_mes)
        ):
            saldo_anterior = Decimal("0.00")

        monto_transaccion = round_money(Decimal(str(monto_total or 0)))
        saldo_nuevo = round_money(saldo_anterior + monto_transaccion)
        db.session.add(
            PrestacionAcumulada(
                empleado_id=empleado_id,
                prestacion_id=prestacion_id,
                fecha_transaccion=fecha_transaccion,
                tipo_transaccion="adicion",
                anio=periodo_anio,
                mes=periodo_mes,
                moneda_id=moneda_id,
                monto_transaccion=monto_transaccion,
                saldo_anterior=saldo_anterior,
                saldo_nuevo=saldo_nuevo,
                nomina_id=nomina.id,
                empresa_id=planilla.empresa_id,
                observaciones=(
                    f"Provisión nómina {nomina.periodo_inicio.strftime('%Y-%m-%d')} - "
                    f"{nomina.periodo_fin.strftime('%Y-%m-%d')}"
                ),
                procesado_por=procesado_por,
                creado_por=creado_por,
            )
        )
        return 1
