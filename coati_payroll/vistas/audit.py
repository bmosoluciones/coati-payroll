# SPDX-License-Identifier: Apache-2.0
"""Unified audit viewer and CSV export with paginated queries."""

from __future__ import annotations

import csv
import io
from typing import Any, Sequence

from flask import Blueprint, Response, render_template, request
from sqlalchemy import union_all

from coati_payroll.enums import TipoUsuario
from coati_payroll.model import (
    ConceptoAuditLog,
    NominaAuditLog,
    PlanillaAuditLog,
    ReglaCalculoAuditLog,
    ReportAudit,
    SecurityAuditLog,
    db,
)
from coati_payroll.rbac import require_role

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


def _normalize_entry(row: Sequence[Any]) -> dict[str, object]:
    """Normalize audit entry from any source model."""
    timestamp, source, action, actor, target, details, success = row
    return {
        "timestamp": timestamp,
        "source": source,
        "action": action,
        "actor": actor,
        "target": target,
        "details": details or {},
        "success": success,
    }


def _get_filtered_query(limit: int | None = None, offset: int | None = None):
    """Build paginated unified audit query across all sources."""
    source_filter = request.args.get("source")
    actor_filter = request.args.get("actor", "").strip().lower()
    target_filter = request.args.get("target", "").strip().lower()
    action_filter = request.args.get("action", "").strip().lower()

    queries = []

    # SecurityAuditLog
    if not source_filter or source_filter == "security":
        q = db.select(
            SecurityAuditLog.timestamp,
            db.literal("security").label("source"),
            SecurityAuditLog.event,
            SecurityAuditLog.actor,
            SecurityAuditLog.target_username,
            SecurityAuditLog.details,
            SecurityAuditLog.success,
        )
        if actor_filter:
            q = q.filter(SecurityAuditLog.actor.ilike(f"%{actor_filter}%"))
        if target_filter:
            q = q.filter(SecurityAuditLog.target_username.ilike(f"%{target_filter}%"))
        if action_filter:
            q = q.filter(SecurityAuditLog.event.ilike(f"%{action_filter}%"))
        queries.append(q)

    # ReportAudit
    if not source_filter or source_filter == "report":
        q = db.select(
            ReportAudit.timestamp,
            db.literal("report").label("source"),
            ReportAudit.action,
            ReportAudit.performed_by,
            db.literal(None),
            ReportAudit.changes,
            db.literal(True),
        )
        if actor_filter:
            q = q.filter(ReportAudit.performed_by.ilike(f"%{actor_filter}%"))
        if action_filter:
            q = q.filter(ReportAudit.action.ilike(f"%{action_filter}%"))
        queries.append(q)

    # ConceptoAuditLog
    if not source_filter or source_filter == "concept":
        q = db.select(
            ConceptoAuditLog.timestamp,
            db.literal("concept").label("source"),
            ConceptoAuditLog.accion,
            ConceptoAuditLog.usuario,
            db.literal(None),
            ConceptoAuditLog.cambios,
            db.literal(True),
        )
        if actor_filter:
            q = q.filter(ConceptoAuditLog.usuario.ilike(f"%{actor_filter}%"))
        if action_filter:
            q = q.filter(ConceptoAuditLog.accion.ilike(f"%{action_filter}%"))
        queries.append(q)

    # PlanillaAuditLog
    if not source_filter or source_filter == "planilla":
        q = db.select(
            PlanillaAuditLog.timestamp,
            db.literal("planilla").label("source"),
            PlanillaAuditLog.accion,
            PlanillaAuditLog.usuario,
            db.literal(None),
            PlanillaAuditLog.cambios,
            db.literal(True),
        )
        if actor_filter:
            q = q.filter(PlanillaAuditLog.usuario.ilike(f"%{actor_filter}%"))
        if action_filter:
            q = q.filter(PlanillaAuditLog.accion.ilike(f"%{action_filter}%"))
        queries.append(q)

    # NominaAuditLog
    if not source_filter or source_filter == "nomina":
        q = db.select(
            NominaAuditLog.timestamp,
            db.literal("nomina").label("source"),
            NominaAuditLog.accion,
            NominaAuditLog.usuario,
            db.literal(None),
            NominaAuditLog.cambios,
            db.literal(True),
        )
        if actor_filter:
            q = q.filter(NominaAuditLog.usuario.ilike(f"%{actor_filter}%"))
        if action_filter:
            q = q.filter(NominaAuditLog.accion.ilike(f"%{action_filter}%"))
        queries.append(q)

    # ReglaCalculoAuditLog
    if not source_filter or source_filter == "rule":
        q = db.select(
            ReglaCalculoAuditLog.timestamp,
            db.literal("rule").label("source"),
            ReglaCalculoAuditLog.accion,
            ReglaCalculoAuditLog.usuario,
            db.literal(None),
            ReglaCalculoAuditLog.cambios,
            db.literal(True),
        )
        if actor_filter:
            q = q.filter(ReglaCalculoAuditLog.usuario.ilike(f"%{actor_filter}%"))
        if action_filter:
            q = q.filter(ReglaCalculoAuditLog.accion.ilike(f"%{action_filter}%"))
        queries.append(q)

    if not queries:
        return None

    # Union all queries and order by timestamp
    combined = union_all(*queries).order_by(db.desc(db.literal_column("timestamp")))

    if limit:
        combined = combined.limit(limit)
    if offset:
        combined = combined.offset(offset)

    return combined


def _entries(limit: int | None = None, offset: int | None = None) -> list[dict[str, object]]:
    """Fetch paginated audit entries from all sources."""
    query = _get_filtered_query(limit, offset)
    if query is None:
        return []

    entries = []

    for row in db.session.execute(query).all():
        # Determine source based on non-null fields
        entries.append(_normalize_entry(row))

    return entries


def _get_total_count() -> int:
    """Get total count of audit entries matching filters without pagination."""
    query = _get_filtered_query()
    if query is None:
        return 0
    return db.session.execute(db.select(db.func.count()).select_from(query.subquery())).scalar() or 0


@audit_bp.get("/")
@require_role(TipoUsuario.ADMIN, TipoUsuario.AUDIT)
def index():
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 50
    offset = (page - 1) * per_page

    entries = _entries(limit=per_page, offset=offset)
    total = _get_total_count()

    return render_template(
        "modules/audit/index.html",
        entries=entries,
        total=total,
        page=page,
        filters={key: request.args.get(key, "") for key in ("source", "actor", "target", "action")},
    )


@audit_bp.get("/export.csv")
@require_role(TipoUsuario.ADMIN, TipoUsuario.AUDIT)
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "source", "action", "actor", "target", "success", "details"])

    # Fetch all entries (unfiltered by pagination) for export
    query = _get_filtered_query()
    if query is not None:
        for row in db.session.execute(query).all():
            timestamp, source, action, actor, target, details, success = row
            writer.writerow(
                [
                    timestamp,
                    source,
                    action,
                    actor,
                    target,
                    success,
                    details,
                ]
            )

    return Response(
        output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=audit.csv"}
    )
