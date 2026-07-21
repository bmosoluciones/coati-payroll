# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Routes for nomina execution and management."""

from datetime import date
from typing import Any, cast
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coati_payroll.log import log
from coati_payroll.model import (
    db,
    Planilla,
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    NominaNovedad,
    NominaProgress,
    Empleado,
    Percepcion,
    Deduccion,
    PlanillaEmpleado,
    VacationNovelty,
    VacationNominaNovedad,
    VacationLedger,
)
from coati_payroll.enums import NominaEstado, NovedadEstado, VacacionEstado
from coati_payroll.i18n import _
from coati_payroll.nomina_engine.processors.accounting_processor import AccountingProcessor
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.vistas.planilla import planilla_bp
from coati_payroll.vistas.planilla.services import NominaService, NovedadService
from coati_payroll.queue.tasks import retry_failed_nomina
from coati_payroll.vacation_service import VacationService

# Constants
ROUTE_EJECUTAR_NOMINA = "planilla.ejecutar_nomina"
ROUTE_VER_NOMINA = "planilla.ver_nomina"
ROUTE_LISTAR_NOMINAS = "planilla.listar_nominas"
ERROR_NOMINA_NO_PERTENECE = "La nómina no pertenece a esta planilla."


@planilla_bp.route("/<planilla_id>/ejecutar", methods=["GET", "POST"])
@require_write_access()
def ejecutar_nomina(planilla_id: str):
    """Execute a payroll run for a planilla."""
    planilla = db.get_or_404(Planilla, planilla_id)

    if request.method == "POST":
        periodo_inicio_str = request.form.get("periodo_inicio")
        periodo_fin_str = request.form.get("periodo_fin")
        fecha_calculo_str = request.form.get("fecha_calculo")

        if not periodo_inicio_str or not periodo_fin_str:
            flash(_("Debe especificar el período de la nómina."), "error")
            return redirect(url_for(ROUTE_EJECUTAR_NOMINA, planilla_id=planilla_id))

        # Parse dates
        try:
            periodo_inicio_date = date.fromisoformat(periodo_inicio_str)
            periodo_fin_date = date.fromisoformat(periodo_fin_str)
            fecha_calculo_date = date.fromisoformat(fecha_calculo_str) if fecha_calculo_str else date.today()
        except ValueError:
            flash(_("Formato de fecha inválido."), "error")
            return redirect(url_for(ROUTE_EJECUTAR_NOMINA, planilla_id=planilla_id))

        nomina, errors, warnings = NominaService.ejecutar_nomina(
            planilla=planilla,
            periodo_inicio=periodo_inicio_date,
            periodo_fin=periodo_fin_date,
            fecha_calculo=fecha_calculo_date,
            usuario=current_user.usuario,
        )

        if errors:
            for error in errors:
                flash(error, "error")

        if warnings:
            for warning in warnings:
                flash(warning, "warning")

        if nomina:
            if nomina.procesamiento_en_background:
                num_empleados = nomina.total_empleados or 0
                flash(
                    _(
                        "La nómina está siendo calculada en segundo plano. "
                        "Se procesarán %(num)d empleados. "
                        "Por favor, revise el progreso en unos momentos.",
                        num=num_empleados,
                    ),
                    "info",
                )
            else:
                flash(_("Nómina generada exitosamente."), "success")
            return redirect(
                url_for(
                    ROUTE_VER_NOMINA,
                    planilla_id=planilla_id,
                    nomina_id=nomina.id,
                )
            )
        return redirect(url_for(ROUTE_EJECUTAR_NOMINA, planilla_id=planilla_id))

    # GET - show execution form
    periodo_inicio_sugerido, periodo_fin_sugerido = NominaService.calcular_periodo_sugerido(planilla)
    hoy = date.today()

    # Get last nomina for reference
    ultima_nomina = db.session.execute(
        db.select(Nomina).filter_by(planilla_id=planilla_id).order_by(Nomina.periodo_fin.desc())
    ).scalar_one_or_none()

    return render_template(
        "modules/planilla/ejecutar_nomina.html",
        planilla=planilla,
        periodo_inicio=periodo_inicio_sugerido,
        periodo_fin=periodo_fin_sugerido,
        fecha_calculo=hoy,
        ultima_nomina=ultima_nomina,
    )


@planilla_bp.route("/<planilla_id>/nominas", methods=["GET"])
@require_read_access()
def listar_nominas(planilla_id: str):
    """List all nominas for a planilla."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nominas = (
        db.session.execute(db.select(Nomina).filter_by(planilla_id=planilla_id).order_by(Nomina.periodo_fin.desc()))
        .scalars()
        .all()
    )
    _apply_progress_snapshots(cast(list[Nomina], nominas))

    return render_template(
        "modules/planilla/listar_nominas.html",
        planilla=planilla,
        nominas=nominas,
    )


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>", methods=["GET"])
@require_read_access()
def ver_nomina(planilla_id: str, nomina_id: str):
    """View details of a specific nomina."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nomina = db.get_or_404(Nomina, nomina_id)
    _apply_progress_snapshots([nomina])

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    nomina_empleados = db.session.execute(db.select(NominaEmpleado).filter_by(nomina_id=nomina_id)).scalars().all()

    # Check for errors and warnings in the processing log
    has_errors = _nomina_has_errors(nomina)
    has_warnings = _nomina_has_warnings(nomina)

    # Get error and warning messages for display
    error_messages = []
    warning_messages = []
    if nomina.log_procesamiento:
        for entry in nomina.log_procesamiento:
            status = entry.get("status") or entry.get("tipo")
            message = entry.get("message") or entry.get("mensaje") or ""
            if status == "error":
                error_messages.append(message)
            elif status in ("warning", "advertencia_contabilidad"):
                warning_messages.append(message)

    return render_template(
        "modules/planilla/ver_nomina.html",
        planilla=planilla,
        nomina=nomina,
        nomina_empleados=nomina_empleados,
        has_errors=has_errors,
        has_warnings=has_warnings,
        error_messages=error_messages,
        warning_messages=warning_messages,
    )


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/vacaciones/aplicar", methods=["GET", "POST"])
@require_write_access()
def aplicar_vacaciones_nomina(planilla_id: str, nomina_id: str):
    """Apply approved vacations to a nomina by creating novelties."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    if nomina.estado in (NominaEstado.APLICADO, NominaEstado.PAGADO):
        flash(_("No se pueden aplicar vacaciones en una nómina ya aplicada o pagada."), "warning")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    percepciones = (
        db.session.execute(db.select(Percepcion).filter(Percepcion.activo.is_(True)).order_by(Percepcion.codigo))
        .scalars()
        .all()
    )
    deducciones = (
        db.session.execute(db.select(Deduccion).filter(Deduccion.activo.is_(True)).order_by(Deduccion.codigo))
        .scalars()
        .all()
    )

    vacaciones_pendientes = _obtener_vacaciones_aprobadas_pendientes(planilla, nomina)

    if request.method == "POST":
        return _process_vacation_application(
            planilla, nomina, vacaciones_pendientes, percepciones, deducciones
        )

    return render_template(
        "modules/planilla/aplicar_vacaciones.html",
        planilla=planilla,
        nomina=nomina,
        vacaciones=vacaciones_pendientes,
        percepciones=percepciones,
        deducciones=deducciones,
        tipo_concepto="income",
        percepcion_id=None,
        deduccion_id=None,
    )


def _process_vacation_application(planilla, nomina, vacaciones_pendientes, percepciones, deducciones):
    """Process POST request for vacation application."""
    seleccionadas = request.form.getlist("vacation_ids")
    tipo_concepto = request.form.get("tipo_concepto")
    percepcion_id = request.form.get("percepcion_id") if tipo_concepto == "income" else None
    deduccion_id = request.form.get("deduccion_id") if tipo_concepto == "deduction" else None

    template_ctx = dict(
        planilla=planilla, nomina=nomina, vacaciones=vacaciones_pendientes,
        percepciones=percepciones, deducciones=deducciones,
        tipo_concepto=tipo_concepto, percepcion_id=percepcion_id, deduccion_id=deduccion_id,
    )

    if not seleccionadas:
        flash(_("Debe seleccionar al menos una solicitud de vacaciones."), "warning")
        return render_template("modules/planilla/aplicar_vacaciones.html", **template_ctx)

    concepto = _resolve_vacation_concept(tipo_concepto, percepcion_id, deduccion_id)
    if not concepto:
        flash(_("Debe seleccionar un concepto válido para aplicar las vacaciones."), "danger")
        return render_template("modules/planilla/aplicar_vacaciones.html", **template_ctx)

    applied_count = _apply_vacation_novelties(
        seleccionadas, nomina, concepto.codigo, percepcion_id, deduccion_id
    )

    if applied_count:
        db.session.commit()
        flash(_(f"Se aplicaron {applied_count} vacaciones a la nómina."), "success")
    else:
        db.session.rollback()
        flash(_("No se aplicaron vacaciones. Verifique la selección."), "warning")

    return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla.id, nomina_id=nomina.id))


def _resolve_vacation_concept(tipo_concepto, percepcion_id, deduccion_id):
    """Resolve the concept entity for vacation application."""
    if tipo_concepto == "income":
        return db.session.get(Percepcion, percepcion_id) if percepcion_id else None
    elif tipo_concepto == "deduction":
        return db.session.get(Deduccion, deduccion_id) if deduccion_id else None
    return None


def _apply_vacation_novelties(seleccionadas, nomina, codigo_concepto, percepcion_id, deduccion_id):
    """Apply vacation novelties for selected vacation requests."""
    applied_count = 0
    for vacation_id in seleccionadas:
        vacation = db.session.get(VacationNovelty, vacation_id)
        if not vacation or vacation.estado != VacacionEstado.APROBADO:
            continue

        existing_bridge = db.session.execute(
            db.select(VacationNominaNovedad).filter(VacationNominaNovedad.vacation_novelty_id == vacation.id)
        ).scalar_one_or_none()
        if existing_bridge:
            continue

        tipo_valor = "horas" if (vacation.account and vacation.account.policy and vacation.account.policy.unit_type == "hours") else "dias"
        fecha_novedad = max(vacation.start_date, nomina.periodo_inicio)
        es_inasistencia, descontar_pago_inasistencia = NovedadService.resolve_absence_flags(
            percepcion_id=percepcion_id, deduccion_id=deduccion_id,
        )

        nomina_novedad = NominaNovedad(
            nomina_id=nomina.id, empleado_id=vacation.empleado_id,
            tipo_valor=tipo_valor, codigo_concepto=codigo_concepto,
            valor_cantidad=vacation.units, fecha_novedad=fecha_novedad,
            percepcion_id=percepcion_id, deduccion_id=deduccion_id,
            es_inasistencia=es_inasistencia, descontar_pago_inasistencia=descontar_pago_inasistencia,
            es_descanso_vacaciones=True, vacation_novelty_id=vacation.id,
            fecha_inicio_descanso=vacation.start_date, fecha_fin_descanso=vacation.end_date,
            estado=NovedadEstado.PENDIENTE, creado_por=current_user.usuario,
        )
        db.session.add(nomina_novedad)
        db.session.flush()

        bridge = VacationNominaNovedad(
            vacation_novelty_id=vacation.id, nomina_id=nomina.id,
            nomina_novedad_id=nomina_novedad.id, aplicado_por=current_user.usuario,
        )
        db.session.add(bridge)

        vacation.estado = VacacionEstado.APLICADO
        vacation.modificado_por = current_user.usuario
        applied_count += 1

    return applied_count


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/empleado/<nomina_empleado_id>", methods=["GET"])
@require_read_access()
def ver_nomina_empleado(planilla_id: str, nomina_id: str, nomina_empleado_id: str):
    """View details of an employee's payroll."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nomina = db.get_or_404(Nomina, nomina_id)
    nomina_empleado = db.get_or_404(NominaEmpleado, nomina_empleado_id)

    if nomina_empleado.nomina_id != nomina_id:
        flash(_("El detalle no pertenece a esta nómina."), "error")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    detalles = (
        db.session.execute(
            db.select(NominaDetalle).filter_by(nomina_empleado_id=nomina_empleado_id).order_by(NominaDetalle.orden)
        )
        .scalars()
        .all()
    )

    # Separate by type
    percepciones = [d for d in detalles if d.tipo == "income"]
    deducciones = [d for d in detalles if d.tipo == "deduction"]
    prestaciones = [d for d in detalles if d.tipo == "benefit"]

    return render_template(
        "modules/planilla/ver_nomina_empleado.html",
        planilla=planilla,
        nomina=nomina,
        nomina_empleado=nomina_empleado,
        percepciones=percepciones,
        deducciones=deducciones,
        prestaciones=prestaciones,
    )


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/progreso", methods=["GET"])
@require_read_access()
def progreso_nomina(planilla_id: str, nomina_id: str):
    """API endpoint to check calculation progress of a nomina."""
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        return jsonify({"error": "Nomina does not belong to this planilla"}), 404

    progress = _get_nomina_progress_snapshot(nomina_id)
    snapshot = progress or nomina
    return jsonify(
        {
            "estado": nomina.estado,
            "total_empleados": snapshot.total_empleados or 0,
            "empleados_procesados": snapshot.empleados_procesados or 0,
            "empleados_con_error": snapshot.empleados_con_error or 0,
            "progreso_porcentaje": (
                int((snapshot.empleados_procesados / snapshot.total_empleados) * 100)
                if snapshot.total_empleados and snapshot.total_empleados > 0
                else 0
            ),
            "errores_calculo": snapshot.errores_calculo or {},
            "procesamiento_en_background": nomina.procesamiento_en_background,
            "empleado_actual": snapshot.empleado_actual or "",
            "log_procesamiento": snapshot.log_procesamiento or [],
        }
    )


def _nomina_has_errors(nomina: Nomina) -> bool:
    """Check if a nomina has errors in its processing log."""
    if not nomina.log_procesamiento:
        return False
    for entry in nomina.log_procesamiento:
        status = entry.get("status") or entry.get("tipo")
        if status == "error":
            return True
    return False


def _nomina_has_warnings(nomina: Nomina) -> bool:
    """Check if a nomina has warnings in its processing log."""
    if not nomina.log_procesamiento:
        return False
    for entry in nomina.log_procesamiento:
        status = entry.get("status") or entry.get("tipo")
        if status in ("warning", "advertencia_contabilidad"):
            return True
    return False


def _get_nomina_progress_snapshot(nomina_id: str) -> NominaProgress | None:
    return db.session.execute(db.select(NominaProgress).filter(NominaProgress.nomina_id == nomina_id)).scalars().first()


def _apply_progress_snapshots(nominas: list[Nomina]) -> None:
    if not nominas:
        return

    nomina_ids = [nomina.id for nomina in nominas if nomina.id]
    progress_rows = (
        db.session.execute(db.select(NominaProgress).filter(NominaProgress.nomina_id.in_(nomina_ids))).scalars().all()
    )
    progress_by_nomina = {progress.nomina_id: progress for progress in progress_rows}

    for nomina in nominas:
        progress = progress_by_nomina.get(nomina.id)
        if not progress:
            continue
        nomina.total_empleados = progress.total_empleados
        nomina.empleados_procesados = progress.empleados_procesados
        nomina.empleados_con_error = progress.empleados_con_error
        nomina.errores_calculo = progress.errores_calculo
        nomina.log_procesamiento = progress.log_procesamiento
        nomina.empleado_actual = progress.empleado_actual


def _obtener_vacaciones_aprobadas_pendientes(planilla: Planilla, nomina: Nomina) -> list[VacationNovelty]:
    stmt = (
        db.select(VacationNovelty)
        .join(PlanillaEmpleado, PlanillaEmpleado.empleado_id == VacationNovelty.empleado_id)
        .outerjoin(VacationNominaNovedad, VacationNominaNovedad.vacation_novelty_id == VacationNovelty.id)
        .filter(
            PlanillaEmpleado.planilla_id == planilla.id,
            PlanillaEmpleado.activo.is_(True),
            VacationNovelty.estado == VacacionEstado.APROBADO,
            VacationNovelty.start_date <= nomina.periodo_fin,
            VacationNovelty.end_date >= nomina.periodo_inicio,
            VacationNominaNovedad.id.is_(None),
        )
        .order_by(VacationNovelty.start_date, VacationNovelty.end_date)
    )
    return list(db.session.execute(stmt).scalars().all())


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/aprobar", methods=["POST"])
@require_write_access()
def aprobar_nomina(planilla_id: str, nomina_id: str):
    """Approve a nomina for payment."""
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    if nomina.estado == NominaEstado.GENERADO_CON_ERRORES:
        flash(
            _("Nómina calculada con errores: corrija empleados fallidos y recalcule antes de aprobar/aplicar/pagar."),
            "error",
        )
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    if nomina.estado != "generated":
        flash(_("Solo se pueden aprobar nóminas en estado 'generated'."), "error")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    # Check for errors in the processing log - cannot approve with errors
    if _nomina_has_errors(nomina):
        flash(
            _(
                "No se puede aprobar una nómina con errores de procesamiento. "
                "Corrija los errores y recalcule la nómina antes de aprobar."
            ),
            "error",
        )
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    nomina.estado = "approved"
    nomina.modificado_por = current_user.usuario
    db.session.commit()

    flash(_("Nómina aprobada exitosamente."), "success")
    return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/aplicar", methods=["POST"])
@require_write_access()
def aplicar_nomina(planilla_id: str, nomina_id: str):
    """Mark a nomina as applied (paid)."""
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    if nomina.estado == NominaEstado.GENERADO_CON_ERRORES:
        flash(
            _("Nómina calculada con errores: corrija empleados fallidos y recalcule antes de aprobar/aplicar/pagar."),
            "error",
        )
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    if nomina.estado != "approved":
        flash(_("Solo se pueden aplicar nóminas en estado 'approved'."), "error")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    nomina.estado = "applied"
    nomina.modificado_por = current_user.usuario

    # Actualizar estado de todas las novedades asociadas a "ejecutada"
    planilla = db.get_or_404(Planilla, planilla_id)
    planilla_empleados = cast(list[Any], planilla.planilla_empleados)
    empleado_ids = [pe.empleado_id for pe in planilla_empleados if pe.activo]

    # Actualizar novedades que corresponden a este período
    novedades = (
        db.session.execute(
            db.select(NominaNovedad).filter(
                NominaNovedad.empleado_id.in_(empleado_ids),
                NominaNovedad.fecha_novedad >= nomina.periodo_inicio,
                NominaNovedad.fecha_novedad <= nomina.periodo_fin,
                NominaNovedad.estado == NovedadEstado.PENDIENTE,
            )
        )
        .scalars()
        .all()
    )

    for novedad in novedades:
        novedad.estado = NovedadEstado.EJECUTADA
        novedad.modificado_por = current_user.usuario

    _aplicar_prestaciones_nomina(nomina, planilla, current_user.usuario)
    _aplicar_vacaciones_nomina(nomina, planilla, current_user.usuario)

    db.session.commit()

    flash(
        _("Nómina aplicada exitosamente. {} novedad(es) marcadas como ejecutadas.").format(len(novedades)),
        "success",
    )
    return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))


def _aplicar_prestaciones_nomina(nomina: Nomina, planilla: Planilla, usuario: str | None) -> None:
    """Apply prestaciones ledger side effects for an applied/paid nomina.

    This function is idempotent: if transactions already exist for the same
    (nomina, empleado, prestacion), they are skipped.
    """
    created_count = AccountingProcessor().create_prestacion_transactions_for_nomina(
        nomina=nomina,
        planilla=planilla,
        usuario=usuario,
    )

    if created_count:
        log.debug("Created %s prestaciones transactions for nomina %s", created_count, nomina.id)
    else:
        log.debug("No new prestaciones transactions created for nomina %s", nomina.id)


def _aplicar_vacaciones_nomina(nomina: Nomina, planilla: Planilla, usuario: str | None) -> None:
    """Apply vacation ledger side effects for an applied nomina.

    This function is idempotent - it only creates ledger entries if they don't already exist.
    If vacation accruals were already persisted during payroll generation (normal case),
    this function will skip creating duplicate entries.
    """
    # Check if vacation ledger entries already exist for this nomina
    nomina_empleados = db.session.execute(db.select(NominaEmpleado).filter_by(nomina_id=nomina.id)).scalars().all()
    nomina_empleado_ids = [ne.id for ne in nomina_empleados if ne.id]

    if nomina_empleado_ids:
        existing_entries = (
            db.session.execute(
                db.select(VacationLedger).filter(
                    VacationLedger.reference_type == "nomina_empleado",
                    VacationLedger.reference_id.in_(nomina_empleado_ids),
                )
            )
            .scalars()
            .first()
        )

        if existing_entries:
            # Vacation accruals already exist, skip to avoid duplicates
            log.debug(
                "Vacation accruals already exist for nomina %s, skipping re-application",
                nomina.id,
            )
            return

    # Accruals don't exist (e.g., old nomina from before refactor), create them now
    vacation_snapshot: dict = {}
    if nomina.catalogos_snapshot:
        vacation_snapshot = (nomina.catalogos_snapshot.get("vacaciones") or {}).copy()
    vacation_snapshot["configuracion"] = nomina.configuracion_snapshot or {}

    vacation_service = VacationService(
        planilla=planilla,
        periodo_inicio=nomina.periodo_inicio,
        periodo_fin=nomina.periodo_fin,
        snapshot=vacation_snapshot,
        apply_side_effects=True,
    )

    for nomina_empleado in nomina_empleados:
        empleado = nomina_empleado.empleado or db.session.get(Empleado, nomina_empleado.empleado_id)
        if not empleado or not empleado.activo:
            continue
        # Persist accruals and vacation usage only when the payroll is applied.
        vacation_service.acumular_vacaciones_empleado(empleado, nomina_empleado, usuario)
        vacation_service.procesar_novedades_vacaciones(empleado, {}, usuario)


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/reintentar", methods=["POST"])
@require_write_access()
def reintentar_nomina(planilla_id: str, nomina_id: str):
    """Retry processing a failed nomina."""
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    if nomina.estado != NominaEstado.ERROR:
        flash(_("Solo se pueden reintentar nóminas en estado 'error'."), "error")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    # Call the retry function
    result = retry_failed_nomina(nomina_id, current_user.usuario)

    if result.get("success"):
        flash(
            _("Reintento de nómina iniciado exitosamente. El procesamiento se realizará en segundo plano."), "success"
        )
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))
    flash(_("Error al reintentar la nómina: {}").format(result.get("error", "Error desconocido")), "error")
    return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/recalcular", methods=["POST"])
@require_write_access()
def recalcular_nomina(planilla_id: str, nomina_id: str):
    """Recalculate an existing nomina."""
    nomina = db.get_or_404(Nomina, nomina_id)
    planilla = db.get_or_404(Planilla, planilla_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    if nomina.estado == "applied":
        flash(_("No se puede recalcular una nómina en estado 'applied' (paid)."), "error")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    new_nomina, errors, warnings = NominaService.recalcular_nomina(nomina, planilla, current_user.usuario)

    if errors:
        for error in errors:
            flash(error, "error")

    if warnings:
        for warning in warnings:
            flash(warning, "warning")

    if new_nomina:
        flash(_("Nómina recalculada exitosamente."), "success")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=new_nomina.id))
    flash(_("Error al recalcular la nómina."), "error")
    return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/log", methods=["GET"])
@require_read_access()
def ver_log_nomina(planilla_id: str, nomina_id: str):
    """View execution log for a nomina including warnings and errors."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    # Get log entries
    log_entries = nomina.log_procesamiento or []

    # Get comprobante warnings if exists
    from coati_payroll.model import ComprobanteContable

    comprobante = db.session.execute(db.select(ComprobanteContable).filter_by(nomina_id=nomina_id)).scalar_one_or_none()

    comprobante_warnings = comprobante.advertencias if comprobante else []

    return render_template(
        "modules/planilla/log_nomina.html",
        planilla=planilla,
        nomina=nomina,
        log_entries=log_entries,
        comprobante_warnings=comprobante_warnings,
    )


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/regenerar-comprobante", methods=["POST"])
@login_required
@require_write_access()
def regenerar_comprobante_contable(planilla_id: str, nomina_id: str):
    """Regenerate accounting voucher for an applied/paid nomina without recalculating.

    This is useful when accounting configuration was incomplete at the time of calculation
    and has been updated afterwards. Only regenerates the accounting entries based on
    existing payroll calculations.
    """
    planilla = db.get_or_404(Planilla, planilla_id)
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        flash(_("La nómina no pertenece a esta planilla."), "error")
        return redirect(url_for("planilla.listar_nominas", planilla_id=planilla_id))

    # Only allow for applied or paid nominas
    if nomina.estado not in (NominaEstado.APLICADO, NominaEstado.PAGADO):
        flash(
            _(
                "Solo se puede regenerar el comprobante contable para nóminas en estado 'applied' o 'paid'. "
                "Para nóminas en otros estados, use 'recalcular'."
            ),
            "error",
        )
        return redirect(url_for("planilla.ver_nomina", planilla_id=planilla_id, nomina_id=nomina_id))

    try:
        from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService

        accounting_service = AccountingVoucherService(db.session)

        # Regenerate voucher using existing nomina data
        fecha_calculo = nomina.fecha_calculo_original or nomina.periodo_fin
        usuario = current_user.nombre_usuario if current_user and current_user.is_authenticated else None
        comprobante = accounting_service.generate_audit_voucher(nomina, planilla, fecha_calculo, usuario)

        db.session.commit()

        flash(_("Comprobante contable regenerado exitosamente."), "success")

        # Show warnings if configuration is still incomplete
        if comprobante.advertencias:
            for warning in comprobante.advertencias:
                flash(warning, "warning")

    except Exception as e:
        db.session.rollback()
        flash(_("Error al regenerar comprobante contable: {}").format(str(e)), "error")

    return redirect(url_for("planilla.ver_log_nomina", planilla_id=planilla_id, nomina_id=nomina_id))
