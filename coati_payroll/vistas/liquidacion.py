# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

"""Liquidaciones module views."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required, current_user

from coati_payroll.enums import LiquidacionEstado
from coati_payroll.i18n import _
from coati_payroll.model import Liquidacion, LiquidacionConcepto, Empleado, db
from coati_payroll.model import PlanillaEmpleado
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.liquidacion_engine import ejecutar_liquidacion, recalcular_liquidacion
from coati_payroll.vistas.planilla.helpers import check_openpyxl_available
from coati_payroll.vistas.planilla.services import ExportService
from coati_payroll.vistas.constants import MSG_EMPLEADO_NO_ENCONTRADO
from coati_payroll.tenant import require_company_access, scope_company_query, scoped_employee_owned_or_404

liquidacion_bp = Blueprint("liquidacion", __name__, url_prefix="/liquidaciones")

# Constants
ROUTE_LIQUIDACION_VER = "liquidacion.ver"


@liquidacion_bp.route("/", methods=["GET"])
@login_required
@require_read_access()
def index():
    """List liquidaciones with pagination and filters."""
    from coati_payroll.vistas.constants import PER_PAGE

    page = request.args.get("page", 1, type=int)

    # Get filter parameters
    buscar = request.args.get("buscar", type=str)
    estado = request.args.get("estado", type=str)
    fecha_desde = request.args.get("fecha_desde", type=str)
    fecha_hasta = request.args.get("fecha_hasta", type=str)

    # Build query with filters
    query = scope_company_query(db.select(Liquidacion).join(Liquidacion.empleado), Empleado.empresa_id)

    if buscar:
        search_term = f"%{buscar}%"
        query = query.filter(
            db.or_(
                Empleado.primer_nombre.ilike(search_term),
                Empleado.segundo_nombre.ilike(search_term),
                Empleado.primer_apellido.ilike(search_term),
                Empleado.segundo_apellido.ilike(search_term),
                Empleado.codigo_empleado.ilike(search_term),
                Empleado.identificacion_personal.ilike(search_term),
            )
        )

    if estado:
        query = query.filter(Liquidacion.estado == estado)

    if fecha_desde:
        query = query.filter(Liquidacion.fecha_calculo >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Liquidacion.fecha_calculo <= fecha_hasta)

    query = query.order_by(Liquidacion.creado.desc())

    pagination = db.paginate(
        query,
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )

    return render_template(
        "modules/liquidacion/index.html",
        liquidaciones=pagination.items,
        pagination=pagination,
        buscar=buscar,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )


@liquidacion_bp.route("/nueva", methods=["GET", "POST"])
@login_required
@require_write_access()
def nueva():
    """Create and calculate a new liquidacion."""
    empleados = (
        db.session.execute(
            scope_company_query(db.select(Empleado), Empleado.empresa_id)
            .filter_by(activo=True)
            .order_by(Empleado.primer_apellido)
        )
        .scalars()
        .all()
    )
    conceptos = (
        db.session.execute(db.select(LiquidacionConcepto).filter_by(activo=True).order_by(LiquidacionConcepto.nombre))
        .scalars()
        .all()
    )

    if request.method == "POST":
        empleado_id = request.form.get("empleado_id")
        concepto_id = request.form.get("concepto_id") or None
        causa_terminacion = request.form.get("causa_terminacion") or None
        fecha_calculo_str = request.form.get("fecha_calculo")

        try:
            fecha_calculo = date.fromisoformat(fecha_calculo_str) if fecha_calculo_str else date.today()
        except ValueError:
            flash(_("Formato de fecha inválido."), "error")
            return redirect(url_for("liquidacion.nueva"))

        empleado = db.session.get(Empleado, empleado_id)
        require_company_access(empleado.empresa_id if empleado else None)
        liquidacion, errors, warnings = ejecutar_liquidacion(
            empleado_id=empleado_id,
            concepto_id=concepto_id,
            fecha_calculo=fecha_calculo,
            usuario=getattr(current_user, "usuario", None),
        )

        for e in errors:
            flash(e, "error")
        for w in warnings:
            flash(w, "warning")

        if liquidacion:
            liquidacion.causa_terminacion = causa_terminacion
            db.session.commit()
            flash(_("Liquidación calculada."), "success")
            return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion.id))

        return redirect(url_for("liquidacion.nueva"))

    return render_template(
        "modules/liquidacion/nueva.html", empleados=empleados, conceptos=conceptos, fecha_calculo=date.today()
    )


@liquidacion_bp.route("/<liquidacion_id>", methods=["GET"])
@login_required
@require_read_access()
def ver(liquidacion_id: str):
    """View liquidacion detail."""
    liquidacion = scoped_employee_owned_or_404(Liquidacion, liquidacion_id, Liquidacion.empleado_id)
    require_company_access(liquidacion.empleado.empresa_id if liquidacion.empleado else None)
    return render_template("modules/liquidacion/ver.html", liquidacion=liquidacion)


@liquidacion_bp.route("/<liquidacion_id>/recalcular", methods=["POST"])
@login_required
@require_write_access()
def recalcular(liquidacion_id: str):
    liquidacion = scoped_employee_owned_or_404(Liquidacion, liquidacion_id, Liquidacion.empleado_id)
    require_company_access(liquidacion.empleado.empresa_id if liquidacion.empleado else None)
    nueva, errors, warnings = recalcular_liquidacion(
        liquidacion_id=liquidacion.id,
        fecha_calculo=liquidacion.fecha_calculo,
        usuario=getattr(current_user, "usuario", None),
    )

    for e in errors:
        flash(e, "error")
    for w in warnings:
        flash(w, "warning")

    if nueva:
        flash(_("Liquidación recalculada."), "success")
    return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion.id))


@liquidacion_bp.route("/<liquidacion_id>/aplicar", methods=["POST"])
@login_required
@require_write_access()
def aplicar(liquidacion_id: str):
    liquidacion = scoped_employee_owned_or_404(Liquidacion, liquidacion_id, Liquidacion.empleado_id)
    require_company_access(liquidacion.empleado.empresa_id if liquidacion.empleado else None)

    if liquidacion.estado not in {LiquidacionEstado.BORRADOR, LiquidacionEstado.CALCULADA}:
        flash(_("Solo se pueden aplicar liquidaciones en borrador o calculadas."), "error")
        return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion.id))

    empleado = db.session.get(Empleado, liquidacion.empleado_id)
    if not empleado:
        flash(_(MSG_EMPLEADO_NO_ENCONTRADO), "error")
        return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion.id))

    # Mark employee inactive
    empleado.activo = False
    empleado.fecha_baja = liquidacion.fecha_calculo

    # Deactivate all active planilla associations
    asociaciones = (
        db.session.execute(
            db.select(PlanillaEmpleado).where(
                PlanillaEmpleado.empleado_id == empleado.id,
                PlanillaEmpleado.activo.is_(True),
            )
        )
        .scalars()
        .all()
    )

    for pe in asociaciones:
        pe.activo = False
        pe.fecha_fin = liquidacion.fecha_calculo

    liquidacion.estado = LiquidacionEstado.APLICADO

    # Materialize deferred loan/advance payments now that the liquidacion
    # leaves the draft state. Calculating in BORRADOR never touches real
    # balances; this recalculation with estado=APLICADO records the
    # AdelantoAbono rows and reduces the outstanding loan balances.
    from coati_payroll.liquidacion_engine import LiquidacionEngine

    engine = LiquidacionEngine(
        empleado=empleado,
        fecha_calculo=liquidacion.fecha_calculo,
        usuario=getattr(current_user, "usuario", None),
    )
    applied = engine.calcular(liquidacion)

    if not applied:
        db.session.rollback()
        flash(_("No se pudo aplicar la liquidación."), "error")
        return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion.id))
    if engine.errors:
        db.session.rollback()
        for error in engine.errors:
            flash(error, "error")
        flash(_("La liquidación no se aplicó porque contiene errores de cálculo."), "error")
        return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion.id))

    from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService

    AccountingVoucherService(db.session).generate_liquidacion_voucher(
        liquidacion, usuario=getattr(current_user, "usuario", None)
    )
    db.session.commit()
    flash(_("Liquidación aplicada. Empleado marcado como inactivo y desvinculado de planillas."), "success")
    return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion.id))


@liquidacion_bp.route("/<liquidacion_id>/pagar", methods=["POST"])
@login_required
@require_write_access()
def pagar(liquidacion_id: str):
    liquidacion = scoped_employee_owned_or_404(Liquidacion, liquidacion_id, Liquidacion.empleado_id)
    require_company_access(liquidacion.empleado.empresa_id if liquidacion.empleado else None)

    if liquidacion.estado != LiquidacionEstado.APLICADO:
        flash(_("Solo se pueden pagar liquidaciones aplicadas."), "error")
        return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion.id))

    liquidacion.medio_pago = request.form.get("medio_pago") or liquidacion.medio_pago
    liquidacion.referencia_pago = request.form.get("referencia_pago") or liquidacion.referencia_pago
    liquidacion.fecha_pago = date.today()
    liquidacion.detalle_pago = {
        "medio": liquidacion.medio_pago,
        "referencia": liquidacion.referencia_pago,
        "registrado_por": getattr(current_user, "usuario", None),
    }
    liquidacion.estado = LiquidacionEstado.PAGADO
    db.session.commit()
    flash(_("Liquidación marcada como pagada."), "success")
    return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion.id))


@liquidacion_bp.route("/<liquidacion_id>/exportar-excel", methods=["GET"])
@login_required
@require_read_access()
def exportar_excel(liquidacion_id: str):
    if not check_openpyxl_available():
        flash(_("Excel export no disponible. Instale openpyxl."), "warning")
        return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion_id))

    liquidacion = scoped_employee_owned_or_404(Liquidacion, liquidacion_id, Liquidacion.empleado_id)
    require_company_access(liquidacion.empleado.empresa_id if liquidacion.empleado else None)

    try:
        output, filename = ExportService.exportar_liquidacion_excel(liquidacion)
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        flash(_("Error al exportar liquidación: {}").format(str(e)), "error")
        return redirect(url_for(ROUTE_LIQUIDACION_VER, liquidacion_id=liquidacion_id))
