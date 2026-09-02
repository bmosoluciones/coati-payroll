# SPDX-License-Identifier: Apache-2.0
"""Unified audit viewer and CSV export."""

from __future__ import annotations

import csv
import io
from flask import Blueprint, Response, render_template, request

from coati_payroll.enums import TipoUsuario
from coati_payroll.model import (
    ConceptoAuditLog, NominaAuditLog, PlanillaAuditLog, ReglaCalculoAuditLog,
    ReportAudit, SecurityAuditLog, db,
)
from coati_payroll.rbac import require_role

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


def _entries() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for model, source, action_attr, actor_attr, target_attr, details_attr in (
        (SecurityAuditLog, "security", "event", "actor", "target_username", "details"),
        (ReportAudit, "report", "action", "performed_by", None, "changes"),
        (ConceptoAuditLog, "concept", "accion", "usuario", None, "cambios"),
        (PlanillaAuditLog, "planilla", "accion", "usuario", None, "cambios"),
        (NominaAuditLog, "nomina", "accion", "usuario", None, "cambios"),
        (ReglaCalculoAuditLog, "rule", "accion", "usuario", None, "cambios"),
    ):
        rows = db.session.execute(db.select(model).order_by(model.timestamp.desc())).scalars()
        for row in rows:
            entries.append({
                "timestamp": row.timestamp,
                "source": source,
                "action": getattr(row, action_attr),
                "actor": getattr(row, actor_attr),
                "target": getattr(row, target_attr) if target_attr else None,
                "details": getattr(row, details_attr) or {},
                "success": getattr(row, "success", True),
            })
    return sorted(entries, key=lambda item: item["timestamp"], reverse=True)


def _filtered_entries() -> list[dict[str, object]]:
    source = request.args.get("source")
    actor = request.args.get("actor", "").strip().lower()
    target = request.args.get("target", "").strip().lower()
    action = request.args.get("action", "").strip().lower()
    entries = _entries()
    return [entry for entry in entries if
            (not source or entry["source"] == source) and
            (not actor or actor in str(entry["actor"]).lower()) and
            (not target or target in str(entry["target"] or "").lower()) and
            (not action or action in str(entry["action"]).lower())]


@audit_bp.get("/")
@require_role(TipoUsuario.ADMIN, TipoUsuario.AUDIT)
def index():
    entries = _filtered_entries()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 50
    start = (page - 1) * per_page
    return render_template(
        "modules/audit/index.html", entries=entries[start:start + per_page], total=len(entries),
        page=page, filters={key: request.args.get(key, "") for key in ("source", "actor", "target", "action")},
    )


@audit_bp.get("/export.csv")
@require_role(TipoUsuario.ADMIN, TipoUsuario.AUDIT)
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "source", "action", "actor", "target", "success", "details"])
    for entry in _filtered_entries():
        writer.writerow([entry["timestamp"], entry["source"], entry["action"], entry["actor"], entry["target"], entry["success"], entry["details"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=audit.csv"})
