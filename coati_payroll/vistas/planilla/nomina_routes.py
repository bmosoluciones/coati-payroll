# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Routes for nomina execution and management."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from typing import Any, cast
from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coati_payroll.audit_helpers import anular_nomina as registrar_anulacion_nomina
from coati_payroll.log import log
from coati_payroll.model import (
    db,
    Planilla,
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    NominaNovedad,
    NominaProgress,
    ComprobanteContable,
    ComprobanteContableLinea,
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
from coati_payroll.vistas.planilla.services import NominaService, NovedadService, NominaComparisonService
from coati_payroll.queue.tasks import retry_failed_nomina
from coati_payroll.vacation_service import VacationService
from coati_payroll.nomina_engine.repositories.config_repository import ConfigRepository

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
    ultima_nomina = (
        db.session.execute(
            db.select(Nomina)
            .where(Nomina.planilla_id == planilla_id)
            .order_by(Nomina.periodo_fin.desc(), Nomina.fecha_generacion.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )

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
    nomina = db.session.execute(
        db.select(Nomina).filter(Nomina.id == nomina_id, Nomina.planilla_id == planilla_id)
    ).scalar_one_or_none()
    if not nomina:
        nomina_real = db.session.get(Nomina, nomina_id)
        if nomina_real:
            return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=nomina_real.planilla_id, nomina_id=nomina_id))
        abort(404)
    _apply_progress_snapshots([nomina])

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


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/comparar", methods=["GET"])
@require_read_access()
def comparar_nomina(planilla_id: str, nomina_id: str):
    """Compare selected nomina against another nomina in the same planilla."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nomina_actual = db.session.execute(
        db.select(Nomina).filter(Nomina.id == nomina_id, Nomina.planilla_id == planilla_id)
    ).scalar_one_or_none()
    if not nomina_actual:
        nomina_real = db.session.get(Nomina, nomina_id)
        target_planilla_id = nomina_real.planilla_id if nomina_real else planilla_id
        flash(
            _("No se encontro la comparativa solicitada porque una de las nominas no esta disponible."),
            "warning",
        )
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=target_planilla_id))

    nominas_para_comparar = NominaComparisonService.get_nominas_disponibles(
        planilla_id=planilla_id,
        excluir_nomina_id=nomina_id,
    )
    base_seleccionada_id = request.args.get("nomina_base_id")
    ejecutar = request.args.get("ejecutar") == "1"

    if base_seleccionada_id:
        nomina_base_referenciada = db.session.get(Nomina, base_seleccionada_id)
        if (
            not nomina_base_referenciada
            or nomina_base_referenciada.planilla_id != planilla_id
            or nomina_base_referenciada.id == nomina_actual.id
        ):
            target_planilla_id = nomina_base_referenciada.planilla_id if nomina_base_referenciada else planilla_id
            flash(
                _("No se encontro la comparativa solicitada porque una de las nominas no esta disponible."),
                "warning",
            )
            return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=target_planilla_id))

    nomina_base = None
    comparacion_payload: dict[str, Any] | None = None

    if nominas_para_comparar:
        nomina_base = next((n for n in nominas_para_comparar if n.id == base_seleccionada_id), None)
        if base_seleccionada_id and nomina_base is None:
            flash(_("La nómina base seleccionada no es válida para esta planilla."), "warning")
        if nomina_base is None:
            nomina_base = NominaComparisonService.get_nomina_base_default(nomina_actual)

    if ejecutar and nomina_base:
        comparacion_payload = NominaComparisonService.compare_or_cached(
            planilla=planilla,
            nomina_base=nomina_base,
            nomina_actual=nomina_actual,
        )

    return render_template(
        "modules/planilla/comparar_nomina.html",
        planilla=planilla,
        nomina_actual=nomina_actual,
        nomina_base=nomina_base,
        nominas_para_comparar=nominas_para_comparar,
        comparacion_payload=comparacion_payload,
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

    template_ctx = {
        "planilla": planilla, "nomina": nomina, "vacaciones": vacaciones_pendientes,
        "percepciones": percepciones, "deducciones": deducciones,
        "tipo_concepto": tipo_concepto, "percepcion_id": percepcion_id, "deduccion_id": deduccion_id,
    }

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
    if tipo_concepto == "deduction":
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

        is_hours = vacation.account and vacation.account.policy and vacation.account.policy.unit_type == "hours"
        tipo_valor = "horas" if is_hours else "dias"
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
    salario_base_visual = (nomina_empleado.sueldo_base_historico or 0) - (nomina_empleado.inasistencia_descuento or 0)
    novedades_aplicadas = (
        db.session.execute(
            db.select(NominaNovedad)
            .where(
                NominaNovedad.nomina_id == nomina_id,
                NominaNovedad.empleado_id == nomina_empleado.empleado_id,
            )
            .order_by(NominaNovedad.fecha_novedad.asc(), NominaNovedad.timestamp.asc())
        )
        .scalars()
        .all()
    )

    def _to_decimal(value: Any) -> Decimal:
        if value is None or value == "":
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (ArithmeticError, TypeError, ValueError):
            return Decimal("0")

    comprobante = db.session.execute(db.select(ComprobanteContable).filter_by(nomina_id=nomina_id)).scalar_one_or_none()
    if comprobante:
        vacation_liability_rows = db.session.execute(
            db.select(
                ComprobanteContableLinea.concepto,
                db.func.sum(ComprobanteContableLinea.credito).label("monto_total"),
            )
            .where(
                ComprobanteContableLinea.comprobante_id == comprobante.id,
                ComprobanteContableLinea.nomina_empleado_id == nomina_empleado_id,
                ComprobanteContableLinea.tipo_concepto == "vacation_liability",
                ComprobanteContableLinea.tipo_debito_credito == "credito",
            )
            .group_by(ComprobanteContableLinea.concepto)
            .order_by(ComprobanteContableLinea.concepto.asc())
        ).all()
        for concepto, monto_total in vacation_liability_rows:
            monto_provision = _to_decimal(monto_total)
            if monto_provision <= Decimal("0"):
                continue
            prestaciones.append(
                SimpleNamespace(
                    codigo="vacation_liability",
                    descripcion=(concepto or "Provision de Vacaciones"),
                    monto=monto_provision,
                )
            )

    configuracion_snapshot = nomina.configuracion_snapshot or {}

    dias_mes_nomina = _to_decimal(configuracion_snapshot.get("dias_mes_nomina"))
    horas_jornada_diaria = _to_decimal(configuracion_snapshot.get("horas_jornada_diaria"))

    if dias_mes_nomina <= 0 or horas_jornada_diaria <= 0:
        config_resuelta = ConfigRepository(cast(Any, db.session)).get_for_empresa(planilla.empresa_id)
        if dias_mes_nomina <= 0:
            dias_mes_nomina = _to_decimal(getattr(config_resuelta, "dias_mes_nomina", None))
        if horas_jornada_diaria <= 0:
            horas_jornada_diaria = _to_decimal(getattr(config_resuelta, "horas_jornada_diaria", None))
    sueldo_base_historico = _to_decimal(nomina_empleado.sueldo_base_historico)

    valor_dia_referencia: Decimal | None = None
    if dias_mes_nomina > 0:
        valor_dia_referencia = (sueldo_base_historico / dias_mes_nomina).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    valor_hora_referencia: Decimal | None = None
    if valor_dia_referencia is not None and horas_jornada_diaria > 0:
        valor_hora_referencia = (valor_dia_referencia / horas_jornada_diaria).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    percepcion_ids = sorted({n.percepcion_id for n in novedades_aplicadas if n.percepcion_id})
    deduccion_ids = sorted({n.deduccion_id for n in novedades_aplicadas if n.deduccion_id})

    percepcion_catalogo = {
        percepcion.id: percepcion.descripcion or percepcion.nombre or percepcion.codigo
        for percepcion in db.session.execute(db.select(Percepcion).where(Percepcion.id.in_(percepcion_ids)))
        .scalars()
        .all()
    }
    deduccion_catalogo = {
        deduccion.id: deduccion.descripcion or deduccion.nombre or deduccion.codigo
        for deduccion in db.session.execute(db.select(Deduccion).where(Deduccion.id.in_(deduccion_ids))).scalars().all()
    }

    conteo_tipo_valor: dict[str, int] = {}
    acumulado_tipo_valor: dict[str, Decimal] = {}
    for novedad in novedades_aplicadas:
        tipo_valor = novedad.tipo_valor or "sin_tipo"
        conteo_tipo_valor[tipo_valor] = conteo_tipo_valor.get(tipo_valor, 0) + 1
        acumulado_tipo_valor[tipo_valor] = acumulado_tipo_valor.get(tipo_valor, Decimal("0")) + _to_decimal(
            novedad.valor_cantidad
        )

    def _concepto_key_from_novedad(novedad: NominaNovedad) -> str:
        if novedad.percepcion_id:
            return f"percepcion:{novedad.percepcion_id}"
        if novedad.deduccion_id:
            return f"deduccion:{novedad.deduccion_id}"
        return f"codigo:{novedad.codigo_concepto}"

    def _concepto_key_from_detalle(detalle: NominaDetalle) -> str:
        if detalle.percepcion_id:
            return f"percepcion:{detalle.percepcion_id}"
        if detalle.deduccion_id:
            return f"deduccion:{detalle.deduccion_id}"
        return f"codigo:{detalle.codigo}"

    monto_por_concepto: dict[str, Decimal] = {}
    for detalle in detalles:
        concepto_key = _concepto_key_from_detalle(detalle)
        monto_por_concepto[concepto_key] = monto_por_concepto.get(concepto_key, Decimal("0")) + _to_decimal(
            detalle.monto
        )

    monto_novedad_referencia: dict[str, dict[str, Any]] = {}
    for novedad in novedades_aplicadas:
        novedad_key = _concepto_key_from_novedad(novedad)
        tipo_valor_normalizado = (novedad.tipo_valor or "").lower()
        monto_ajuste_salario_base: Decimal | None = None
        if novedad.descontar_pago_inasistencia:
            cantidad = _to_decimal(novedad.valor_cantidad)
            if tipo_valor_normalizado == "dias" and valor_dia_referencia is not None:
                monto_ajuste_salario_base = (cantidad * valor_dia_referencia).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            elif tipo_valor_normalizado == "horas" and valor_hora_referencia is not None:
                monto_ajuste_salario_base = (cantidad * valor_hora_referencia).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            elif tipo_valor_normalizado == "monto":
                monto_ajuste_salario_base = cantidad.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if tipo_valor_normalizado == "monto":
            monto_novedad_referencia[str(novedad.id)] = {
                "monto": _to_decimal(novedad.valor_cantidad),
                "detalle": "Monto directo reportado en la novedad",
                "es_estimado": False,
            }
        elif novedad_key in monto_por_concepto:
            monto_novedad_referencia[str(novedad.id)] = {
                "monto": monto_por_concepto[novedad_key],
                "detalle": "Monto total calculado para el concepto en la nomina",
                "es_estimado": False,
            }
        elif monto_ajuste_salario_base is not None:
            monto_novedad_referencia[str(novedad.id)] = {
                "monto": monto_ajuste_salario_base,
                "detalle": "Monto estimado por ajuste de salario base segun configuracion de la nomina",
                "es_estimado": True,
            }
        else:
            monto_novedad_referencia[str(novedad.id)] = {
                "monto": None,
                "detalle": "Sin monto monetario directo",
                "es_estimado": False,
            }

    novedades_por_id = {str(n.id): n for n in novedades_aplicadas}
    novedades_descuento_ids = [str(n.id) for n in novedades_aplicadas if n.descontar_pago_inasistencia]
    if novedades_descuento_ids:
        descuento_total = _to_decimal(nomina_empleado.inasistencia_descuento)
        if descuento_total > 0:
            suma_asignada = sum(
                _to_decimal(monto_novedad_referencia[nid]["monto"])
                for nid in novedades_descuento_ids
                if monto_novedad_referencia[nid]["monto"] is not None
            )
            residuo = (descuento_total - suma_asignada).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            if residuo != Decimal("0.00"):
                pendientes_sin_monto = [
                    nid for nid in novedades_descuento_ids if monto_novedad_referencia[nid]["monto"] is None
                ]
                if pendientes_sin_monto:
                    pesos = [
                        max(_to_decimal(novedades_por_id[nid].valor_cantidad), Decimal("0"))
                        for nid in pendientes_sin_monto
                    ]
                    suma_pesos = sum(pesos)

                    if suma_pesos <= 0:
                        pesos = [Decimal("1")] * len(pendientes_sin_monto)
                        suma_pesos = Decimal(str(len(pendientes_sin_monto)))

                    acumulado = Decimal("0")
                    for idx, nid in enumerate(pendientes_sin_monto):
                        if idx < len(pendientes_sin_monto) - 1:
                            asignado = (residuo * pesos[idx] / suma_pesos).quantize(
                                Decimal("0.01"), rounding=ROUND_HALF_UP
                            )
                            acumulado += asignado
                        else:
                            asignado = residuo - acumulado
                        monto_novedad_referencia[nid]["monto"] = asignado
                        monto_novedad_referencia[nid][
                            "detalle"
                        ] = "Monto prorrateado por conciliacion del descuento total aplicado al salario base"
                        monto_novedad_referencia[nid]["es_estimado"] = True
                else:
                    estimadas = [
                        nid for nid in novedades_descuento_ids if monto_novedad_referencia[nid].get("es_estimado")
                    ]
                    if estimadas:
                        objetivo_id = estimadas[-1]
                        monto_actual = _to_decimal(monto_novedad_referencia[objetivo_id]["monto"])
                        monto_nuevo = (monto_actual + residuo).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        monto_novedad_referencia[objetivo_id]["monto"] = monto_nuevo
                        monto_novedad_referencia[objetivo_id]["detalle"] = (
                            "Monto estimado por ajuste de salario base"
                            " segun configuracion de la nomina"
                            " (ajustado por conciliacion de centavos)"
                        )

    resumen_novedades = {
        "total": len(novedades_aplicadas),
        "con_percepcion": sum(1 for n in novedades_aplicadas if n.percepcion_id),
        "con_deduccion": sum(1 for n in novedades_aplicadas if n.deduccion_id),
        "sin_referencia_catalogo": sum(1 for n in novedades_aplicadas if not n.percepcion_id and not n.deduccion_id),
        "conteo_tipo_valor": conteo_tipo_valor,
        "acumulado_tipo_valor": acumulado_tipo_valor,
    }

    configuracion_contexto: dict[str, Any] = {}
    for clave, valor in configuracion_snapshot.items():
        if valor is None or valor == "":
            continue
        if isinstance(valor, (str, int, float, bool, Decimal, date)):
            configuracion_contexto[str(clave)] = valor
    if "dias_mes_nomina" not in configuracion_contexto and dias_mes_nomina > 0:
        configuracion_contexto["dias_mes_nomina"] = dias_mes_nomina
    if "horas_jornada_diaria" not in configuracion_contexto and horas_jornada_diaria > 0:
        configuracion_contexto["horas_jornada_diaria"] = horas_jornada_diaria

    salario_base_historico = _to_decimal(nomina_empleado.sueldo_base_historico)
    salario_base_resultante = _to_decimal(salario_base_visual)
    ajuste_total_salario_base = salario_base_historico - salario_base_resultante

    conciliacion_salario_base = {
        "salario_base_historico": salario_base_historico,
        "ajuste_total_salario_base": ajuste_total_salario_base,
        "salario_base_resultante": salario_base_resultante,
        "configuracion_contexto": configuracion_contexto,
    }

    return render_template(
        "modules/planilla/ver_nomina_empleado.html",
        planilla=planilla,
        nomina=nomina,
        nomina_empleado=nomina_empleado,
        salario_base_visual=salario_base_visual,
        percepciones=percepciones,
        deducciones=deducciones,
        prestaciones=prestaciones,
        novedades_aplicadas=novedades_aplicadas,
        percepcion_catalogo=percepcion_catalogo,
        deduccion_catalogo=deduccion_catalogo,
        resumen_novedades=resumen_novedades,
        monto_novedad_referencia=monto_novedad_referencia,
        conciliacion_salario_base=conciliacion_salario_base,
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

    planilla = db.get_or_404(Planilla, planilla_id)
    nomina_id_value = nomina.id
    planilla_id_value = planilla.id
    novedades: list[NominaNovedad] = []
    try:
        nomina.estado = "applied"
        nomina.modificado_por = current_user.usuario

        # Actualizar estado de todas las novedades asociadas a "ejecutada"
        planilla_empleados = cast(list[Any], planilla.planilla_empleados)
        empleado_ids = [pe.empleado_id for pe in planilla_empleados if pe.activo]

        # Actualizar novedades que corresponden a este período o nómina
        if empleado_ids:
            from sqlalchemy import or_, and_
            condition = or_(
                NominaNovedad.nomina_id == nomina.id,
                and_(
                    NominaNovedad.nomina_id.is_(None),
                    NominaNovedad.fecha_novedad >= nomina.periodo_inicio,
                    NominaNovedad.fecha_novedad <= nomina.periodo_fin,
                )
            )
            novedades = cast(
                list[NominaNovedad],
                db.session.execute(
                    db.select(NominaNovedad).filter(
                        NominaNovedad.empleado_id.in_(empleado_ids),
                        condition,
                        NominaNovedad.estado == NovedadEstado.PENDIENTE,
                    )
                )
                .scalars()
                .all(),
            )

        for novedad in novedades:
            novedad.estado = NovedadEstado.EJECUTADA
            novedad.modificado_por = current_user.usuario

        _aplicar_prestaciones_nomina(nomina, planilla, current_user.usuario)
        _aplicar_vacaciones_nomina(nomina, planilla, current_user.usuario)
        _regenerar_comprobante_contable_nomina(nomina, planilla, current_user.usuario)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.exception(
            "Failed to apply nomina and regenerate voucher",
            extra={"nomina_id": nomina_id_value, "planilla_id": planilla_id_value},
        )
        flash(_("Error al aplicar nómina: {}").format(str(e)), "error")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    flash(
        _("Nómina aplicada exitosamente. {} novedad(es) marcadas como ejecutadas.").format(len(novedades)),
        "success",
    )
    return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/anular", methods=["POST"])
@require_write_access()
def anular_nomina(planilla_id: str, nomina_id: str):
    """Void a nomina when it has not been applied/paid."""
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    if nomina.estado in (NominaEstado.APLICADO, NominaEstado.PAGADO):
        flash(_("No se puede anular una nómina en estado 'applied' o 'paid'."), "error")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    if nomina.estado == NominaEstado.CALCULANDO:
        flash(
            _("No se puede anular una nómina en estado 'calculating'. Espere a que termine el procesamiento."), "error"
        )
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    if nomina.estado == NominaEstado.ANULADO:
        flash(_("La nómina ya está anulada."), "warning")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    razon_anulacion = (request.form.get("razon_anulacion") or "").strip()
    if not razon_anulacion:
        razon_anulacion = _("Nómina anulada por el usuario.")

    try:
        if not registrar_anulacion_nomina(nomina, current_user.usuario, razon_anulacion):
            flash(_("No se pudo anular la nómina."), "error")
            return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

        nomina.modificado_por = current_user.usuario
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.exception(
            "Failed to void nomina",
            extra={"nomina_id": nomina_id, "planilla_id": planilla_id},
        )
        flash(_("Error al anular nómina: {}").format(str(e)), "error")
        return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))

    flash(_("Nómina anulada exitosamente."), "success")
    return redirect(url_for(ROUTE_VER_NOMINA, planilla_id=planilla_id, nomina_id=nomina_id))


def _regenerar_comprobante_contable_nomina(
    nomina: Nomina,
    planilla: Planilla,
    usuario: str | None,
):
    """Regenerate the audit voucher with current persisted side effects."""
    from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService

    accounting_service = AccountingVoucherService(db.session)
    fecha_calculo = nomina.fecha_calculo_original or nomina.periodo_fin
    return accounting_service.generate_audit_voucher(nomina, planilla, fecha_calculo, usuario)


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
        usuario = current_user.nombre_usuario if current_user and current_user.is_authenticated else None
        comprobante = _regenerar_comprobante_contable_nomina(nomina, planilla, usuario)

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
