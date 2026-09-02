# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Views for managing Planilla (master payroll) and its associations.

A Planilla is the central hub that connects:
- Employees (via PlanillaEmpleado)
- Perceptions (via PlanillaIngreso)
- Deductions (via PlanillaDeduccion) - with priority ordering
- Benefits/Prestaciones (via PlanillaPrestacion)
- Calculation Rules (via PlanillaReglaCalculo)
"""

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from importlib import import_module

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from flask import Blueprint, abort, request
from flask_login import current_user

from coati_payroll.model import Nomina, Planilla, db
from coati_payroll.tenant import company_is_accessible

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #

# Create the blueprint
planilla_bp = Blueprint("planilla", __name__, url_prefix="/planilla")


@planilla_bp.before_request
def enforce_planilla_tenant_scope():
    """Protect every planilla sub-route, including routes added by modules."""
    # Let the route-level RBAC decorators produce the normal login redirect.
    if not current_user.is_authenticated:
        return
    view_args = request.view_args or {}
    planilla_id = view_args.get("planilla_id")
    if planilla_id:
        planilla = db.session.get(Planilla, planilla_id)
        if planilla is None or not company_is_accessible(planilla.empresa_id):
            abort(404)
        return

    nomina_id = view_args.get("nomina_id")
    if nomina_id:
        nomina = db.session.get(Nomina, nomina_id)
        if nomina is None or nomina.planilla is None or not company_is_accessible(nomina.planilla.empresa_id):
            abort(404)

# Import all route modules to register them with the blueprint
# This must be done after creating the blueprint
for module_name in (
    "coati_payroll.vistas.planilla.routes",
    "coati_payroll.vistas.planilla.config_routes",
    "coati_payroll.vistas.planilla.association_routes",
    "coati_payroll.vistas.planilla.nomina_routes",
    "coati_payroll.vistas.planilla.novedad_routes",
    "coati_payroll.vistas.planilla.export_routes",
):
    import_module(module_name)

__all__ = ["planilla_bp"]
