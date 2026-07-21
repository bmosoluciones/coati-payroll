# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Empresa (Company) views module."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import false, true

from coati_payroll.enums import NominaEstado, TipoUsuario
from coati_payroll.i18n import _
from coati_payroll.model import Empleado, Empresa, Nomina, Planilla, db
from coati_payroll.rbac import require_role, require_read_access

empresa_bp = Blueprint("empresa", __name__, url_prefix="/empresa")
EMPRESA_INDEX_ENDPOINT = "empresa.index"


def _bootstrap_fields_locked(empresa_id: str) -> bool:
    """Return True when bootstrap fields must be locked for the company."""
    nomina_id = db.session.execute(
        db.select(Nomina.id)
        .join(Planilla, Nomina.planilla_id == Planilla.id)
        .filter(
            Planilla.empresa_id == empresa_id,
            Nomina.estado.in_([NominaEstado.APLICADO.value, NominaEstado.PAGADO.value]),
        )
        .limit(1)
    ).scalar_one_or_none()
    return nomina_id is not None


@empresa_bp.route("/", methods=["GET"])
@require_read_access()
def index():
    """List all companies with pagination and filters."""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    # Get filter parameters
    buscar = request.args.get("buscar", type=str)
    estado = request.args.get("estado", type=str)

    # Build query with filters
    query = db.select(Empresa)

    if buscar:
        search_term = f"%{buscar}%"
        query = query.filter(
            db.or_(
                Empresa.razon_social.ilike(search_term),
                Empresa.nombre_comercial.ilike(search_term),
                Empresa.codigo.ilike(search_term),
                Empresa.ruc.ilike(search_term),
            )
        )

    if estado == "activo":
        query = query.filter(Empresa.activo.is_(true()))
    elif estado == "inactivo":
        query = query.filter(Empresa.activo.is_(false()))

    query = query.order_by(Empresa.razon_social)

    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    empresas = pagination.items

    return render_template(
        "modules/empresa/index.html",
        empresas=empresas,
        pagination=pagination,
        buscar=buscar,
        estado=estado,
    )


@empresa_bp.route("/new", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def new():
    """Create a new company. Only administrators can create companies."""
    from coati_payroll.forms import EmpresaForm

    form = EmpresaForm()
    if request.method == "GET":
        if form.primer_mes_nomina.data is None:
            form.primer_mes_nomina.data = date.today().month
        if form.primer_anio_nomina.data is None:
            form.primer_anio_nomina.data = date.today().year

    if form.validate_on_submit():
        empresa = Empresa()
        form.populate_obj(empresa)
        if empresa.primer_mes_nomina is None:
            empresa.primer_mes_nomina = date.today().month
        if empresa.primer_anio_nomina is None:
            empresa.primer_anio_nomina = date.today().year
        empresa.creado_por = current_user.usuario

        db.session.add(empresa)
        try:
            db.session.commit()
            flash(_("Empresa creada exitosamente."), "success")
            return redirect(url_for(EMPRESA_INDEX_ENDPOINT))
        except Exception as e:
            db.session.rollback()
            flash(_("Error al crear la empresa: {}").format(str(e)), "danger")

    return render_template(
        "modules/empresa/form.html", form=form, titulo=_("Nueva Empresa"), lock_bootstrap_fields=False
    )


@empresa_bp.route("/<string:empresa_id>/edit", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def edit(empresa_id):
    """Edit an existing company. Only administrators can edit companies."""
    from coati_payroll.forms import EmpresaForm

    empresa = db.session.get(Empresa, empresa_id)
    if not empresa:
        flash(_("Empresa no encontrada."), "warning")
        return redirect(url_for(EMPRESA_INDEX_ENDPOINT))

    lock_bootstrap_fields = _bootstrap_fields_locked(empresa.id)
    form = EmpresaForm(obj=empresa)

    if form.validate_on_submit():
        original_primer_mes = empresa.primer_mes_nomina
        original_primer_anio = empresa.primer_anio_nomina
        form.populate_obj(empresa)

        if lock_bootstrap_fields:
            attempted_change = (
                empresa.primer_mes_nomina != original_primer_mes or empresa.primer_anio_nomina != original_primer_anio
            )
            empresa.primer_mes_nomina = original_primer_mes
            empresa.primer_anio_nomina = original_primer_anio
            if attempted_change:
                flash(
                    _(
                        "No se puede modificar el período inicial de nómina "
                        "porque ya existen nóminas aplicadas o pagadas."
                    ),
                    "warning",
                )

        empresa.modificado_por = current_user.usuario

        try:
            db.session.commit()
            flash(_("Empresa actualizada exitosamente."), "success")
            return redirect(url_for(EMPRESA_INDEX_ENDPOINT))
        except Exception as e:
            db.session.rollback()
            flash(_("Error al actualizar la empresa: {}").format(str(e)), "danger")

    return render_template(
        "modules/empresa/form.html",
        form=form,
        empresa=empresa,
        titulo=_("Editar Empresa"),
        lock_bootstrap_fields=lock_bootstrap_fields,
    )


@empresa_bp.route("/<string:empresa_id>/delete", methods=["POST"])
@require_role(TipoUsuario.ADMIN)
def delete(empresa_id):
    """Delete a company. Only administrators can delete companies."""
    empresa = db.session.get(Empresa, empresa_id)
    if not empresa:
        flash(_("Empresa no encontrada."), "warning")
        return redirect(url_for(EMPRESA_INDEX_ENDPOINT))

    # Prevent deletion when the company still has active links.
    has_active_employees = db.session.execute(
        db.select(Empleado.id).filter(Empleado.empresa_id == empresa.id, Empleado.activo.is_(true())).limit(1)
    ).scalar_one_or_none()

    has_nominas = db.session.execute(
        db.select(Nomina.id)
        .join(Planilla, Nomina.planilla_id == Planilla.id)
        .filter(Planilla.empresa_id == empresa.id)
        .limit(1)
    ).scalar_one_or_none()

    if has_active_employees or has_nominas:
        flash(
            _("No se puede eliminar la empresa porque tiene empleados activos o nóminas asociadas."),
            "danger",
        )
        return redirect(url_for(EMPRESA_INDEX_ENDPOINT))

    try:
        db.session.delete(empresa)
        db.session.commit()
        flash(_("Empresa eliminada exitosamente."), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error al eliminar la empresa: {}").format(str(e)), "danger")

    return redirect(url_for(EMPRESA_INDEX_ENDPOINT))


@empresa_bp.route("/<string:empresa_id>/toggle", methods=["POST"])
@require_role(TipoUsuario.ADMIN)
def toggle_active(empresa_id):
    """Toggle company active status. Only administrators can toggle status."""
    empresa = db.session.get(Empresa, empresa_id)
    if not empresa:
        flash(_("Empresa no encontrada."), "warning")
        return redirect(url_for(EMPRESA_INDEX_ENDPOINT))

    empresa.activo = not empresa.activo
    empresa.modificado_por = current_user.usuario

    try:
        db.session.commit()
        estado = _("activada") if empresa.activo else _("desactivada")
        flash(_("Empresa {} exitosamente.").format(estado), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error al cambiar el estado de la empresa: {}").format(str(e)), "danger")

    return redirect(url_for(EMPRESA_INDEX_ENDPOINT))
