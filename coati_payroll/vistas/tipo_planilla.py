# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Payroll Type (TipoPlanilla) CRUD routes."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from coati_payroll.forms import TipoPlanillaForm
from coati_payroll.i18n import _
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.model import TipoPlanilla, db
from coati_payroll.vistas.constants import PER_PAGE

tipo_planilla_bp = Blueprint("tipo_planilla", __name__, url_prefix="/tipo-planilla")


@tipo_planilla_bp.route("/", methods=["GET"])
@require_read_access()
def index():
    """List all payroll types with pagination."""
    page = request.args.get("page", 1, type=int)
    pagination = db.paginate(
        db.select(TipoPlanilla).order_by(TipoPlanilla.codigo),
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template(
        "modules/tipo_planilla/index.html",
        tipos_planilla=pagination.items,
        pagination=pagination,
    )


@tipo_planilla_bp.route("/new", methods=["GET", "POST"])
@require_write_access()
def new():
    """Create a new payroll type."""
    form = TipoPlanillaForm()

    if form.validate_on_submit():
        tipo_planilla = TipoPlanilla()
        tipo_planilla.codigo = form.codigo.data
        tipo_planilla.descripcion = form.descripcion.data
        tipo_planilla.periodicidad = form.periodicidad.data
        tipo_planilla.dias = form.dias.data
        tipo_planilla.mes_inicio_fiscal = form.mes_inicio_fiscal.data
        tipo_planilla.dia_inicio_fiscal = form.dia_inicio_fiscal.data
        tipo_planilla.acumula_anual = form.acumula_anual.data
        tipo_planilla.periodos_por_anio = form.periodos_por_anio.data
        tipo_planilla.activo = form.activo.data
        tipo_planilla.creado_por = current_user.usuario

        db.session.add(tipo_planilla)
        db.session.commit()
        flash(_("Tipo de planilla creado exitosamente."), "success")
        return redirect(url_for("tipo_planilla.index"))

    return render_template(
        "modules/tipo_planilla/form.html",
        form=form,
        title=_("Nuevo Tipo de Planilla"),
    )


@tipo_planilla_bp.route("/edit/<string:id_>", methods=["GET", "POST"])
@require_write_access()
def edit(id_: str):
    """Edit an existing payroll type."""
    tipo_planilla = db.session.get(TipoPlanilla, id_)
    if not tipo_planilla:
        flash(_("Tipo de planilla no encontrado."), "error")
        return redirect(url_for("tipo_planilla.index"))

    form = TipoPlanillaForm(obj=tipo_planilla)

    if form.validate_on_submit():
        tipo_planilla.codigo = form.codigo.data
        tipo_planilla.descripcion = form.descripcion.data
        tipo_planilla.periodicidad = form.periodicidad.data
        tipo_planilla.dias = form.dias.data
        tipo_planilla.mes_inicio_fiscal = form.mes_inicio_fiscal.data
        tipo_planilla.dia_inicio_fiscal = form.dia_inicio_fiscal.data
        tipo_planilla.acumula_anual = form.acumula_anual.data
        tipo_planilla.periodos_por_anio = form.periodos_por_anio.data
        tipo_planilla.activo = form.activo.data
        tipo_planilla.modificado_por = current_user.usuario

        db.session.commit()
        flash(_("Tipo de planilla actualizado exitosamente."), "success")
        return redirect(url_for("tipo_planilla.index"))

    return render_template(
        "modules/tipo_planilla/form.html",
        form=form,
        title=_("Editar Tipo de Planilla"),
        tipo_planilla=tipo_planilla,
    )


@tipo_planilla_bp.route("/delete/<string:id_>", methods=["POST"])
@require_write_access()
def delete(id_: str):
    """Delete a payroll type."""
    tipo_planilla = db.session.get(TipoPlanilla, id_)
    if not tipo_planilla:
        flash(_("Tipo de planilla no encontrado."), "error")
        return redirect(url_for("tipo_planilla.index"))

    # Check if this type is used by any planilla
    if tipo_planilla.planillas:
        flash(
            _("No se puede eliminar un tipo de planilla que está siendo usado."),
            "error",
        )
        return redirect(url_for("tipo_planilla.index"))

    db.session.delete(tipo_planilla)
    db.session.commit()
    flash(_("Tipo de planilla eliminado exitosamente."), "success")
    return redirect(url_for("tipo_planilla.index"))
