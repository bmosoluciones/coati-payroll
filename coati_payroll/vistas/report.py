# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Report management routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify, send_file
from flask_login import current_user
from sqlalchemy import true

from coati_payroll.enums import ReportType, ReportStatus, TipoUsuario
from coati_payroll.i18n import _
from coati_payroll.model import db, Report, ReportRole, ReportExecution, ReportAudit
from coati_payroll.rbac import require_read_access, require_role
from coati_payroll.report_engine import (
    ReportExecutionManager,
    can_view_report,
    can_execute_report,
    can_export_report,
)
from coati_payroll.report_export import export_report_to_excel, export_report_to_csv, export_report_to_pdf
from coati_payroll.system_reports import get_system_report_metadata
from coati_payroll.log import log
from coati_payroll.vistas.constants import PER_PAGE

report_bp = Blueprint("report", __name__, url_prefix="/report")
REPORT_INDEX_ENDPOINT = "report.index"
REPORT_ADMIN_INDEX_ENDPOINT = "report.admin_index"
REPORT_NOT_FOUND_MESSAGE = "Reporte no encontrado."


# ============================================================================
# Report List and Administration
# ============================================================================


@report_bp.route("/", methods=["GET"])
@require_read_access()
def index():
    """List all available reports.

    Shows reports based on user permissions.
    """
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "", type=str)
    report_type = request.args.get("type", "", type=str)
    status = request.args.get("status", "", type=str)

    # Base query
    stmt = db.select(Report)

    # Apply filters
    if category:
        stmt = stmt.filter(Report.category == category)
    if report_type:
        stmt = stmt.filter(Report.type == report_type)
    if status:
        stmt = stmt.filter(Report.status == status)

    # Only show enabled reports to non-admin users
    if current_user.tipo != TipoUsuario.ADMIN:
        stmt = stmt.filter(Report.status == ReportStatus.ENABLED)

    # Filter by user permissions
    if current_user.tipo != TipoUsuario.ADMIN:
        # Filter reports where user has view permission
        stmt = stmt.join(ReportRole).filter(ReportRole.role == current_user.tipo, ReportRole.can_view.is_(true()))

    stmt = stmt.order_by(Report.category, Report.name)

    # Paginate using Flask-SQLAlchemy's paginate method
    pagination = db.paginate(stmt, page=page, per_page=PER_PAGE, error_out=False)

    # Get unique categories for filter
    categories = (
        db.session.execute(
            db.select(Report.category).distinct().filter(Report.category.isnot(None)).order_by(Report.category)
        )
        .scalars()
        .all()
    )

    return render_template(
        "modules/report/index.html",
        reports=pagination.items,
        pagination=pagination,
        categories=categories,
        current_category=category,
        current_type=report_type,
        current_status=status,
    )


@report_bp.route("/admin", methods=["GET"])
@require_role(TipoUsuario.ADMIN)
def admin_index():
    """Administrative report list.

    Only accessible to administrators.
    Shows all reports with management options.
    """
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "", type=str)
    report_type = request.args.get("type", "", type=str)
    status = request.args.get("status", "", type=str)

    # Base query - show all reports for admin
    stmt = db.select(Report)

    # Apply filters
    if category:
        stmt = stmt.filter(Report.category == category)
    if report_type:
        stmt = stmt.filter(Report.type == report_type)
    if status:
        stmt = stmt.filter(Report.status == status)

    stmt = stmt.order_by(Report.category, Report.name)

    # Paginate using Flask-SQLAlchemy's paginate method
    pagination = db.paginate(stmt, page=page, per_page=PER_PAGE, error_out=False)

    # Get unique categories
    categories = (
        db.session.execute(
            db.select(Report.category).distinct().filter(Report.category.isnot(None)).order_by(Report.category)
        )
        .scalars()
        .all()
    )

    return render_template(
        "modules/report/admin_index.html",
        reports=pagination.items,
        pagination=pagination,
        categories=categories,
        current_category=category,
        current_type=report_type,
        current_status=status,
    )


# ============================================================================
# Report Execution
# ============================================================================


@report_bp.route("/<report_id>/execute", methods=["GET"])
@require_read_access()
def execute_form(report_id: str):
    """Show report execution form.

    Displays form to input parameters and execute report.
    """
    report = db.session.get(Report, report_id)
    if not report:
        flash(_(REPORT_NOT_FOUND_MESSAGE), "danger")
        return redirect(url_for(REPORT_INDEX_ENDPOINT))

    # Check if report is enabled
    if report.status != ReportStatus.ENABLED and current_user.tipo != TipoUsuario.ADMIN:
        flash(_("Este reporte está deshabilitado."), "warning")
        return redirect(url_for(REPORT_INDEX_ENDPOINT))

    # Check view permission
    if not can_view_report(report, current_user.tipo):
        flash(_("No tiene permisos para ver este reporte."), "danger")
        return redirect(url_for(REPORT_INDEX_ENDPOINT))

    # Check execute permission
    if not can_execute_report(report, current_user.tipo):
        flash(_("No tiene permisos para ejecutar este reporte."), "danger")
        return redirect(url_for(REPORT_INDEX_ENDPOINT))

    # Get metadata for system reports
    metadata = None
    if report.type == ReportType.SYSTEM:
        metadata = get_system_report_metadata(report.system_report_id)

    return render_template("modules/report/execute.html", report=report, metadata=metadata)


@report_bp.route("/<report_id>/run", methods=["POST"])
@require_read_access()
def run_report(report_id: str):
    """Execute report and show results.

    Processes parameters and executes report.
    """
    report = db.session.get(Report, report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404

    # Check permissions
    if report.status != ReportStatus.ENABLED and current_user.tipo != TipoUsuario.ADMIN:
        return jsonify({"error": "Report is disabled"}), 403

    if not can_execute_report(report, current_user.tipo):
        return jsonify({"error": "Permission denied"}), 403

    # Get parameters from request
    parameters = request.get_json() or {}

    if parameters.pop("async", False):
        from coati_payroll.queue.tasks import queue

        task_id = queue.enqueue(
            "generate_report", report_id=report.id, user=current_user.usuario, parameters=parameters
        )
        return jsonify({"success": True, "status": "queued", "task_id": str(task_id)}), 202

    # Get pagination parameters
    page = parameters.pop("page", 1)
    per_page = parameters.pop("per_page", 100)

    try:
        # Execute report
        manager = ReportExecutionManager(report, current_user.usuario)
        results, total_count, execution = manager.execute(parameters, page, per_page)

        return jsonify(
            {
                "success": True,
                "results": results,
                "total_count": total_count,
                "execution_id": execution.id,
                "execution_time_ms": execution.execution_time_ms,
            }
        )

    except Exception as e:
        log.error("Error executing report: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Report Export
# ============================================================================


@report_bp.route("/<report_id>/export/<export_format>", methods=["POST"])
@require_read_access()
def export_report(report_id: str, export_format: str):
    """Export report to specified format.

    Args:
        report_id: Report ID
        export_format: Export format (excel, csv)
    """
    report = db.session.get(Report, report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404

    # Check export permission
    if not can_export_report(report, current_user.tipo):
        flash(_("No tiene permisos para exportar este reporte."), "danger")
        return redirect(url_for("report.execute_form", report_id=report_id))

    # Get parameters from request
    parameters = request.get_json() or {}

    try:
        # Execute report (get all results, no pagination for export)
        manager = ReportExecutionManager(report, current_user.usuario)
        results, _total_count, execution = manager.execute(parameters, page=1, per_page=50000)

        # Export based on format
        if export_format == "excel":
            file_path = export_report_to_excel(report.name, results)
        elif export_format == "csv":
            file_path = export_report_to_csv(report.name, results)
        elif export_format == "pdf":
            file_path = export_report_to_pdf(report.name, results)
        else:
            return jsonify({"error": "Invalid format"}), 400

        # Update execution record with export info
        execution.export_file_path = file_path
        execution.export_format = export_format
        db.session.commit()

        # Send file
        return send_file(file_path, as_attachment=True)

    except Exception as e:
        log.error("Error exporting report: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Report Administration (Admin Only)
# ============================================================================


@report_bp.route("/<report_id>/toggle-status", methods=["POST"])
@require_role(TipoUsuario.ADMIN)
def toggle_status(report_id: str):
    """Toggle report enabled/disabled status.

    Only accessible to administrators.
    """
    report = db.session.get(Report, report_id)
    if not report:
        flash(_(REPORT_NOT_FOUND_MESSAGE), "danger")
        return redirect(url_for(REPORT_ADMIN_INDEX_ENDPOINT))

    # Toggle status
    old_status = report.status
    report.status = ReportStatus.DISABLED if report.status == ReportStatus.ENABLED else ReportStatus.ENABLED

    # Create audit entry
    audit = ReportAudit(
        report_id=report.id,
        action="status_changed",
        performed_by=current_user.usuario,
        changes={"old_status": old_status, "new_status": report.status},
    )
    db.session.add(audit)
    db.session.commit()

    flash(_("Estado del reporte actualizado."), "success")
    return redirect(url_for(REPORT_ADMIN_INDEX_ENDPOINT))


@report_bp.route("/<report_id>/permissions", methods=["GET"])
@require_role(TipoUsuario.ADMIN)
def permissions_form(report_id: str):
    """Show report permissions form.

    Allows administrators to configure role-based permissions.
    """
    report = db.session.get(Report, report_id)
    if not report:
        flash(_(REPORT_NOT_FOUND_MESSAGE), "danger")
        return redirect(url_for(REPORT_ADMIN_INDEX_ENDPOINT))

    # Get existing permissions
    permissions = cast(list[Any], report.permissions)
    existing_permissions = {perm.role: perm for perm in permissions}

    return render_template(
        "modules/report/permissions.html", report=report, existing_permissions=existing_permissions, roles=TipoUsuario
    )


@report_bp.route("/<report_id>/permissions", methods=["POST"])
@require_role(TipoUsuario.ADMIN)
def update_permissions(report_id: str):
    """Update report permissions.

    Processes form and updates role-based permissions.
    """
    report = db.session.get(Report, report_id)
    if not report:
        flash(_(REPORT_NOT_FOUND_MESSAGE), "danger")
        return redirect(url_for(REPORT_ADMIN_INDEX_ENDPOINT))

    # Process permissions for each role
    for role in [TipoUsuario.ADMIN, TipoUsuario.HHRR, TipoUsuario.AUDIT]:
        can_view = request.form.get(f"{role}_can_view") == "on"
        can_execute = request.form.get(f"{role}_can_execute") == "on"
        can_export = request.form.get(f"{role}_can_export") == "on"

        # Get or create permission record
        perm = db.session.execute(db.select(ReportRole).filter_by(report_id=report.id, role=role)).scalar_one_or_none()

        if perm:
            # Update existing
            perm.can_view = can_view
            perm.can_execute = can_execute
            perm.can_export = can_export
        else:
            # Create new
            perm = ReportRole(
                report_id=report.id, role=role, can_view=can_view, can_execute=can_execute, can_export=can_export
            )
            db.session.add(perm)

    # Create audit entry
    audit = ReportAudit(
        report_id=report.id,
        action="permissions_updated",
        performed_by=current_user.usuario,
        changes={"timestamp": datetime.now().isoformat()},
    )
    db.session.add(audit)
    db.session.commit()

    flash(_("Permisos actualizados correctamente."), "success")
    return redirect(url_for(REPORT_ADMIN_INDEX_ENDPOINT))


# ============================================================================
# Report Detail
# ============================================================================


@report_bp.route("/<report_id>", methods=["GET"])
@require_read_access()
def detail(report_id: str):
    """Show report details.

    Displays report information, definition, and execution history.
    """
    report = db.session.get(Report, report_id)
    if not report:
        flash(_(REPORT_NOT_FOUND_MESSAGE), "danger")
        return redirect(url_for(REPORT_INDEX_ENDPOINT))

    # Check view permission
    if not can_view_report(report, current_user.tipo):
        flash(_("No tiene permisos para ver este reporte."), "danger")
        return redirect(url_for(REPORT_INDEX_ENDPOINT))

    # Get recent executions
    executions = (
        db.session.execute(
            db.select(ReportExecution)
            .filter_by(report_id=report.id)
            .order_by(ReportExecution.timestamp.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )

    # Get metadata for system reports
    metadata = None
    if report.type == ReportType.SYSTEM:
        metadata = get_system_report_metadata(report.system_report_id)

    return render_template("modules/report/detail.html", report=report, executions=executions, metadata=metadata)
