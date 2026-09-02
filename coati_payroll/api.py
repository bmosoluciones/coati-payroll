# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Small versioned REST API for integrations.

The API intentionally uses opaque bearer tokens rather than session cookies.
Only token hashes are stored, and every tenant-scoped query is resolved from
the token owner instead of trusting request parameters.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import secrets
from functools import wraps
from typing import Any, Callable

from flask import Blueprint, g, jsonify, request

from coati_payroll.enums import TipoUsuario
from coati_payroll.model import ApiToken, Empleado, Nomina, NominaEmpleado, Planilla, Report, db

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_api_token(usuario, nombre: str, scopes: set[str] | None = None, expires_at=None) -> tuple[ApiToken, str]:
    """Create a token and return the raw secret exactly once."""
    raw_token = secrets.token_urlsafe(32)
    record = ApiToken(
        usuario=usuario,
        nombre=nombre,
        token_hash=_hash_token(raw_token),
        alcances={scope: True for scope in (scopes or {"read"})},
        expira_en=expires_at,
    )
    db.session.add(record)
    db.session.flush()
    return record, raw_token


def _require_token(scope: str = "read"):
    def decorator(view: Callable):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            scheme, _, raw_token = header.partition(" ")
            if scheme.lower() != "bearer" or not raw_token:
                return jsonify(error="Bearer token required"), 401
            record = db.session.execute(db.select(ApiToken).filter_by(token_hash=_hash_token(raw_token))).scalar_one_or_none()
            now = datetime.now(UTC)
            if record is None or record.revocado_en is not None or not record.usuario or not record.usuario.activo:
                return jsonify(error="Invalid or revoked token"), 401
            expires_at = record.expira_en
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at is not None and expires_at <= now:
                return jsonify(error="Expired token"), 401
            if not (record.alcances or {}).get(scope, False):
                return jsonify(error="Insufficient scope"), 403
            record.ultimo_uso_en = now
            g.api_user = record.usuario
            g.api_token = record
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _company_ids() -> list[str] | None:
    user = g.api_user
    if user.tipo == TipoUsuario.ADMIN.value:
        return None
    return [empresa.id for empresa in user.empresas]


def _employee_allowed(employee_id: str) -> bool:
    company_ids = _company_ids()
    employee = db.session.get(Empleado, employee_id)
    return employee is not None and (company_ids is None or employee.empresa_id in company_ids)


@api_bp.get("/health")
def health():
    return jsonify(status="ok", version="v1")


@api_bp.get("/employees")
@_require_token()
def employees():
    query = db.select(Empleado).order_by(Empleado.codigo_empleado)
    company_ids = _company_ids()
    if company_ids is not None:
        query = query.where(Empleado.empresa_id.in_(company_ids))
    rows = db.session.execute(query).scalars().all()
    return jsonify(data=[{
        "id": employee.id, "codigo": employee.codigo_empleado,
        "nombre": f"{employee.primer_nombre} {employee.primer_apellido}".strip(),
        "empresa_id": employee.empresa_id, "activo": employee.activo,
    } for employee in rows])


@api_bp.get("/payrolls")
@_require_token()
def payrolls():
    query = db.select(Nomina).join(Planilla, Planilla.id == Nomina.planilla_id).order_by(Nomina.periodo_fin.desc())
    company_ids = _company_ids()
    if company_ids is not None:
        query = query.where(Planilla.empresa_id.in_(company_ids))
    rows = db.session.execute(query.limit(100)).scalars().all()
    return jsonify(data=[{
        "id": payroll.id, "planilla_id": payroll.planilla_id,
        "periodo_inicio": payroll.periodo_inicio.isoformat(), "periodo_fin": payroll.periodo_fin.isoformat(),
        "estado": payroll.estado, "total_neto": str(payroll.total_neto or 0),
    } for payroll in rows])


@api_bp.get("/payrolls/<string:payroll_id>/results")
@_require_token()
def payroll_results(payroll_id: str):
    payroll = db.session.get(Nomina, payroll_id)
    if payroll is None or not payroll.planilla or (_company_ids() is not None and payroll.planilla.empresa_id not in _company_ids()):
        return jsonify(error="Payroll not found"), 404
    employees = db.session.execute(db.select(NominaEmpleado).filter_by(nomina_id=payroll.id)).scalars().all()
    return jsonify(data=[{
        "employee_id": row.empleado_id, "gross": str(row.salario_bruto or 0),
        "income": str(row.total_ingresos or 0), "deductions": str(row.total_deducciones or 0),
        "net": str(row.salario_neto or 0),
    } for row in employees])


@api_bp.get("/reports")
@_require_token()
def reports():
    rows = db.session.execute(db.select(Report).filter_by(status="enabled").order_by(Report.name)).scalars().all()
    return jsonify(data=[{"id": row.id, "name": row.name, "category": row.category} for row in rows])


@api_bp.get("/novelties")
@_require_token()
def novelties_list():
    from coati_payroll.model import NominaNovedad

    query = db.select(NominaNovedad).order_by(NominaNovedad.fecha_novedad.desc()).limit(100)
    rows = db.session.execute(query).scalars().all()
    rows = [row for row in rows if _employee_allowed(row.empleado_id)]
    return jsonify(data=[{"id": row.id, "empleado_id": row.empleado_id, "codigo_concepto": row.codigo_concepto,
                         "valor": str(row.valor_cantidad)} for row in rows])


@api_bp.post("/novelties")
@_require_token("write")
def novelties_create():
    from coati_payroll.model import NominaNovedad

    payload: dict[str, Any] = request.get_json(silent=True) or {}
    employee_id = payload.get("empleado_id")
    if not employee_id or not _employee_allowed(employee_id) or not payload.get("codigo_concepto"):
        return jsonify(error="empleado_id and codigo_concepto are required"), 400
    novelty = NominaNovedad(
        empleado_id=employee_id, codigo_concepto=payload["codigo_concepto"],
        tipo_valor=payload.get("tipo_valor", "monto"), valor_cantidad=payload.get("valor_cantidad", 0),
        creado_por=g.api_user.usuario,
    )
    db.session.add(novelty)
    db.session.commit()
    return jsonify(id=novelty.id), 201
