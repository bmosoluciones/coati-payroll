# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Configuration routes for planilla associations."""

from flask import render_template

from coati_payroll.model import (
    db,
    Planilla,
    Empleado,
    PlanillaEmpleado,
    PlanillaIngreso,
    PlanillaDeduccion,
    PlanillaPrestacion,
    PlanillaReglaCalculo,
    Percepcion,
    Deduccion,
    Prestacion,
    ReglaCalculo,
    empresa_percepcion,
    empresa_deduccion,
    empresa_prestacion,
)
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.vistas.planilla import planilla_bp
from coati_payroll.tenant import concept_scope_for_company, scoped_or_404


@planilla_bp.route("/<planilla_id>/config/empleados", methods=["GET"])
@require_read_access()
def config_empleados(planilla_id: str):
    """View employees associated with a planilla."""
    planilla = scoped_or_404(Planilla, planilla_id, Planilla.empresa_id)

    empleados_asignados = (
        db.session.execute(db.select(PlanillaEmpleado).filter_by(planilla_id=planilla_id)).scalars().all()
    )

    # Filter employees to only show those from the same company as the planilla
    # CRITICAL: Only employees with matching empresa_id can be added to this planilla
    query = db.select(Empleado).filter_by(activo=True)
    if planilla.empresa_id:
        # Only show employees from the same company (exact match required)
        query = query.filter(Empleado.empresa_id == planilla.empresa_id)
    else:
        # If planilla has no company, show no employees (planilla must have empresa)
        query = query.filter(db.false())
    empleados_disponibles = db.session.execute(query.order_by(Empleado.primer_apellido)).scalars().all()

    return render_template(
        "modules/planilla/config_empleados.html",
        planilla=planilla,
        empleados_asignados=empleados_asignados,
        empleados_disponibles=empleados_disponibles,
    )


@planilla_bp.route("/<planilla_id>/config/percepciones", methods=["GET"])
@require_read_access()
def config_percepciones(planilla_id: str):
    """View perceptions associated with a planilla."""
    planilla = scoped_or_404(Planilla, planilla_id, Planilla.empresa_id)

    percepciones_asignadas = (
        db.session.execute(db.select(PlanillaIngreso).filter_by(planilla_id=planilla_id)).scalars().all()
    )

    percepciones_disponibles = (
        db.session.execute(
            concept_scope_for_company(db.select(Percepcion), empresa_percepcion, Percepcion.id, planilla.empresa_id)
            .filter(Percepcion.activo.is_(True)).order_by(Percepcion.nombre)
        ).scalars().all()
    )

    return render_template(
        "modules/planilla/config_percepciones.html",
        planilla=planilla,
        percepciones_asignadas=percepciones_asignadas,
        percepciones_disponibles=percepciones_disponibles,
    )


@planilla_bp.route("/<planilla_id>/config/deducciones", methods=["GET"])
@require_read_access()
def config_deducciones(planilla_id: str):
    """View deductions associated with a planilla."""
    planilla = scoped_or_404(Planilla, planilla_id, Planilla.empresa_id)

    deducciones_asignadas = (
        db.session.execute(
            db.select(PlanillaDeduccion).filter_by(planilla_id=planilla_id).order_by(PlanillaDeduccion.prioridad)
        )
        .scalars()
        .all()
    )

    deducciones_disponibles = (
        db.session.execute(
            concept_scope_for_company(db.select(Deduccion), empresa_deduccion, Deduccion.id, planilla.empresa_id)
            .filter(Deduccion.activo.is_(True)).order_by(Deduccion.nombre)
        ).scalars().all()
    )

    return render_template(
        "modules/planilla/config_deducciones.html",
        planilla=planilla,
        deducciones_asignadas=deducciones_asignadas,
        deducciones_disponibles=deducciones_disponibles,
    )


@planilla_bp.route("/<planilla_id>/config/prestaciones", methods=["GET"])
@require_write_access()
def config_prestaciones(planilla_id: str):
    """Manage benefits associated with a planilla."""
    planilla = scoped_or_404(Planilla, planilla_id, Planilla.empresa_id)

    prestaciones_asignadas = (
        db.session.execute(db.select(PlanillaPrestacion).filter_by(planilla_id=planilla_id)).scalars().all()
    )

    prestaciones_disponibles = (
        db.session.execute(
            concept_scope_for_company(db.select(Prestacion), empresa_prestacion, Prestacion.id, planilla.empresa_id)
            .filter(Prestacion.activo.is_(True)).order_by(Prestacion.nombre)
        ).scalars().all()
    )

    return render_template(
        "modules/planilla/config_prestaciones.html",
        planilla=planilla,
        prestaciones_asignadas=prestaciones_asignadas,
        prestaciones_disponibles=prestaciones_disponibles,
    )


@planilla_bp.route("/<planilla_id>/config/reglas", methods=["GET"])
@require_read_access()
def config_reglas(planilla_id: str):
    """View calculation rules associated with a planilla."""
    planilla = scoped_or_404(Planilla, planilla_id, Planilla.empresa_id)

    reglas_asignadas = (
        db.session.execute(
            db.select(PlanillaReglaCalculo).filter_by(planilla_id=planilla_id).order_by(PlanillaReglaCalculo.orden)
        )
        .scalars()
        .all()
    )

    reglas_disponibles = (
        db.session.execute(db.select(ReglaCalculo).filter_by(activo=True).order_by(ReglaCalculo.nombre)).scalars().all()
    )

    return render_template(
        "modules/planilla/config_reglas.html",
        planilla=planilla,
        reglas_asignadas=reglas_asignadas,
        reglas_disponibles=reglas_disponibles,
    )
