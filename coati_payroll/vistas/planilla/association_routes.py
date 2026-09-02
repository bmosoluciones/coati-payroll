# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Routes for managing planilla associations."""

from datetime import date
from flask import abort, flash, redirect, request, url_for
from flask_login import current_user

from coati_payroll.model import (
    db,
    Planilla,
    Empleado,
    PlanillaEmpleado,
    PlanillaIngreso,
    PlanillaDeduccion,
    PlanillaPrestacion,
    PlanillaReglaCalculo,
)
from coati_payroll.i18n import _
from coati_payroll.rbac import require_write_access
from coati_payroll.vistas.planilla import planilla_bp
from coati_payroll.vistas.planilla.helpers.association_helpers import agregar_asociacion
from coati_payroll.vistas.planilla.validators.planilla_validators import PlanillaValidator
from coati_payroll.tenant import require_company_access, scoped_or_404

# Constants
ROUTE_CONFIG_EMPLEADOS = "planilla.config_empleados"
ROUTE_CONFIG_PERCEPCIONES = "planilla.config_percepciones"
ROUTE_CONFIG_DEDUCCIONES = "planilla.config_deducciones"
ROUTE_CONFIG_PRESTACIONES = "planilla.config_prestaciones"
ROUTE_CONFIG_REGLAS = "planilla.config_reglas"
ERROR_NOT_FOUND = "no encontrada"
LITERAL_CONFIG_EMPLEADOS = "planilla.config_empleados"
LITERAL_CONFIG_DEDUCCIONES = "planilla.config_deducciones"


def _scoped_association(planilla_id: str, model, association_id: str):
    """Load an association only through its already-scoped planilla."""
    planilla = scoped_or_404(Planilla, planilla_id, Planilla.empresa_id)
    association = db.get_or_404(model, association_id)
    if association.planilla_id != planilla.id:
        abort(404)
    return association


@planilla_bp.route("/<planilla_id>/empleado/add", methods=["POST"])
@require_write_access()
def add_empleado(planilla_id: str):
    """Add an employee to the planilla."""
    planilla = scoped_or_404(Planilla, planilla_id, Planilla.empresa_id)
    empleado_id = request.form.get("empleado_id")

    if not empleado_id:
        flash(_("Debe seleccionar un empleado."), "error")
        return redirect(url_for(ROUTE_CONFIG_EMPLEADOS, planilla_id=planilla_id))

    # Check if already exists
    existing = db.session.execute(
        db.select(PlanillaEmpleado).filter_by(planilla_id=planilla_id, empleado_id=empleado_id)
    ).scalar_one_or_none()

    if existing:
        flash(_("El empleado ya está asignado a esta planilla."), "warning")
        return redirect(url_for(ROUTE_CONFIG_EMPLEADOS, planilla_id=planilla_id))

    # Validate that employee and planilla belong to the same company
    empleado = db.get_or_404(Empleado, empleado_id)
    if empleado.empresa_id:
        require_company_access(empleado.empresa_id)
    is_valid, error_message = PlanillaValidator.validar_empresa_empleado(planilla, empleado)
    if not is_valid:
        flash(_(error_message or "Empleado no válido para esta planilla."), "error")
        return redirect(url_for(ROUTE_CONFIG_EMPLEADOS, planilla_id=planilla_id))

    association = PlanillaEmpleado(
        planilla_id=planilla_id,
        empleado_id=empleado_id,
        fecha_inicio=date.today(),
        activo=True,
        creado_por=current_user.usuario,
    )
    db.session.add(association)
    db.session.commit()
    flash(_("Empleado agregado exitosamente."), "success")
    return redirect(url_for(LITERAL_CONFIG_EMPLEADOS, planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/empleado/<association_id>/remove", methods=["POST"])
@require_write_access()
def remove_empleado(planilla_id: str, association_id: str):
    """Remove an employee from the planilla."""
    association = _scoped_association(planilla_id, PlanillaEmpleado, association_id)
    db.session.delete(association)
    db.session.commit()
    flash(_("Empleado removido exitosamente."), "success")
    return redirect(url_for(LITERAL_CONFIG_EMPLEADOS, planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/percepcion/add", methods=["POST"])
@require_write_access()
def add_percepcion(planilla_id: str):
    """Add a perception to the planilla."""
    orden = request.form.get("orden", 0, type=int)
    percepcion_id = request.form.get("percepcion_id") or ""
    success, error_message, _association_id = agregar_asociacion(
        planilla_id=planilla_id,
        tipo_componente="percepcion",
        componente_id=percepcion_id,
        datos_extra={"orden": orden},
        usuario=current_user.usuario,
    )

    if not success:
        error_text = error_message or "No se pudo agregar la percepción."
        flash(_(error_text), "error" if ERROR_NOT_FOUND in error_text else "warning")
        return redirect(url_for(ROUTE_CONFIG_PERCEPCIONES, planilla_id=planilla_id))

    flash(_("Percepción agregada exitosamente."), "success")
    return redirect(url_for(ROUTE_CONFIG_PERCEPCIONES, planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/percepcion/<association_id>/remove", methods=["POST"])
@require_write_access()
def remove_percepcion(planilla_id: str, association_id: str):
    """Remove a perception from the planilla."""
    association = _scoped_association(planilla_id, PlanillaIngreso, association_id)
    db.session.delete(association)
    db.session.commit()
    flash(_("Percepción removida exitosamente."), "success")
    return redirect(url_for("planilla.config_percepciones", planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/deduccion/add", methods=["POST"])
@require_write_access()
def add_deduccion(planilla_id: str):
    """Add a deduction to the planilla with priority."""
    prioridad = request.form.get("prioridad", 100, type=int)
    es_obligatoria = request.form.get("es_obligatoria") == "on"
    deduccion_id = request.form.get("deduccion_id") or ""
    success, error_message, _association_id = agregar_asociacion(
        planilla_id=planilla_id,
        tipo_componente="deduccion",
        componente_id=deduccion_id,
        datos_extra={"prioridad": prioridad, "es_obligatoria": es_obligatoria},
        usuario=current_user.usuario,
    )

    if not success:
        error_text = error_message or "No se pudo agregar la deducción."
        flash(_(error_text), "error" if ERROR_NOT_FOUND in error_text else "warning")
        return redirect(url_for(ROUTE_CONFIG_DEDUCCIONES, planilla_id=planilla_id))

    flash(_("Deducción agregada exitosamente."), "success")
    return redirect(url_for(ROUTE_CONFIG_DEDUCCIONES, planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/deduccion/<association_id>/remove", methods=["POST"])
@require_write_access()
def remove_deduccion(planilla_id: str, association_id: str):
    """Remove a deduction from the planilla."""
    association = _scoped_association(planilla_id, PlanillaDeduccion, association_id)
    db.session.delete(association)
    db.session.commit()
    flash(_("Deducción removida exitosamente."), "success")
    return redirect(url_for(LITERAL_CONFIG_DEDUCCIONES, planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/deduccion/<association_id>/update-priority", methods=["POST"])
@require_write_access()
def update_deduccion_priority(planilla_id: str, association_id: str):
    """Update the priority of a deduction."""
    association = _scoped_association(planilla_id, PlanillaDeduccion, association_id)

    prioridad = request.form.get("prioridad", type=int)
    if prioridad is not None:
        association.prioridad = prioridad
        association.modificado_por = current_user.usuario
        db.session.commit()
        flash(_("Prioridad actualizada."), "success")

    return redirect(url_for(LITERAL_CONFIG_DEDUCCIONES, planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/prestacion/add", methods=["POST"])
@require_write_access()
def add_prestacion(planilla_id: str):
    """Add a benefit (prestacion) to the planilla."""
    orden = request.form.get("orden", 0, type=int)
    prestacion_id = request.form.get("prestacion_id") or ""
    success, error_message, _association_id = agregar_asociacion(
        planilla_id=planilla_id,
        tipo_componente="prestacion",
        componente_id=prestacion_id,
        datos_extra={"orden": orden},
        usuario=current_user.usuario,
    )

    if not success:
        error_text = error_message or "No se pudo agregar la prestación."
        flash(_(error_text), "error" if ERROR_NOT_FOUND in error_text else "warning")
        return redirect(url_for(ROUTE_CONFIG_PRESTACIONES, planilla_id=planilla_id))

    flash(_("Prestación agregada exitosamente."), "success")
    return redirect(url_for(ROUTE_CONFIG_PRESTACIONES, planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/prestacion/<association_id>/remove", methods=["POST"])
@require_write_access()
def remove_prestacion(planilla_id: str, association_id: str):
    """Remove a benefit from the planilla."""
    association = _scoped_association(planilla_id, PlanillaPrestacion, association_id)
    db.session.delete(association)
    db.session.commit()
    flash(_("Prestación removida exitosamente."), "success")
    return redirect(url_for("planilla.config_prestaciones", planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/regla/add", methods=["POST"])
@require_write_access()
def add_regla(planilla_id: str):
    """Add a calculation rule to the planilla."""
    orden = request.form.get("orden", 0, type=int)
    regla_calculo_id = request.form.get("regla_calculo_id") or ""
    success, error_message, _association_id = agregar_asociacion(
        planilla_id=planilla_id,
        tipo_componente="regla",
        componente_id=regla_calculo_id,
        datos_extra={"orden": orden},
        usuario=current_user.usuario,
    )

    if not success:
        error_text = error_message or "No se pudo agregar la regla de cálculo."
        flash(_(error_text), "error" if ERROR_NOT_FOUND in error_text else "warning")
        return redirect(url_for(ROUTE_CONFIG_REGLAS, planilla_id=planilla_id))

    flash(_("Regla de cálculo agregada exitosamente."), "success")
    return redirect(url_for(ROUTE_CONFIG_REGLAS, planilla_id=planilla_id))


@planilla_bp.route("/<planilla_id>/regla/<association_id>/remove", methods=["POST"])
@require_write_access()
def remove_regla(planilla_id: str, association_id: str):
    """Remove a calculation rule from the planilla."""
    association = _scoped_association(planilla_id, PlanillaReglaCalculo, association_id)
    db.session.delete(association)
    db.session.commit()
    flash(_("Regla de cálculo removida exitosamente."), "success")
    return redirect(url_for("planilla.config_reglas", planilla_id=planilla_id))
