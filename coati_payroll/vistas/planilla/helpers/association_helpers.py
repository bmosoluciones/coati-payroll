# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Helper functions for managing planilla associations."""

from sqlalchemy import select
from sqlalchemy.sql.functions import count
from coati_payroll.model import (
    db,
    Nomina,
    Planilla,
    PlanillaEmpleado,
    PlanillaIngreso,
    PlanillaDeduccion,
    PlanillaPrestacion,
    PlanillaReglaCalculo,
)


def get_planilla_component_counts(planilla_id: str) -> dict:
    """Get counts of all components associated with a planilla.

    Returns a dictionary with counts for empleados, percepciones, deducciones,
    prestaciones, and reglas.
    """
    return {
        "empleados_count": db.session.execute(
            select(count()).select_from(PlanillaEmpleado).filter_by(planilla_id=planilla_id)
        ).scalar(),
        "percepciones_count": db.session.execute(
            select(count()).select_from(PlanillaIngreso).filter_by(planilla_id=planilla_id)
        ).scalar(),
        "deducciones_count": db.session.execute(
            select(count()).select_from(PlanillaDeduccion).filter_by(planilla_id=planilla_id)
        ).scalar(),
        "prestaciones_count": db.session.execute(
            select(count()).select_from(PlanillaPrestacion).filter_by(planilla_id=planilla_id)
        ).scalar(),
        "reglas_count": db.session.execute(
            select(count()).select_from(PlanillaReglaCalculo).filter_by(planilla_id=planilla_id)
        ).scalar(),
    }


def get_nomina_counts_by_planilla(planilla_ids: list[str]) -> dict[str, int]:
    """Get nomina counts grouped by planilla id."""
    if not planilla_ids:
        return {}

    rows = db.session.execute(
        select(Nomina.planilla_id, count(Nomina.id))
        .where(Nomina.planilla_id.in_(planilla_ids))
        .group_by(Nomina.planilla_id)
    ).all()

    counts = dict.fromkeys(planilla_ids, 0)
    counts.update(dict(tuple(row) for row in rows))
    return counts


_COMPONENT_REGISTRY = {
    "income": {
        "model": PlanillaIngreso,
        "fk_field": "percepcion_id",
        "create_fields": lambda cid, extra, user: dict(
            percepcion_id=cid, orden=extra.get("orden", 0), editable=True, activo=True, creado_por=user,
        ),
    },
    "deduction": {
        "model": PlanillaDeduccion,
        "fk_field": "deduccion_id",
        "create_fields": lambda cid, extra, user: dict(
            deduccion_id=cid, prioridad=extra.get("prioridad", 100),
            es_obligatoria=extra.get("es_obligatoria", False), editable=True, activo=True, creado_por=user,
        ),
    },
    "benefit": {
        "model": PlanillaPrestacion,
        "fk_field": "prestacion_id",
        "create_fields": lambda cid, extra, user: dict(
            prestacion_id=cid, orden=extra.get("orden", 0), editable=True, activo=True, creado_por=user,
        ),
    },
    "regla": {
        "model": PlanillaReglaCalculo,
        "fk_field": "regla_calculo_id",
        "create_fields": lambda cid, extra, user: dict(
            regla_calculo_id=cid, orden=extra.get("orden", 0), activo=True, creado_por=user,
        ),
    },
}


def agregar_asociacion(
    planilla_id: str,
    tipo_componente: str,
    componente_id: str,
    datos_extra: dict | None = None,
    usuario: str | None = None,
) -> tuple[bool, str | None, str | None]:
    """Generic function to add any component association to a planilla.

    Args:
        planilla_id: ID of the planilla
        tipo_componente: Type of component ('percepcion', 'deduccion', 'prestacion', 'regla')
        componente_id: ID of the component to associate
        datos_extra: Additional data for the association (orden, prioridad, etc.)
        usuario: Username of the user creating the association

    Returns:
        Tuple of (success, error_message, association_id). If success is False, error_message is set.
    """
    datos_extra = datos_extra or {}
    usuario = usuario or "system"

    planilla = db.session.get(Planilla, planilla_id)
    if not planilla:
        return False, "Planilla no encontrada", None

    if not componente_id:
        return False, f"Debe seleccionar una {tipo_componente}.", None

    tipo_componente = {"percepcion": "income", "deduccion": "deduction", "prestacion": "benefit"}.get(
        tipo_componente, tipo_componente
    )

    reg = _COMPONENT_REGISTRY.get(tipo_componente)
    if not reg:
        return False, f"Tipo de componente desconocido: {tipo_componente}", None

    filter_params = {"planilla_id": planilla_id, reg["fk_field"]: componente_id}
    existing = db.session.execute(db.select(reg["model"]).filter_by(**filter_params)).scalar_one_or_none()
    if existing:
        return False, f"La {tipo_componente} ya está asignada a esta planilla.", None

    association = reg["model"](
        planilla_id=planilla_id,
        **reg["create_fields"](componente_id, datos_extra, usuario),
    )
    db.session.add(association)
    db.session.commit()

    return True, None, association.id
