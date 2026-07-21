# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Form helper functions for planilla views."""

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from typing import Any, cast

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from sqlalchemy.orm import joinedload

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.forms import PlanillaForm
from coati_payroll.i18n import _
from coati_payroll.model import (
    db,
    TipoPlanilla,
    Moneda,
    Empresa,
    VacationPolicy,
    Nomina,
    NominaEmpleado,
    PlanillaIngreso,
    PlanillaDeduccion,
    Percepcion,
    Deduccion,
)

# Constants
SELECT_PLACEHOLDER = "-- Seleccionar --"


def populate_form_choices(form: PlanillaForm):
    """Populate form select choices from database."""
    tipos = (
        db.session.execute(db.select(TipoPlanilla).filter_by(activo=True).order_by(TipoPlanilla.codigo)).scalars().all()
    )
    form.tipo_planilla_id.choices = [("", _(SELECT_PLACEHOLDER))] + [
        (t.id, f"{t.codigo} - {t.descripcion or t.codigo}") for t in tipos
    ]

    monedas = db.session.execute(db.select(Moneda).filter_by(activo=True).order_by(Moneda.codigo)).scalars().all()
    form.moneda_id.choices = [("", _(SELECT_PLACEHOLDER))] + [(m.id, f"{m.codigo} - {m.nombre}") for m in monedas]

    empresas = (
        db.session.execute(db.select(Empresa).filter_by(activo=True).order_by(Empresa.razon_social)).scalars().all()
    )
    form.empresa_id.choices = [("", _(SELECT_PLACEHOLDER))] + [
        (e.id, f"{e.codigo} - {e.razon_social}") for e in empresas
    ]

    vacation_policies = (
        db.session.execute(db.select(VacationPolicy).filter_by(activo=True).order_by(VacationPolicy.codigo))
        .scalars()
        .all()
    )
    form.vacation_policy_id.choices = [("", _("-- Sin regla vinculada --"))] + [
        (
            p.id,
            f"{p.codigo} - {p.nombre}"
            + (
                f" [Planilla: {p.planilla.nombre}]"
                if p.planilla
                else (f" [Empresa: {p.empresa.razon_social}]" if p.empresa else " [Global]")
            ),
        )
        for p in vacation_policies
    ]


def populate_novedad_form_choices(form, nomina_id: str):
    """Populate form select choices for novedad form."""
    nomina = db.session.get(Nomina, nomina_id)

    # Get employees associated with this nomina with eager loading
    nomina_empleados = (
        db.session.execute(
            db.select(NominaEmpleado)
            .filter_by(nomina_id=nomina_id)
            .options(joinedload(cast(Any, NominaEmpleado.empleado)))
        )
        .scalars()
        .all()
    )
    form.empleado_id.choices = [("", _("-- Seleccionar Empleado --"))] + [
        (
            ne.empleado.id,
            f"{ne.empleado.primer_nombre} {ne.empleado.primer_apellido} ({ne.empleado.codigo_empleado})",
        )
        for ne in nomina_empleados
    ]

    if nomina is None:
        form.percepcion_id.choices = [("", _("-- Seleccionar Percepción --"))]
        form.deduccion_id.choices = [("", _("-- Seleccionar Deducción --"))]
        return

    # Get active percepciones assigned to this planilla
    percepciones = (
        db.session.execute(
            db.select(Percepcion)
            .join(PlanillaIngreso, PlanillaIngreso.percepcion_id == Percepcion.id)
            .where(
                PlanillaIngreso.planilla_id == nomina.planilla_id,
                PlanillaIngreso.activo.is_(True),
                Percepcion.activo.is_(True),
            )
            .order_by(PlanillaIngreso.orden.asc(), Percepcion.nombre.asc())
        )
        .scalars()
        .all()
    )
    form.percepcion_id.choices = [("", _("-- Seleccionar Percepción --"))] + [
        (p.id, f"{p.codigo} - {p.nombre}") for p in percepciones
    ]

    # Get active deducciones assigned to this planilla excluding tax/social security
    deducciones = (
        db.session.execute(
            db.select(Deduccion)
            .join(PlanillaDeduccion, PlanillaDeduccion.deduccion_id == Deduccion.id)
            .where(
                PlanillaDeduccion.planilla_id == nomina.planilla_id,
                PlanillaDeduccion.activo.is_(True),
                Deduccion.activo.is_(True),
                ~Deduccion.tipo.in_(["tax", "social_security"]),
            )
            .order_by(PlanillaDeduccion.prioridad.asc(), Deduccion.nombre.asc())
        )
        .scalars()
        .all()
    )
    form.deduccion_id.choices = [("", _("-- Seleccionar Deducción --"))] + [
        (d.id, f"{d.codigo} - {d.nombre}") for d in deducciones
    ]


def get_concepto_ids_from_form(form) -> tuple[str | None, str | None]:
    """Extract percepcion_id and deduccion_id from form based on tipo_concepto.

    Args:
        form: The NominaNovedadForm with submitted data

    Returns:
        Tuple of (percepcion_id, deduccion_id) - one will be set, other will be None
    """
    percepcion_id = None
    deduccion_id = None

    tipo_concepto = {
        "percepcion": "income",
        "deduccion": "deduction",
    }.get(form.tipo_concepto.data, form.tipo_concepto.data)

    if tipo_concepto == "income":
        percepcion_id = form.percepcion_id.data if form.percepcion_id.data else None
    else:
        deduccion_id = form.deduccion_id.data if form.deduccion_id.data else None

    return percepcion_id, deduccion_id
