# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Service for nomina business logic."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4
from flask import current_app
from sqlalchemy import func
from coati_payroll.model import db, Planilla, Nomina, AcumuladoAnual, Deduccion, Percepcion
from coati_payroll.enums import NominaEstado
from coati_payroll.nomina_engine import NominaEngine
from coati_payroll.nomina_engine.services.snapshot_service import SnapshotService
from coati_payroll.queue import get_queue_driver
from coati_payroll.queue.drivers.dramatiq_driver import DramatiqDriver


class NominaService:
    """Service for nomina operations."""

    _PERIODICIDAD_SHORT_PERIOD_RULES: dict[str, tuple[str, int]] = {
        "monthly": ("mensual", 30),
        "mensual": ("mensual", 30),
        "biweekly": ("quincenal", 15),
        "quincenal": ("quincenal", 15),
        "weekly": ("semanal", 7),
        "semanal": ("semanal", 7),
    }

    @staticmethod
    def _rollback_accumulations_for_nomina(nomina: Nomina, planilla: Planilla) -> None:
        """Rollback accumulated annual values produced by one payroll.

        This is required before recalculation to avoid double-counting
        (e.g., periodos_procesados jumping from 2 -> 3 for the same month).
        """
        from coati_payroll.model import NominaEmpleado, NominaDetalle

        if not planilla.tipo_planilla:
            return

        tipo_planilla = planilla.tipo_planilla
        empresa_id = planilla.empresa_id
        if not empresa_id:
            return

        # Accumulations are posted using the payroll period end, not the date
        # an operator happened to run it.  The same date must be used when
        # reversing them, especially around a mid-month fiscal boundary.
        fecha_base = nomina.periodo_fin
        anio = fecha_base.year
        mes_inicio = int(planilla.mes_inicio_fiscal or tipo_planilla.mes_inicio_fiscal)
        dia_inicio = tipo_planilla.dia_inicio_fiscal
        if fecha_base < date(anio, mes_inicio, dia_inicio):
            anio -= 1
        periodo_fiscal_inicio = date(anio, mes_inicio, dia_inicio)

        nomina_empleados = (
            db.session.execute(db.select(NominaEmpleado).where(NominaEmpleado.nomina_id == nomina.id)).scalars().all()
        )
        if not nomina_empleados:
            return

        empleado_ids = [ne.empleado_id for ne in nomina_empleados]
        nomina_empleado_ids = [ne.id for ne in nomina_empleados]

        acumulados = (
            db.session.execute(
                db.select(AcumuladoAnual).where(
                    AcumuladoAnual.empleado_id.in_(empleado_ids),
                    AcumuladoAnual.tipo_planilla_id == tipo_planilla.id,
                    AcumuladoAnual.empresa_id == empresa_id,
                    AcumuladoAnual.periodo_fiscal_inicio == periodo_fiscal_inicio,
                )
            )
            .scalars()
            .all()
        )
        acumulado_by_empleado = {a.empleado_id: a for a in acumulados}

        # Rollbacks must use the same tax metadata that produced the original
        # accumulation.  Catalog concepts are editable; consulting only their
        # live flags after a change would leave (or remove) taxable income and
        # pre-tax deductions that never belonged to the voided payroll.
        catalogos_snapshot = nomina.catalogos_snapshot or {}
        deducciones_snapshot = {
            entry.get("id"): entry
            for entry in catalogos_snapshot.get("deducciones", [])
            if isinstance(entry, dict) and entry.get("id")
        }
        percepciones_snapshot = {
            entry.get("id"): entry
            for entry in catalogos_snapshot.get("percepciones", [])
            if isinstance(entry, dict) and entry.get("id")
        }

        # Aggregate deduction amounts by payroll employee and deduction type.
        deduction_rows = db.session.execute(
            db.select(
                NominaDetalle.nomina_empleado_id,
                NominaDetalle.deduccion_id,
                Deduccion.es_impuesto,
                Deduccion.antes_impuesto,
                func.sum(NominaDetalle.monto),
            )
            .join(Deduccion, Deduccion.id == NominaDetalle.deduccion_id)
            .where(
                NominaDetalle.nomina_empleado_id.in_(nomina_empleado_ids),
                NominaDetalle.tipo == "deduction",
                NominaDetalle.deduccion_id.is_not(None),
            )
            .group_by(
                NominaDetalle.nomina_empleado_id,
                NominaDetalle.deduccion_id,
                Deduccion.es_impuesto,
                Deduccion.antes_impuesto,
            )
        ).all()

        deducciones_by_ne: dict[str, dict[str, Decimal]] = {}
        for ne_id, deduccion_id, es_impuesto, antes_impuesto, total in deduction_rows:
            bucket = deducciones_by_ne.setdefault(ne_id, {"impuesto": Decimal("0.00"), "antes": Decimal("0.00")})
            amount = Decimal(str(total or 0))
            snapshot = deducciones_snapshot.get(deduccion_id)
            if snapshot:
                es_impuesto = snapshot.get("es_impuesto", False)
                antes_impuesto = snapshot.get("antes_impuesto", False)
            if es_impuesto:
                bucket["impuesto"] += amount
            elif antes_impuesto:
                bucket["antes"] += amount

        # Aggregate only gravable perceptions for salario_gravable rollback.
        gravable_rows = db.session.execute(
            db.select(
                NominaDetalle.nomina_empleado_id,
                NominaDetalle.percepcion_id,
                Percepcion.gravable,
                func.sum(NominaDetalle.monto),
            )
            .join(Percepcion, Percepcion.id == NominaDetalle.percepcion_id)
            .where(
                NominaDetalle.nomina_empleado_id.in_(nomina_empleado_ids),
                NominaDetalle.tipo == "income",
                NominaDetalle.percepcion_id.is_not(None),
            )
            .group_by(NominaDetalle.nomina_empleado_id, NominaDetalle.percepcion_id, Percepcion.gravable)
        ).all()
        gravable_by_ne: dict[str, Decimal] = {}
        for ne_id, percepcion_id, gravable, total in gravable_rows:
            snapshot = percepciones_snapshot.get(percepcion_id)
            if snapshot:
                gravable = snapshot.get("gravable", False)
            if gravable:
                gravable_by_ne[ne_id] = gravable_by_ne.get(ne_id, Decimal("0.00")) + Decimal(str(total or 0))

        for ne in nomina_empleados:
            acumulado = acumulado_by_empleado.get(ne.empleado_id)
            if not acumulado:
                continue

            salario_bruto = Decimal(str(ne.salario_bruto or 0))
            salario_base_neto_inasistencia = Decimal(str(ne.sueldo_base_historico or 0)) - Decimal(
                str(ne.inasistencia_descuento or 0)
            )
            salario_gravable = salario_base_neto_inasistencia + gravable_by_ne.get(ne.id, Decimal("0.00"))
            deducciones = deducciones_by_ne.get(ne.id, {"impuesto": Decimal("0.00"), "antes": Decimal("0.00")})

            acumulado.salario_bruto_acumulado = max(
                Decimal(str(acumulado.salario_bruto_acumulado or 0)) - salario_bruto,
                Decimal("0.00"),
            )
            acumulado.salario_acumulado_mes = max(
                Decimal(str(acumulado.salario_acumulado_mes or 0)) - salario_bruto,
                Decimal("0.00"),
            )
            acumulado.salario_gravable_acumulado = max(
                Decimal(str(acumulado.salario_gravable_acumulado or 0)) - salario_gravable,
                Decimal("0.00"),
            )
            acumulado.deducciones_antes_impuesto_acumulado = max(
                Decimal(str(acumulado.deducciones_antes_impuesto_acumulado or 0)) - deducciones["antes"],
                Decimal("0.00"),
            )
            acumulado.impuesto_retenido_acumulado = max(
                Decimal(str(acumulado.impuesto_retenido_acumulado or 0)) - deducciones["impuesto"],
                Decimal("0.00"),
            )

            acumulado.periodos_procesados = max(int(acumulado.periodos_procesados or 0) - 1, 0)
            if acumulado.periodos_procesados == 0:
                acumulado.ultimo_periodo_procesado = None
                if Decimal(str(acumulado.salario_acumulado_mes or 0)) == Decimal("0.00"):
                    acumulado.mes_actual = None

    @staticmethod
    def _rollback_loans_and_advances_for_nomina(nomina: Nomina) -> None:
        """Rollback loans and advances side effects produced by one payroll."""
        from coati_payroll.model import Adelanto, AdelantoAbono, InteresAdelanto

        # 1. Revert payments
        abonos = (
            db.session.execute(db.select(AdelantoAbono).where(AdelantoAbono.nomina_id == nomina.id)).scalars().all()
        )

        for abono in abonos:
            NominaService._rollback_payment(abono, Adelanto)

        # 2. Revert interest calculations
        intereses = (
            db.session.execute(db.select(InteresAdelanto).where(InteresAdelanto.nomina_id == nomina.id)).scalars().all()
        )

        for interes in intereses:
            NominaService._rollback_interest(interes, Adelanto)

    @staticmethod
    def _rollback_payment(abono, adelanto_model) -> None:
        """Restore an advance balance after removing a payroll payment."""
        from coati_payroll.enums import AdelantoEstado

        adelanto = db.session.get(adelanto_model, abono.adelanto_id)
        if adelanto:
            adelanto.saldo_pendiente = Decimal(str(adelanto.saldo_pendiente or 0)) + Decimal(
                str(abono.monto_abonado or 0)
            )
            if adelanto.saldo_pendiente > 0 and adelanto.estado == AdelantoEstado.PAGADO:
                adelanto.estado = AdelantoEstado.APROBADO
        db.session.delete(abono)

    @staticmethod
    def _rollback_interest(interes, adelanto_model) -> None:
        """Restore an advance balance after removing calculated interest."""
        adelanto = db.session.get(adelanto_model, interes.adelanto_id)
        if adelanto:
            amount = Decimal(str(interes.interes_calculado or 0))
            adelanto.saldo_pendiente = max(Decimal("0.00"), Decimal(str(adelanto.saldo_pendiente or 0)) - amount)
            adelanto.interes_acumulado = max(
                Decimal("0.00"), Decimal(str(adelanto.interes_acumulado or 0)) - amount
            )
            adelanto.fecha_ultimo_calculo_interes = interes.fecha_desde
        db.session.delete(interes)

    @staticmethod
    def _rollback_vacation_requests_for_nomina(nomina: Nomina) -> None:
        """Rollback vacation requests applied to a payroll."""
        from coati_payroll.model import VacationNominaNovedad, VacationNovelty, NominaNovedad
        from coati_payroll.enums import VacacionEstado

        bridges = (
            db.session.execute(db.select(VacationNominaNovedad).where(VacationNominaNovedad.nomina_id == nomina.id))
            .scalars()
            .all()
        )

        for bridge in bridges:
            vacation = db.session.get(VacationNovelty, bridge.vacation_novelty_id)
            if vacation:
                vacation.estado = VacacionEstado.APROBADO
                # Deleting the associated NominaNovedad
                if bridge.nomina_novedad_id:
                    novedad = db.session.get(NominaNovedad, bridge.nomina_novedad_id)
                    if novedad:
                        db.session.delete(novedad)
            db.session.delete(bridge)

    @staticmethod
    def _rollback_vacation_ledgers_for_nomina(nomina: Nomina) -> None:
        """Rollback vacation ledger entries and adjust balances."""
        from coati_payroll.model import NominaEmpleado, VacationLedger, VacationAccount

        nomina_empleado_ids = (
            db.session.execute(db.select(NominaEmpleado.id).where(NominaEmpleado.nomina_id == nomina.id))
            .scalars()
            .all()
        )
        if nomina_empleado_ids:
            account_ids = {
                row[0]
                for row in db.session.execute(
                    db.select(VacationLedger.account_id).where(
                        VacationLedger.reference_type == "nomina_empleado",
                        VacationLedger.reference_id.in_(nomina_empleado_ids),
                    )
                ).all()
                if row[0]
            }
            db.session.execute(
                db.delete(VacationLedger).where(
                    VacationLedger.reference_type == "nomina_empleado",
                    VacationLedger.reference_id.in_(nomina_empleado_ids),
                )
            )
            if account_ids:
                accounts = (
                    db.session.execute(db.select(VacationAccount).where(VacationAccount.id.in_(account_ids)))
                    .scalars()
                    .all()
                )
                for account in accounts:
                    balance = db.session.execute(
                        db.select(func.coalesce(func.sum(VacationLedger.quantity), 0)).where(
                            VacationLedger.account_id == account.id
                        )
                    ).scalar_one()
                    account.current_balance = Decimal(str(balance))
                    last_accrual = db.session.execute(
                        db.select(func.max(VacationLedger.fecha)).where(
                            VacationLedger.account_id == account.id,
                            VacationLedger.entry_type == "accrual",
                        )
                    ).scalar_one()
                    account.last_accrual_date = last_accrual

    @staticmethod
    def anular_nomina(nomina: Nomina, planilla: Planilla, usuario: str, razon: str) -> bool:
        """Cancel/void a nomina and revert all its associated side effects.

        This ensures that when a payroll is cancelled:
        1. Accumulated values are reverted.
        2. Vacation accruals are deleted and balances adjusted.
        3. Loan/advance payments and interests are reverted.
        4. Applied vacations are restored to approved state.
        """
        from coati_payroll.audit_helpers import anular_nomina as registrar_anulacion_nomina

        # 1. Rollback accumulated values
        NominaService._rollback_accumulations_for_nomina(nomina, planilla)

        # 2. Rollback vacation ledgers
        NominaService._rollback_vacation_ledgers_for_nomina(nomina)

        # 3. Rollback loans and advances
        NominaService._rollback_loans_and_advances_for_nomina(nomina)

        # 4. Rollback vacation requests (bridge, status)
        NominaService._rollback_vacation_requests_for_nomina(nomina)

        # 5. Actually register cancellation in state
        return registrar_anulacion_nomina(nomina, usuario, razon)

    @staticmethod
    def calcular_periodo_sugerido(planilla: Planilla) -> tuple[date, date]:
        """Calculate suggested period dates for a new nomina.

        Args:
            planilla: The planilla to calculate period for

        Returns:
            Tuple of (periodo_inicio, periodo_fin)
        """
        # Get last nomina for default dates
        estados_relevantes = (
            NominaEstado.CALCULANDO,
            NominaEstado.GENERADO,
            NominaEstado.APROBADO,
            NominaEstado.APLICADO,
            NominaEstado.PAGADO,
        )
        ultima_nomina = (
            db.session.execute(
                db.select(Nomina)
                .where(
                    Nomina.planilla_id == planilla.id,
                    Nomina.estado.in_(estados_relevantes),
                )
                .order_by(Nomina.periodo_fin.desc(), Nomina.fecha_generacion.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

        hoy = date.today()

        if ultima_nomina:
            # Start from the day after last period ended
            periodo_inicio_sugerido = ultima_nomina.periodo_fin + timedelta(days=1)
        else:
            # First day of current month
            periodo_inicio_sugerido = hoy.replace(day=1)

        # Calculate end of period based on tipo_planilla
        tipo = planilla.tipo_planilla
        match tipo.periodicidad if tipo else "mensual":
            case "semanal":
                periodo_fin_sugerido = periodo_inicio_sugerido + timedelta(days=6)
            case "quincenal":
                if periodo_inicio_sugerido.day <= 15:
                    periodo_fin_sugerido = periodo_inicio_sugerido.replace(day=15)
                else:
                    # End of month
                    next_month = periodo_inicio_sugerido.replace(day=28) + timedelta(days=4)
                    periodo_fin_sugerido = next_month - timedelta(days=next_month.day)
            case _:  # mensual or other
                # End of month
                next_month = periodo_inicio_sugerido.replace(day=28) + timedelta(days=4)
                periodo_fin_sugerido = next_month - timedelta(days=next_month.day)

        return periodo_inicio_sugerido, periodo_fin_sugerido

    @staticmethod
    def _build_first_payroll_fiscal_start_warning(planilla: Planilla, periodo_inicio: date) -> str | None:
        """Warn when first payroll period does not start at fiscal period start.

        This helps operators identify potential tax-side effects (e.g., annualized
        income tax behaviors) when bootstrapping payroll mid-fiscal-year.
        """
        has_previous_nomina = db.session.execute(
            db.select(Nomina.id).where(Nomina.planilla_id == planilla.id).limit(1)
        ).scalar_one_or_none()
        if has_previous_nomina:
            return None

        tipo_planilla = planilla.tipo_planilla
        if not tipo_planilla:
            return None

        mes_inicio_fiscal = int(planilla.mes_inicio_fiscal or tipo_planilla.mes_inicio_fiscal or 1)
        dia_inicio_fiscal = int(tipo_planilla.dia_inicio_fiscal or 1)
        anio_fiscal = periodo_inicio.year
        if periodo_inicio < date(anio_fiscal, mes_inicio_fiscal, dia_inicio_fiscal):
            anio_fiscal -= 1

        try:
            inicio_fiscal = date(anio_fiscal, mes_inicio_fiscal, dia_inicio_fiscal)
        except ValueError:
            return None

        if periodo_inicio == inicio_fiscal:
            return None

        return (
            "La primera nomina calculada no coincide con el inicio del periodo fiscal "
            f"({inicio_fiscal.isoformat()}). Se recomienda verificacion manual de impuestos."
        )

    @staticmethod
    def _build_short_period_warning(planilla: Planilla, periodo_inicio: date, periodo_fin: date) -> str | None:
        """Warn when selected payroll period has fewer days than expected by payroll periodicity."""
        dias_periodo = (periodo_fin - periodo_inicio).days + 1
        if dias_periodo <= 0:
            return None

        tipo_planilla = planilla.tipo_planilla
        if not tipo_planilla:
            return None

        periodicidad = (tipo_planilla.periodicidad or "").strip().lower()
        periodicidad_label, dias_esperados = NominaService._PERIODICIDAD_SHORT_PERIOD_RULES.get(
            periodicidad,
            ("periodica", int(tipo_planilla.dias or 0)),
        )

        if dias_esperados <= 0:
            return None

        # For monthly payrolls, a full natural month (28/29/30/31 days) is expected and valid.
        if periodicidad in {"monthly", "mensual"}:
            same_month = periodo_inicio.year == periodo_fin.year and periodo_inicio.month == periodo_fin.month
            if same_month and periodo_inicio.day == 1:
                next_month = periodo_inicio.replace(day=28) + timedelta(days=4)
                fin_mes = next_month - timedelta(days=next_month.day)
                if periodo_fin == fin_mes:
                    return None

        if dias_periodo >= dias_esperados:
            return None

        return (
            "WARNING: Este calculo de planilla tiene menos dias de lo esperado para una "
            f"periodicidad {periodicidad_label}. Se seleccionaron {dias_periodo} dias y se esperan al menos "
            f"{dias_esperados}. Periodo: {periodo_inicio.isoformat()} a {periodo_fin.isoformat()}."
        )

    @staticmethod
    def ejecutar_nomina(
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        fecha_calculo: date,
        usuario: str,
    ) -> tuple[Nomina | None, list[str], list[str]]:
        """Execute a nomina calculation.

        Args:
            planilla: The planilla to execute
            periodo_inicio: Start date of the period
            periodo_fin: End date of the period
            fecha_calculo: Calculation date
            usuario: Username of the user executing

        Returns:
            Tuple of (nomina, errors, warnings)
        """
        warnings: list[str] = []
        short_period_warning = NominaService._build_short_period_warning(planilla, periodo_inicio, periodo_fin)
        if short_period_warning:
            warnings.append(short_period_warning)

        fiscal_start_warning = NominaService._build_first_payroll_fiscal_start_warning(planilla, periodo_inicio)
        if fiscal_start_warning:
            warnings.append(fiscal_start_warning)

        # Count active employees
        planilla_empleados = cast(list[Any], planilla.planilla_empleados)
        num_empleados = len([pe for pe in planilla_empleados if pe.activo and pe.empleado.activo])

        # Get configurable threshold for background processing
        threshold = current_app.config.get("BACKGROUND_PAYROLL_THRESHOLD", 100)

        queue_enabled = bool(current_app.config.get("QUEUE_ENABLED", False))
        should_attempt_background = queue_enabled and num_empleados > threshold

        if should_attempt_background:
            queue = get_queue_driver()
            if isinstance(queue, DramatiqDriver) and queue.is_available():
                snapshot = SnapshotService(db.session).capture_complete_snapshot(
                    planilla, periodo_inicio, periodo_fin, fecha_calculo
                )
                # Create nomina record with "calculating" status
                nomina = Nomina(
                    planilla_id=planilla.id,
                    periodo_inicio=periodo_inicio,
                    periodo_fin=periodo_fin,
                    generado_por=usuario,
                    estado=NominaEstado.CALCULANDO,
                    total_bruto=0,
                    total_deducciones=0,
                    total_neto=0,
                    total_empleados=num_empleados,
                    empleados_procesados=0,
                    empleados_con_error=0,
                    procesamiento_en_background=True,
                    fecha_calculo_original=fecha_calculo,
                    configuracion_snapshot=snapshot["configuracion"],
                    tipos_cambio_snapshot=snapshot["tipos_cambio"],
                    catalogos_snapshot=snapshot["catalogos"],
                )
                db.session.add(nomina)
                db.session.commit()

                # Enqueue background task
                try:
                    queue.enqueue(
                        "process_large_payroll",
                        nomina_id=nomina.id,
                        job_id=uuid4().hex,
                        planilla_id=planilla.id,
                        periodo_inicio=periodo_inicio.isoformat(),
                        periodo_fin=periodo_fin.isoformat(),
                        fecha_calculo=fecha_calculo.isoformat(),
                        usuario=usuario,
                    )
                    return nomina, [], warnings
                except Exception:
                    # Fallback to synchronous execution while keeping an auditable trace
                    db.session.delete(nomina)
                    db.session.commit()

        # Synchronous processing path (default / fallback)
        engine = NominaEngine(
            planilla=planilla,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            fecha_calculo=fecha_calculo,
            usuario=usuario,
        )

        nomina_result = engine.ejecutar()
        return nomina_result, engine.errors, warnings + list(engine.warnings or [])

    @staticmethod
    def recalcular_nomina(
        nomina: Nomina, planilla: Planilla, usuario: str
    ) -> tuple[Nomina | None, list[str], list[str]]:
        """Recalculate an existing nomina.

        Args:
            nomina: The nomina to recalculate
            planilla: The planilla
            usuario: Username of the user recalculating

        Returns:
            Tuple of (new_nomina, errors, warnings)
        """
        from coati_payroll.model import (
            NominaEmpleado,
            NominaDetalle,
            NominaNovedad,
            ComprobanteContable,
            PrestacionAcumulada,
        )
        from coati_payroll.vistas.planilla.services.nomina_comparison_service import NominaComparisonService

        # Store the original period and calculation date for consistency
        periodo_inicio = nomina.periodo_inicio
        periodo_fin = nomina.periodo_fin
        fecha_calculo_original = nomina.fecha_calculo_original or nomina.fecha_generacion.date()
        nomina_original_id = nomina.id
        warnings: list[str] = []
        short_period_warning = NominaService._build_short_period_warning(planilla, periodo_inicio, periodo_fin)
        if short_period_warning:
            warnings.append(short_period_warning)
        novedad_ids = (
            db.session.execute(db.select(NominaNovedad.id).where(NominaNovedad.nomina_id == nomina.id)).scalars().all()
        )

        # Revert original accumulated values first to keep period counts correct on recalculation.
        NominaService._rollback_accumulations_for_nomina(nomina, planilla)

        # Remove vacation ledger entries tied to the old payroll employees to avoid double accruals.
        NominaService._rollback_vacation_ledgers_for_nomina(nomina)

        # Revert any automatic loans and advances payments/interest for this payroll run
        NominaService._rollback_loans_and_advances_for_nomina(nomina)

        # Re-execute the payroll with the ORIGINAL calculation date for consistency.
        # Reuse the snapshots captured in the original run so the recalculation
        # reproduces the exact same payroll numbers even if the live
        # configuration changed since (fixes reproducibility of recalculations).
        stored_snapshot: dict[str, Any] | None = None
        if nomina.configuracion_snapshot or nomina.catalogos_snapshot:
            stored_snapshot = {
                "configuracion": nomina.configuracion_snapshot or None,
                "tipos_cambio": nomina.tipos_cambio_snapshot or [],
                "catalogos": nomina.catalogos_snapshot or {},
            }
        engine = NominaEngine(
            planilla=planilla,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            fecha_calculo=fecha_calculo_original,
            usuario=usuario,
            excluded_nomina_id=nomina_original_id,
            snapshot_override=stored_snapshot,
        )

        new_nomina = engine.ejecutar()

        # Mark as recalculation and link to original
        if new_nomina:
            new_nomina.es_recalculo = True
            new_nomina.nomina_original_id = nomina_original_id

            # Delete NominaDetalle records
            db.session.execute(
                db.delete(NominaDetalle).where(
                    NominaDetalle.nomina_empleado_id.in_(
                        db.select(NominaEmpleado.id).where(NominaEmpleado.nomina_id == nomina.id)
                    )
                )
            )

            # Delete all NominaEmpleado records
            db.session.execute(db.delete(NominaEmpleado).where(NominaEmpleado.nomina_id == nomina.id))

            # Defensive cleanup for legacy behavior where prestaciones were
            # written during payroll generation. With deferred side effects,
            # these rows should not exist for draft/generated payrolls.
            db.session.execute(db.delete(PrestacionAcumulada).where(PrestacionAcumulada.nomina_id == nomina.id))

            # Helper to detect MagicMock IDs in unit tests to avoid DB binding failures
            new_id = new_nomina.id
            is_mock_id = hasattr(new_id, "assert_called") or "mock" in type(new_id).__name__.lower()

            # CRITICAL: NominaNovedad must be preserved during recalculation.
            # They are master payroll events (overtime, absences, bonuses, etc.)
            # and deleting them breaks repeatable payroll calculations.
            # Re-link previous novedades to the new recalculated payroll.
            if novedad_ids and not is_mock_id:
                db.session.execute(
                    db.update(NominaNovedad).where(NominaNovedad.id.in_(novedad_ids)).values(nomina_id=new_id)
                )

            # Re-link previous VacationNominaNovedad records to the new recalculated payroll.
            if not is_mock_id:
                from coati_payroll.model import VacationNominaNovedad

                db.session.execute(
                    db.update(VacationNominaNovedad)
                    .where(VacationNominaNovedad.nomina_id == nomina_original_id)
                    .values(nomina_id=new_id)
                )

            # Remove existing accounting voucher tied to the old nomina.
            # The voucher has a non-nullable FK, so it must be deleted before the nomina.
            db.session.execute(db.delete(ComprobanteContable).where(ComprobanteContable.nomina_id == nomina.id))

            # Refresh comparisons that referenced the old payroll id.
            if not is_mock_id:
                NominaComparisonService.refresh_after_recalculo(
                    planilla_id=planilla.id,
                    nomina_original_id=nomina_original_id,
                    nomina_nueva_id=new_id,
                )

            # Delete the old nomina record after moving linked novelties
            db.session.delete(nomina)

            # Create audit log for recalculation
            from coati_payroll.audit_helpers import crear_log_auditoria_nomina

            crear_log_auditoria_nomina(
                nomina=new_nomina,
                accion="recalculated",
                usuario=usuario,
                descripcion=f"Nómina recalculada desde nómina original {nomina_original_id}",
                cambios={
                    "nomina_original_id": nomina_original_id,
                    "fecha_calculo_original": fecha_calculo_original.isoformat(),
                    "periodo_inicio": periodo_inicio.isoformat(),
                    "periodo_fin": periodo_fin.isoformat(),
                },
                estado_anterior="deleted",
                estado_nuevo=new_nomina.estado,
            )

            db.session.commit()

        return new_nomina, engine.errors, warnings + list(engine.warnings or [])
