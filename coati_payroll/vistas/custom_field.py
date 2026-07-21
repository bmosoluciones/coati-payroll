# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Custom employee field CRUD routes."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from coati_payroll.forms import CustomFieldForm
from coati_payroll.i18n import _
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.model import CampoPersonalizado, db
from coati_payroll.vistas.constants import PER_PAGE

custom_field_bp = Blueprint("custom_field", __name__, url_prefix="/custom_field")
CUSTOM_FIELD_INDEX_ENDPOINT = "custom_field.index"


@custom_field_bp.route("/", methods=["GET"])
@require_read_access()
def index():
    """List all custom fields with pagination."""
    page = request.args.get("page", 1, type=int)
    pagination = db.paginate(
        db.select(CampoPersonalizado).order_by(CampoPersonalizado.orden),
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template(
        "modules/custom_field/index.html",
        custom_fields=pagination.items,
        pagination=pagination,
    )


@custom_field_bp.route("/new", methods=["GET", "POST"])
@require_write_access()
def new():
    """Create a new custom field."""
    form = CustomFieldForm()

    if form.validate_on_submit():
        custom_field = CampoPersonalizado()
        custom_field.nombre_campo = form.nombre_campo.data
        custom_field.etiqueta = form.etiqueta.data
        custom_field.tipo_dato = form.tipo_dato.data
        custom_field.descripcion = form.descripcion.data
        custom_field.orden = int(form.orden.data or 0)
        custom_field.activo = form.activo.data
        custom_field.creado_por = current_user.usuario

        db.session.add(custom_field)
        db.session.commit()
        flash(_("Campo personalizado creado exitosamente."), "success")
        return redirect(url_for(CUSTOM_FIELD_INDEX_ENDPOINT))

    return render_template(
        "modules/custom_field/form.html",
        form=form,
        title=_("Nuevo Campo Personalizado"),
    )


@custom_field_bp.route("/edit/<string:id_>", methods=["GET", "POST"])
@require_write_access()
def edit(id_: str):
    """Edit an existing custom field."""
    custom_field = db.session.get(CampoPersonalizado, id_)
    if not custom_field:
        flash(_("Campo personalizado no encontrado."), "error")
        return redirect(url_for(CUSTOM_FIELD_INDEX_ENDPOINT))

    form = CustomFieldForm(obj=custom_field)

    if form.validate_on_submit():
        custom_field.nombre_campo = form.nombre_campo.data
        custom_field.etiqueta = form.etiqueta.data
        custom_field.tipo_dato = form.tipo_dato.data
        custom_field.descripcion = form.descripcion.data
        custom_field.orden = int(form.orden.data or 0)
        custom_field.activo = form.activo.data
        custom_field.modificado_por = current_user.usuario

        db.session.commit()
        flash(_("Campo personalizado actualizado exitosamente."), "success")
        return redirect(url_for(CUSTOM_FIELD_INDEX_ENDPOINT))

    return render_template(
        "modules/custom_field/form.html",
        form=form,
        title=_("Editar Campo Personalizado"),
        custom_field=custom_field,
    )


@custom_field_bp.route("/delete/<string:id_>", methods=["POST"])
@require_write_access()
def delete(id_: str):
    """Delete a custom field."""
    custom_field = db.session.get(CampoPersonalizado, id_)
    if not custom_field:
        flash(_("Campo personalizado no encontrado."), "error")
        return redirect(url_for(CUSTOM_FIELD_INDEX_ENDPOINT))

    db.session.delete(custom_field)
    db.session.commit()
    flash(_("Campo personalizado eliminado exitosamente."), "success")
    return redirect(url_for(CUSTOM_FIELD_INDEX_ENDPOINT))
