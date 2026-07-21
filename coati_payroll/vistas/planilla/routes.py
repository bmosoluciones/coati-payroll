# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Main routes for planilla management."""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import false, true

from coati_payroll.model import db, Planilla, VacationPolicy
from coati_payroll.forms import PlanillaForm
from coati_payroll.i18n import _
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.vistas.planilla.helpers import (
    populate_form_choices,
    get_planilla_component_counts,
    get_nomina_counts_by_planilla,
)
from coati_payroll.vistas.planilla.services import PlanillaService
from coati_payroll.vistas.constants import TEMPLATE_PLANILLA_FORM

# Import blueprint from __init__.py
from coati_payroll.vistas.planilla import planilla_bp


@planilla_bp.route("/", methods=["GET"])
@require_read_access()
def index():
    """List all planillas with pagination and filters."""
    from coati_payroll.model import TipoPlanilla, Empresa
    from coati_payroll.vistas.constants import PER_PAGE

    page = request.args.get("page", 1, type=int)

    # Get filter parameters
    buscar = request.args.get("buscar", type=str)
    estado = request.args.get("estado", type=str)
    tipo_planilla_id = request.args.get("tipo_planilla_id", type=str) if request.args.get("tipo_planilla_id") else None
    empresa_id = request.args.get("empresa_id", type=str) if request.args.get("empresa_id") else None

    # Build query with filters
    query = db.select(Planilla)

    if buscar:
        search_term = f"%{buscar}%"
        query = query.filter(
            db.or_(
                Planilla.nombre.ilike(search_term),
                Planilla.descripcion.ilike(search_term),
            )
        )

    if estado == "activo":
        query = query.filter(Planilla.activo.is_(true()))
    elif estado == "inactivo":
        query = query.filter(Planilla.activo.is_(false()))

    if tipo_planilla_id:
        query = query.filter(Planilla.tipo_planilla_id == tipo_planilla_id)

    if empresa_id:
        query = query.filter(Planilla.empresa_id == empresa_id)

    query = query.order_by(Planilla.nombre)

    pagination = db.paginate(
        query,
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )

    # Get choices for filter dropdowns
    tipos_planilla = (
        db.session.execute(db.select(TipoPlanilla).filter_by(activo=True).order_by(TipoPlanilla.codigo)).scalars().all()
    )
    empresas = (
        db.session.execute(db.select(Empresa).filter_by(activo=True).order_by(Empresa.razon_social)).scalars().all()
    )
    nomina_counts = get_nomina_counts_by_planilla([planilla.id for planilla in pagination.items])

    return render_template(
        "modules/planilla/index.html",
        planillas=pagination.items,
        pagination=pagination,
        buscar=buscar,
        estado=estado,
        tipo_planilla_id=tipo_planilla_id,
        empresa_id=empresa_id,
        tipos_planilla=tipos_planilla,
        empresas=empresas,
        nomina_counts=nomina_counts,
    )


@planilla_bp.route("/new", methods=["GET", "POST"])
@require_write_access()
def new():
    """Create a new planilla. Admin and HR can create planillas."""
    form = PlanillaForm()
    populate_form_choices(form)

    if form.validate_on_submit():
        vacation_policy_id = form.vacation_policy_id.data or None
        if vacation_policy_id:
            policy = db.session.get(VacationPolicy, vacation_policy_id)
            if not policy:
                flash(_("La regla de vacaciones seleccionada no existe."), "danger")
                return render_template(TEMPLATE_PLANILLA_FORM, form=form, is_edit=False)
            if policy.empresa_id and policy.empresa_id != (form.empresa_id.data or None):
                flash(_("La regla de vacaciones pertenece a otra empresa."), "danger")
                return render_template(TEMPLATE_PLANILLA_FORM, form=form, is_edit=False)

        planilla = Planilla(
            nombre=form.nombre.data,
            descripcion=form.descripcion.data,
            tipo_planilla_id=form.tipo_planilla_id.data,
            moneda_id=form.moneda_id.data,
            empresa_id=form.empresa_id.data or None,
            mes_inicio_fiscal=form.mes_inicio_fiscal.data or 1,
            vacation_policy_id=vacation_policy_id,
            periodo_fiscal_inicio=form.periodo_fiscal_inicio.data,
            periodo_fiscal_fin=form.periodo_fiscal_fin.data,
            prioridad_prestamos=form.prioridad_prestamos.data or 250,
            prioridad_adelantos=form.prioridad_adelantos.data or 251,
            aplicar_prestamos_automatico=form.aplicar_prestamos_automatico.data,
            aplicar_adelantos_automatico=form.aplicar_adelantos_automatico.data,
            codigo_cuenta_debe_salario=form.codigo_cuenta_debe_salario.data,
            descripcion_cuenta_debe_salario=form.descripcion_cuenta_debe_salario.data,
            codigo_cuenta_haber_salario=form.codigo_cuenta_haber_salario.data,
            descripcion_cuenta_haber_salario=form.descripcion_cuenta_haber_salario.data,
            activo=form.activo.data,
            creado_por=current_user.usuario,
        )
        db.session.add(planilla)
        db.session.commit()
        flash(_("Planilla creada exitosamente."), "success")
        return redirect(url_for("planilla.edit", planilla_id=planilla.id))

    return render_template(TEMPLATE_PLANILLA_FORM, form=form, is_edit=False)


@planilla_bp.route("/<planilla_id>/edit", methods=["GET", "POST"])
@require_write_access()
def edit(planilla_id: str):
    """Edit basic planilla configuration."""
    planilla = db.get_or_404(Planilla, planilla_id)
    form = PlanillaForm(obj=planilla)
    populate_form_choices(form)

    if form.validate_on_submit():
        vacation_policy_id = form.vacation_policy_id.data or None
        if vacation_policy_id:
            policy = db.session.get(VacationPolicy, vacation_policy_id)
            if not policy:
                flash(_("La regla de vacaciones seleccionada no existe."), "danger")
                counts = get_planilla_component_counts(planilla_id)
                return render_template(
                    TEMPLATE_PLANILLA_FORM, form=form, planilla=planilla, is_edit=True, **counts
                )
            if policy.empresa_id and policy.empresa_id != (form.empresa_id.data or None):
                flash(_("La regla de vacaciones pertenece a otra empresa."), "danger")
                counts = get_planilla_component_counts(planilla_id)
                return render_template(
                    TEMPLATE_PLANILLA_FORM, form=form, planilla=planilla, is_edit=True, **counts
                )

        planilla.nombre = form.nombre.data
        planilla.descripcion = form.descripcion.data
        planilla.tipo_planilla_id = form.tipo_planilla_id.data
        planilla.moneda_id = form.moneda_id.data
        planilla.empresa_id = form.empresa_id.data or None
        planilla.mes_inicio_fiscal = form.mes_inicio_fiscal.data or 1
        planilla.vacation_policy_id = vacation_policy_id
        planilla.periodo_fiscal_inicio = form.periodo_fiscal_inicio.data
        planilla.periodo_fiscal_fin = form.periodo_fiscal_fin.data
        planilla.prioridad_prestamos = form.prioridad_prestamos.data or 250
        planilla.prioridad_adelantos = form.prioridad_adelantos.data or 251
        planilla.aplicar_prestamos_automatico = form.aplicar_prestamos_automatico.data
        planilla.aplicar_adelantos_automatico = form.aplicar_adelantos_automatico.data
        planilla.codigo_cuenta_debe_salario = form.codigo_cuenta_debe_salario.data
        planilla.descripcion_cuenta_debe_salario = form.descripcion_cuenta_debe_salario.data
        planilla.codigo_cuenta_haber_salario = form.codigo_cuenta_haber_salario.data
        planilla.descripcion_cuenta_haber_salario = form.descripcion_cuenta_haber_salario.data
        planilla.activo = form.activo.data
        planilla.modificado_por = current_user.usuario
        db.session.commit()
        flash(_("Planilla actualizada exitosamente."), "success")
        return redirect(url_for("planilla.config", planilla_id=planilla.id))

    # Get association counts for the summary
    counts = get_planilla_component_counts(planilla_id)

    return render_template(
        TEMPLATE_PLANILLA_FORM,
        form=form,
        planilla=planilla,
        is_edit=True,
        **counts,
    )


@planilla_bp.route("/<planilla_id>/config", methods=["GET"])
@require_read_access()
def config(planilla_id: str):
    """Configuration overview page for a planilla."""
    planilla = db.get_or_404(Planilla, planilla_id)

    # Get association counts for the summary
    counts = get_planilla_component_counts(planilla_id)

    return render_template(
        "modules/planilla/config.html",
        planilla=planilla,
        **counts,
    )


@planilla_bp.route("/<planilla_id>/clone", methods=["POST"])
@require_write_access()
def clone(planilla_id: str):
    """Clone a planilla and redirect to edit the new copy."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nueva_planilla = PlanillaService.clone_planilla(planilla, creado_por=current_user.usuario)
    flash(_("Planilla clonada exitosamente: %(nombre)s", nombre=nueva_planilla.nombre), "success")
    return redirect(url_for("planilla.edit", planilla_id=nueva_planilla.id))


@planilla_bp.route("/<planilla_id>/delete", methods=["POST"])
@require_write_access()
def delete(planilla_id: str):
    """Delete a planilla."""
    planilla = db.get_or_404(Planilla, planilla_id)

    can_delete, error_message = PlanillaService.can_delete(planilla)
    if not can_delete:
        flash(_(error_message or "No se puede eliminar la planilla."), "error")
        return redirect(url_for("planilla.index"))

    db.session.delete(planilla)
    db.session.commit()
    flash(_("Planilla eliminada exitosamente."), "success")
    return redirect(url_for("planilla.index"))
