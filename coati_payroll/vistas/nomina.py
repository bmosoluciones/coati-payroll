# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Nominas (Payruns) list view - top-level access to all payroll runs."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from coati_payroll.model import Nomina, Planilla, Empresa, db
from coati_payroll.rbac import require_read_access
from coati_payroll.vistas.constants import PER_PAGE
from coati_payroll.tenant import accessible_empresas, scope_company_query

nomina_bp = Blueprint("nomina", __name__, url_prefix="/nominas")


@nomina_bp.route("/", methods=["GET"])
@require_read_access()
def index():
    """List all nominas (payruns) with pagination and filters."""
    page = request.args.get("page", 1, type=int)

    # Get filter parameters
    planilla_id = request.args.get("planilla_id", type=str) if request.args.get("planilla_id") else None
    empresa_id = request.args.get("empresa_id", type=str) if request.args.get("empresa_id") else None
    estado = request.args.get("estado", type=str)
    fecha_desde = request.args.get("fecha_desde", type=str)
    fecha_hasta = request.args.get("fecha_hasta", type=str)

    # Build query with filters
    query = scope_company_query(db.select(Nomina).join(Nomina.planilla), Planilla.empresa_id)

    if planilla_id:
        query = query.filter(Nomina.planilla_id == planilla_id)

    if empresa_id:
        query = query.filter(Planilla.empresa_id == empresa_id)

    if estado:
        query = query.filter(Nomina.estado == estado)

    if fecha_desde:
        query = query.filter(Nomina.periodo_fin >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Nomina.periodo_inicio <= fecha_hasta)

    query = query.order_by(Nomina.fecha_generacion.desc())

    pagination = db.paginate(
        query,
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )

    # Get choices for filter dropdowns
    planillas = db.session.execute(
        scope_company_query(db.select(Planilla), Planilla.empresa_id).filter_by(activo=True).order_by(Planilla.nombre)
    ).scalars().all()
    empresas = accessible_empresas()

    return render_template(
        "modules/nominas/index.html",
        nominas=pagination.items,
        pagination=pagination,
        planilla_id=planilla_id,
        empresa_id=empresa_id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        planillas=planillas,
        empresas=empresas,
    )
