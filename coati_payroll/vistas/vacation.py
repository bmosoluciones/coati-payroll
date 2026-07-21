# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Vacation module views.

This module provides views for managing vacation policies, accounts, and leave requests.
Implements a robust, auditable, and country-agnostic vacation management system.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.functions import count

from coati_payroll.enums import TipoUsuario, VacacionEstado, VacationLedgerType
from coati_payroll.i18n import _
from coati_payroll.model import (
    db,
    VacationPolicy,
    VacationAccount,
    VacationLedger,
    VacationNovelty,
    Empleado,
    Empresa,
)
from coati_payroll.rbac import require_role, require_read_access, require_write_access
from coati_payroll.vistas.constants import MSG_EMPLEADO_NO_ENCONTRADO

vacation_bp = Blueprint("vacation", __name__, url_prefix="/vacation")


# ============================================================================
# Vacation Policy Management
# ============================================================================


@vacation_bp.route("/policies")
@require_read_access()
def policy_index():
    """List all vacation policies."""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = db.select(VacationPolicy).order_by(VacationPolicy.nombre)
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    policies = pagination.items

    return render_template(
        "modules/vacation/policy_index.html",
        policies=policies,
        pagination=pagination,
    )


def _normalize_policy_optional_defaults(form):
    """Normalize optional policy fields with DB-required defaults."""
    if form.accrual_rate.data is None:
        form.accrual_rate.data = Decimal("0.0")
    if form.min_service_days.data is None:
        form.min_service_days.data = 0


@vacation_bp.route("/policies/new", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def policy_new():
    """Create a new vacation policy. Only administrators can create policies."""
    from coati_payroll.forms import VacationPolicyForm
    from coati_payroll.model import Planilla

    form = VacationPolicyForm()

    # Populate planilla choices
    planillas = (
        db.session.execute(
            db.select(Planilla)
            .options(selectinload(Planilla.empresa))
            .filter(Planilla.activo.is_(True))
            .order_by(Planilla.nombre)
        )
        .scalars()
        .all()
    )
    form.planilla_id.choices = [("", _("-- Seleccionar Planilla --"))] + [
        (p.id, f"{p.nombre} ({p.empresa.razon_social if p.empresa else 'N/A'})") for p in planillas
    ]

    # Populate empresa choices
    empresas = (
        db.session.execute(db.select(Empresa).filter(Empresa.activo.is_(True)).order_by(Empresa.razon_social))
        .scalars()
        .all()
    )
    form.empresa_id.choices = [("", _("-- Seleccionar Empresa --"))] + [(e.id, e.razon_social) for e in empresas]

    if form.validate_on_submit():
        _normalize_policy_optional_defaults(form)
        policy = VacationPolicy()
        form.populate_obj(policy)
        policy.creado_por = current_user.usuario

        db.session.add(policy)
        try:
            db.session.commit()
            flash(_("Política de vacaciones creada exitosamente."), "success")
            return redirect(url_for("vacation.policy_index"))
        except Exception as e:
            db.session.rollback()
            flash(_("Error al crear la política: {}").format(str(e)), "danger")

    return render_template(
        "modules/vacation/policy_form.html",
        form=form,
        titulo=_("Nueva Política de Vacaciones"),
    )


@vacation_bp.route("/policies/<string:policy_id>/edit", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def policy_edit(policy_id):
    """Edit an existing vacation policy. Only administrators can edit policies."""
    from coati_payroll.forms import VacationPolicyForm
    from coati_payroll.model import Planilla

    policy = db.session.get(VacationPolicy, policy_id)
    if not policy:
        flash(_("Política no encontrada."), "warning")
        return redirect(url_for("vacation.policy_index"))

    form = VacationPolicyForm(obj=policy)

    # Populate planilla choices
    planillas = (
        db.session.execute(
            db.select(Planilla)
            .options(selectinload(Planilla.empresa))
            .filter(Planilla.activo.is_(True))
            .order_by(Planilla.nombre)
        )
        .scalars()
        .all()
    )
    form.planilla_id.choices = [("", _("-- Seleccionar Planilla --"))] + [
        (p.id, f"{p.nombre} ({p.empresa.razon_social if p.empresa else 'N/A'})") for p in planillas
    ]

    # Populate empresa choices
    empresas = (
        db.session.execute(db.select(Empresa).filter(Empresa.activo.is_(True)).order_by(Empresa.razon_social))
        .scalars()
        .all()
    )
    form.empresa_id.choices = [("", _("-- Seleccionar Empresa --"))] + [(e.id, e.razon_social) for e in empresas]

    if form.validate_on_submit():
        _normalize_policy_optional_defaults(form)
        form.populate_obj(policy)
        policy.modificado_por = current_user.usuario

        try:
            db.session.commit()
            flash(_("Política actualizada exitosamente."), "success")
            return redirect(url_for("vacation.policy_index"))
        except Exception as e:
            db.session.rollback()
            flash(_("Error al actualizar la política: {}").format(str(e)), "danger")

    return render_template(
        "modules/vacation/policy_form.html",
        form=form,
        policy=policy,
        titulo=_("Editar Política de Vacaciones"),
    )


@vacation_bp.route("/policies/<string:policy_id>")
@require_read_access()
def policy_detail(policy_id):
    """View vacation policy details."""
    policy = db.session.get(VacationPolicy, policy_id)
    if not policy:
        flash(_("Política no encontrada."), "warning")
        return redirect(url_for("vacation.policy_index"))

    # Get statistics
    total_accounts = (
        db.session.execute(db.select(count(VacationAccount.id)).filter(VacationAccount.policy_id == policy_id)).scalar()
        or 0
    )

    return render_template(
        "modules/vacation/policy_detail.html",
        policy=policy,
        total_accounts=total_accounts,
    )


# ============================================================================
# Vacation Account Management
# ============================================================================


@vacation_bp.route("/accounts")
@require_read_access()
def account_index():
    """List all vacation accounts."""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    # Join with Empleado to get employee details
    query = (
        db.select(VacationAccount)
        .join(VacationAccount.empleado)
        .order_by(Empleado.primer_apellido, Empleado.primer_nombre)
    )
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    accounts = pagination.items

    return render_template(
        "modules/vacation/account_index.html",
        accounts=accounts,
        pagination=pagination,
    )


@vacation_bp.route("/accounts/<string:account_id>")
@require_read_access()
def account_detail(account_id):
    """View vacation account details and history."""
    account = db.session.get(VacationAccount, account_id)
    if not account:
        flash(_("Cuenta no encontrada."), "warning")
        return redirect(url_for("vacation.account_index"))

    # Get ledger history
    ledger_entries = (
        db.session.execute(
            db.select(VacationLedger)
            .filter(VacationLedger.account_id == account_id)
            .order_by(VacationLedger.fecha.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )

    # Get pending leave requests
    pending_requests = (
        db.session.execute(
            db.select(VacationNovelty)
            .filter(VacationNovelty.account_id == account_id, VacationNovelty.estado == "pending")
            .order_by(VacationNovelty.start_date)
        )
        .scalars()
        .all()
    )

    return render_template(
        "modules/vacation/account_detail.html",
        account=account,
        ledger_entries=ledger_entries,
        pending_requests=pending_requests,
    )


@vacation_bp.route("/accounts/new", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def account_new():
    """Create a new vacation account for an employee."""
    from coati_payroll.forms import VacationAccountForm

    form = VacationAccountForm()

    if form.validate_on_submit():
        account = VacationAccount()
        form.populate_obj(account)
        account.creado_por = current_user.usuario

        db.session.add(account)
        try:
            db.session.commit()
            flash(_("Cuenta de vacaciones creada exitosamente."), "success")
            return redirect(url_for("vacation.account_detail", account_id=account.id))
        except Exception as e:
            db.session.rollback()
            flash(_("Error al crear la cuenta: {}").format(str(e)), "danger")

    return render_template(
        "modules/vacation/account_form.html",
        form=form,
        titulo=_("Nueva Cuenta de Vacaciones"),
    )


# ============================================================================
# Vacation Leave Request Management
# ============================================================================


@vacation_bp.route("/leave-requests")
@require_read_access()
def leave_request_index():
    """List vacation leave requests."""
    page = request.args.get("page", 1, type=int)
    per_page = 20
    estado = request.args.get("estado", None)

    query = db.select(VacationNovelty).join(VacationNovelty.empleado)

    if estado:
        query = query.filter(VacationNovelty.estado == estado)

    query = query.order_by(VacationNovelty.start_date.desc())
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    leave_requests = pagination.items

    return render_template(
        "modules/vacation/leave_request_index.html",
        leave_requests=leave_requests,
        pagination=pagination,
        estado=estado,
    )


@vacation_bp.route("/leave-requests/new", methods=["GET", "POST"])
@require_write_access()
def leave_request_new():
    """Create a new vacation leave request."""
    from coati_payroll.forms import VacationLeaveRequestForm

    form = VacationLeaveRequestForm()
    # Asignar choices de empleados activos antes de validar
    empleados = (
        db.session.execute(
            db.select(Empleado)
            .filter(Empleado.activo.is_(True))
            .order_by(Empleado.primer_apellido, Empleado.primer_nombre)
        )
        .scalars()
        .all()
    )
    form.empleado_id.choices = [("", _("-- Seleccionar Empleado --"))] + [
        (e.id, f"{e.codigo_empleado} - {e.primer_nombre} {e.primer_apellido}") for e in empleados
    ]

    if form.validate_on_submit():
        # Validate that employee has a vacation account
        account = db.session.execute(
            db.select(VacationAccount).filter(
                VacationAccount.empleado_id == form.empleado_id.data, VacationAccount.activo.is_(True)
            )
        ).scalar_one_or_none()

        if not account:
            flash(_("El empleado no tiene una cuenta de vacaciones activa."), "danger")
            return render_template(
                "modules/vacation/leave_request_form.html",
                form=form,
                titulo=_("Nueva Solicitud de Vacaciones"),
            )

        # Check balance
        if account.current_balance < form.units.data:
            if not account.policy.allow_negative:
                flash(_("Saldo insuficiente para la solicitud."), "danger")
                return render_template(
                    "modules/vacation/leave_request_form.html",
                    form=form,
                    titulo=_("Nueva Solicitud de Vacaciones"),
                )

        # Create leave request
        leave_request = VacationNovelty()
        form.populate_obj(leave_request)
        leave_request.account_id = account.id
        leave_request.creado_por = current_user.usuario

        db.session.add(leave_request)
        try:
            db.session.commit()
            flash(_("Solicitud de vacaciones creada exitosamente."), "success")
            return redirect(url_for("vacation.leave_request_detail", request_id=leave_request.id))
        except Exception as e:
            db.session.rollback()
            flash(_("Error al crear la solicitud: {}").format(str(e)), "danger")

    return render_template(
        "modules/vacation/leave_request_form.html",
        form=form,
        titulo=_("Nueva Solicitud de Vacaciones"),
    )


@vacation_bp.route("/leave-requests/<string:request_id>")
@require_read_access()
def leave_request_detail(request_id):
    """View vacation leave request details."""
    leave_request = db.session.get(VacationNovelty, request_id)
    if not leave_request:
        flash(_("Solicitud no encontrada."), "warning")
        return redirect(url_for("vacation.leave_request_index"))

    return render_template(
        "modules/vacation/leave_request_detail.html",
        leave_request=leave_request,
    )


@vacation_bp.route("/leave-requests/<string:request_id>/approve", methods=["POST"])
@require_role(TipoUsuario.ADMIN)
def leave_request_approve(request_id):
    """Approve a vacation leave request."""
    leave_request = db.session.get(VacationNovelty, request_id)
    if not leave_request:
        flash(_("Solicitud no encontrada."), "warning")
        return redirect(url_for("vacation.leave_request_index"))

    if leave_request.estado != VacacionEstado.PENDIENTE:
        flash(_("Solo se pueden aprobar solicitudes pendientes."), "warning")
        return redirect(url_for("vacation.leave_request_detail", request_id=request_id))

    # Get the vacation account
    account = leave_request.account
    if not account:
        flash(_("Cuenta de vacaciones no encontrada."), "danger")
        return redirect(url_for("vacation.leave_request_detail", request_id=request_id))

    # Check if there's enough balance (validation only; discount happens via payroll execution)
    if account.current_balance < leave_request.units and not account.policy.allow_negative:
        flash(
            _("Saldo insuficiente. Disponible: {}, Solicitado: {}").format(
                account.current_balance, leave_request.units
            ),
            "danger",
        )
        return redirect(url_for("vacation.leave_request_detail", request_id=request_id))

    # Update request status; accounting/balance impact is deferred to payroll novelties execution
    leave_request.estado = VacacionEstado.APROBADO
    leave_request.fecha_aprobacion = date.today()
    leave_request.aprobado_por = current_user.usuario
    leave_request.modificado_por = current_user.usuario

    try:
        db.session.commit()
        flash(_("Solicitud aprobada exitosamente."), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error al aprobar la solicitud: {}").format(str(e)), "danger")

    return redirect(url_for("vacation.leave_request_detail", request_id=request_id))


@vacation_bp.route("/leave-requests/<string:request_id>/reject", methods=["POST"])
@require_role(TipoUsuario.ADMIN)
def leave_request_reject(request_id):
    """Reject a vacation leave request."""
    leave_request = db.session.get(VacationNovelty, request_id)
    if not leave_request:
        flash(_("Solicitud no encontrada."), "warning")
        return redirect(url_for("vacation.leave_request_index"))

    if leave_request.estado != VacacionEstado.PENDIENTE:
        flash(_("Solo se pueden rechazar solicitudes pendientes."), "warning")
        return redirect(url_for("vacation.leave_request_detail", request_id=request_id))

    # Get rejection reason from form
    motivo_rechazo = request.form.get("motivo_rechazo", "")

    # Update request status
    leave_request.estado = VacacionEstado.RECHAZADO
    leave_request.motivo_rechazo = motivo_rechazo
    leave_request.modificado_por = current_user.usuario

    try:
        db.session.commit()
        flash(_("Solicitud rechazada."), "info")
    except Exception as e:
        db.session.rollback()
        flash(_("Error al rechazar la solicitud: {}").format(str(e)), "danger")

    return redirect(url_for("vacation.leave_request_detail", request_id=request_id))


# ============================================================================
# Register Vacation Taken (Direct Registration with Novelty Creation)
# ============================================================================


@vacation_bp.route("/register-taken", methods=["GET", "POST"])
@require_write_access()
def register_vacation_taken():
    """Register vacation days taken by an employee (creates vacation record + novelty).

    This is an alternative method to register novelties from the vacation module.
    The novelty is created using the existing infrastructure (NominaNovedad) and MUST
    be associated with either a Percepcion or Deduccion for payroll calculations.

    Workflow:
    1. Creates a VacationNovelty record (vacation tracking)
    2. Creates a linked NominaNovedad record (payroll integration)
    3. The NominaNovedad is associated with the selected Percepcion/Deduccion
    4. Marks vacation as approved and deducts from balance
    5. When payroll is calculated, the novelty will be processed normally
    """
    from coati_payroll.forms import VacationTakenForm
    from coati_payroll.model import NominaNovedad, Percepcion, Deduccion
    from coati_payroll.vistas.planilla.services.novedad_service import NovedadService

    form = VacationTakenForm()

    # Populate employee choices
    empleados = (
        db.session.execute(
            db.select(Empleado)
            .filter(Empleado.activo.is_(True))
            .order_by(Empleado.primer_apellido, Empleado.primer_nombre)
        )
        .scalars()
        .all()
    )
    form.empleado_id.choices = [("", _("-- Seleccionar Empleado --"))] + [
        (e.id, f"{e.codigo_empleado} - {e.primer_nombre} {e.primer_apellido}") for e in empleados
    ]

    # Populate percepcion choices
    percepciones = (
        db.session.execute(db.select(Percepcion).filter(Percepcion.activo.is_(True)).order_by(Percepcion.codigo))
        .scalars()
        .all()
    )
    form.percepcion_id.choices = [("", _("-- Seleccionar Percepción --"))] + [
        (p.id, f"{p.codigo} - {p.nombre}") for p in percepciones
    ]

    # Populate deduccion choices
    deducciones = (
        db.session.execute(db.select(Deduccion).filter(Deduccion.activo.is_(True)).order_by(Deduccion.codigo))
        .scalars()
        .all()
    )
    form.deduccion_id.choices = [("", _("-- Seleccionar Deducción --"))] + [
        (d.id, f"{d.codigo} - {d.nombre}") for d in deducciones
    ]

    if form.validate_on_submit():
        empleado_id = form.empleado_id.data
        empleado = db.session.get(Empleado, empleado_id)

        if not empleado:
            flash(_(MSG_EMPLEADO_NO_ENCONTRADO), "danger")
            return render_template(
                "modules/vacation/register_taken_form.html",
                form=form,
                titulo=_("Registrar Vacaciones Descansadas"),
            )

        # Validate tipo_concepto and associated percepcion/deduccion
        tipo_concepto = form.tipo_concepto.data
        percepcion_id = form.percepcion_id.data if tipo_concepto == "income" else None
        deduccion_id = form.deduccion_id.data if tipo_concepto == "deduction" else None

        if tipo_concepto == "income" and not percepcion_id:
            flash(_("Debe seleccionar una percepción cuando el tipo de concepto es percepción."), "danger")
            return render_template(
                "modules/vacation/register_taken_form.html",
                form=form,
                titulo=_("Registrar Vacaciones Descansadas"),
            )

        if tipo_concepto == "deduction" and not deduccion_id:
            flash(_("Debe seleccionar una deducción cuando el tipo de concepto es deducción."), "danger")
            return render_template(
                "modules/vacation/register_taken_form.html",
                form=form,
                titulo=_("Registrar Vacaciones Descansadas"),
            )

        # Get the concepto for codigo
        if tipo_concepto == "income":
            concepto = db.session.get(Percepcion, percepcion_id)
            codigo_concepto = concepto.codigo if concepto else "VACATION"
        else:
            concepto = db.session.get(Deduccion, deduccion_id)
            codigo_concepto = concepto.codigo if concepto else "ABSENCE"

        # Validate that employee has a vacation account
        account = db.session.execute(
            db.select(VacationAccount).filter(
                VacationAccount.empleado_id == empleado_id, VacationAccount.activo.is_(True)
            )
        ).scalar_one_or_none()

        if not account:
            flash(_("El empleado no tiene una cuenta de vacaciones activa. Cree una cuenta primero."), "danger")
            return render_template(
                "modules/vacation/register_taken_form.html",
                form=form,
                titulo=_("Registrar Vacaciones Descansadas"),
            )

        # Check balance (considering dias_descontados, not calendar days)
        dias_descontados = form.dias_descontados.data
        if account.current_balance < dias_descontados:
            if not account.policy.allow_negative:
                flash(
                    _(f"Saldo insuficiente. Balance actual: {account.current_balance}, Solicitado: {dias_descontados}"),
                    "danger",
                )
                return render_template(
                    "modules/vacation/register_taken_form.html",
                    form=form,
                    titulo=_("Registrar Vacaciones Descansadas"),
                )

        # Create VacationNovelty (leave record)
        vacation_novelty = VacationNovelty(
            empleado_id=empleado_id,
            account_id=account.id,
            start_date=form.fecha_inicio.data,
            end_date=form.fecha_fin.data,
            units=dias_descontados,  # CRITICAL: Use dias_descontados, not calendar days
            estado=VacacionEstado.APROBADO,  # Directly approved
            fecha_aprobacion=date.today(),
            aprobado_por=current_user.usuario,
            observaciones=form.observaciones.data,
            creado_por=current_user.usuario,
        )

        db.session.add(vacation_novelty)
        db.session.flush()  # Get ID

        # IMPORTANT: do NOT write VacationLedger here.
        # Vacation discounts must be executed via payroll (Nomina) processing only.

        # Create associated NominaNovedad using existing infrastructure
        # This ensures the novelty is properly processed during payroll calculation
        es_inasistencia, descontar_pago_inasistencia = NovedadService.resolve_absence_flags(
            percepcion_id=percepcion_id,
            deduccion_id=deduccion_id,
        )
        nomina_novedad = NominaNovedad(
            nomina_id=None,  # Will be linked to the employee's next nomina when calculated
            empleado_id=empleado_id,
            tipo_valor="dias",  # Or "horas" based on policy unit_type
            codigo_concepto=codigo_concepto,
            valor_cantidad=dias_descontados,
            fecha_novedad=form.fecha_inicio.data,
            percepcion_id=percepcion_id,  # Required association
            deduccion_id=deduccion_id,  # Required association
            es_inasistencia=es_inasistencia,
            descontar_pago_inasistencia=descontar_pago_inasistencia,
            es_descanso_vacaciones=True,
            vacation_novelty_id=vacation_novelty.id,
            fecha_inicio_descanso=form.fecha_inicio.data,
            fecha_fin_descanso=form.fecha_fin.data,
            estado=VacacionEstado.PENDIENTE,  # Will be processed when nomina is calculated
            creado_por=current_user.usuario,
        )

        vacation_novelty.estado = VacacionEstado.APLICADO

        db.session.add(nomina_novedad)

        try:
            db.session.commit()
            flash(_(f"Vacaciones registradas exitosamente. {dias_descontados} días descontados del saldo."), "success")
            return redirect(url_for("vacation.account_detail", account_id=account.id))
        except Exception as e:
            db.session.rollback()
            flash(_("Error al registrar vacaciones: {}").format(str(e)), "danger")

    return render_template(
        "modules/vacation/register_taken_form.html",
        form=form,
        titulo=_("Registrar Vacaciones Descansadas"),
    )


# ============================================================================
# Vacation Dashboard
# ============================================================================


@vacation_bp.route("/")
@login_required
def dashboard():
    """Vacation management dashboard."""
    # Statistics
    total_policies = (
        db.session.execute(db.select(count(VacationPolicy.id)).filter(VacationPolicy.activo.is_(True))).scalar() or 0
    )

    total_accounts = (
        db.session.execute(db.select(count(VacationAccount.id)).filter(VacationAccount.activo.is_(True))).scalar() or 0
    )

    pending_requests = (
        db.session.execute(
            db.select(count(VacationNovelty.id)).filter(VacationNovelty.estado == VacacionEstado.PENDIENTE)
        ).scalar()
        or 0
    )

    # Recent activity
    recent_requests = (
        db.session.execute(
            db.select(VacationNovelty)
            .join(VacationNovelty.empleado)
            .order_by(VacationNovelty.timestamp.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )

    return render_template(
        "modules/vacation/dashboard.html",
        total_policies=total_policies,
        total_accounts=total_accounts,
        pending_requests=pending_requests,
        recent_requests=recent_requests,
    )


# ============================================================================
# API Endpoints for AJAX
# ============================================================================


@vacation_bp.route("/api/employee/<string:employee_id>/balance")
@login_required
def api_employee_balance(employee_id):
    """Get employee vacation balance (AJAX endpoint)."""
    account = db.session.execute(
        db.select(VacationAccount).filter(VacationAccount.empleado_id == employee_id, VacationAccount.activo.is_(True))
    ).scalar_one_or_none()

    if not account:
        return jsonify({"error": "No vacation account found"}), 404

    return jsonify(
        {
            "balance": float(account.current_balance),
            "unit_type": account.policy.unit_type,
            "policy_name": account.policy.nombre,
        }
    )


# ============================================================================
# Initial Balance Loading (for System Implementation)
# ============================================================================


@vacation_bp.route("/initial-balance", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def initial_balance_form():
    """Load initial vacation balance for a single employee.

    Used during system implementation to set the initial accumulated vacation
    balance for employees who already have vacation time earned before the
    system goes live.

    Creates an ADJUSTMENT ledger entry with the initial balance and sets
    the account's current_balance to match.
    """
    from coati_payroll.forms import VacationInitialBalanceForm

    form = VacationInitialBalanceForm()

    # Populate employee choices
    empleados = (
        db.session.execute(
            db.select(Empleado)
            .filter(Empleado.activo.is_(True))
            .order_by(Empleado.primer_apellido, Empleado.primer_nombre)
        )
        .scalars()
        .all()
    )
    form.empleado_id.choices = [("", _("-- Seleccionar Empleado --"))] + [
        (e.id, f"{e.codigo_empleado} - {e.primer_nombre} {e.primer_apellido}") for e in empleados
    ]

    if form.validate_on_submit():
        empleado_id = form.empleado_id.data
        saldo_inicial = form.saldo_inicial.data
        fecha_corte = form.fecha_corte.data
        observaciones = form.observaciones.data or "Carga de saldo inicial al implementar el sistema"

        # Get employee and their vacation account
        empleado = db.session.get(Empleado, empleado_id)
        if not empleado:
            flash(_(MSG_EMPLEADO_NO_ENCONTRADO), "danger")
            return redirect(url_for("vacation.initial_balance_form"))

        # Check if employee has an active vacation account
        account = db.session.execute(
            db.select(VacationAccount).filter(
                VacationAccount.empleado_id == empleado_id, VacationAccount.activo.is_(True)
            )
        ).scalar_one_or_none()

        if not account:
            flash(
                _(
                    "El empleado {} no tiene una cuenta de vacaciones activa. " "Por favor, cree una cuenta primero."
                ).format(empleado.codigo_empleado),
                "warning",
            )
            return redirect(url_for("vacation.account_index"))

        # Check if there are already ledger entries for this account
        existing_entries = (
            db.session.execute(
                db.select(count(VacationLedger.id)).filter(VacationLedger.account_id == account.id)
            ).scalar()
            or 0
        )

        if existing_entries > 0:
            flash(
                _(
                    "La cuenta de vacaciones del empleado {} ya tiene movimientos registrados. "
                    "No se puede cargar un saldo inicial para cuentas con historial."
                ).format(empleado.codigo_empleado),
                "warning",
            )
            return redirect(url_for("vacation.account_detail", account_id=account.id))

        # Create ledger entry for initial balance
        ledger_entry = VacationLedger(
            account_id=account.id,
            empleado_id=empleado_id,
            fecha=fecha_corte,
            entry_type=VacationLedgerType.ADJUSTMENT,
            quantity=saldo_inicial,
            source="initial_balance",
            reference_type="manual",
            observaciones=observaciones,
            creado_por=current_user.usuario,
        )

        # Set account balance to initial balance
        account.current_balance = saldo_inicial
        account.last_accrual_date = fecha_corte
        account.modificado_por = current_user.usuario

        ledger_entry.balance_after = account.current_balance

        db.session.add(ledger_entry)

        try:
            db.session.commit()
            flash(
                _("Saldo inicial de {} {} cargado exitosamente para {}.").format(
                    saldo_inicial, account.policy.unit_type, empleado.codigo_empleado
                ),
                "success",
            )
            return redirect(url_for("vacation.account_detail", account_id=account.id))
        except Exception as e:
            db.session.rollback()
            flash(_("Error al cargar saldo inicial: {}").format(str(e)), "danger")

    return render_template("modules/vacation/initial_balance_form.html", form=form)


@vacation_bp.route("/initial-balance/bulk", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def initial_balance_bulk():
    """Bulk load initial vacation balances from Excel.

    Used during system implementation for companies with many employees.
    Allows uploading an Excel file with initial vacation balances for multiple
    employees at once.

    Expected Excel format (without headers, data starts on row 1):
    - Column A: Código de Empleado
    - Column B: Saldo Inicial (días/horas)
    - Column C: Fecha de Corte (DD/MM/YYYY)
    - Column D: Observaciones (opcional)
    """
    if request.method == "POST":
        # Check if file was uploaded
        if "file" not in request.files:
            flash(_("No se seleccionó ningún archivo."), "warning")
            return redirect(url_for("vacation.initial_balance_bulk"))

        file = request.files["file"]

        if file.filename == "":
            flash(_("No se seleccionó ningún archivo."), "warning")
            return redirect(url_for("vacation.initial_balance_bulk"))

        if not file.filename.endswith((".xlsx", ".xls")):
            flash(_("Por favor, suba un archivo Excel (.xlsx o .xls)."), "warning")
            return redirect(url_for("vacation.initial_balance_bulk"))

        try:
            import openpyxl
            from datetime import datetime as dt

            # Load Excel file
            workbook = openpyxl.load_workbook(file, data_only=True)
            sheet = workbook.active

            success_count = 0
            error_count = 0
            errors = []

            # Process each row (data starts at row 1, no headers expected)
            for row_num, row in enumerate(sheet.iter_rows(min_row=1, values_only=True), start=1):
                codigo_empleado = row[0]
                saldo_inicial = row[1]
                fecha_corte = row[2]
                observaciones = row[3] if len(row) > 3 else "Carga masiva de saldo inicial"

                # Validate required fields
                if not codigo_empleado or saldo_inicial is None or not fecha_corte:
                    errors.append(f"Fila {row_num}: Faltan campos requeridos")
                    error_count += 1
                    continue

                # Convert fecha_corte if it's a datetime object
                if isinstance(fecha_corte, dt):
                    fecha_corte = fecha_corte.date()
                elif isinstance(fecha_corte, str):
                    try:
                        fecha_corte = dt.strptime(fecha_corte, "%d/%m/%Y").date()
                    except ValueError:
                        errors.append(f"Fila {row_num}: Formato de fecha inválido (use DD/MM/YYYY)")
                        error_count += 1
                        continue

                # Find employee
                empleado = db.session.execute(
                    db.select(Empleado).filter(Empleado.codigo_empleado == codigo_empleado, Empleado.activo.is_(True))
                ).scalar_one_or_none()

                if not empleado:
                    errors.append(f"Fila {row_num}: Empleado {codigo_empleado} no encontrado")
                    error_count += 1
                    continue

                # Check if employee has an active vacation account
                account = db.session.execute(
                    db.select(VacationAccount).filter(
                        VacationAccount.empleado_id == empleado.id, VacationAccount.activo.is_(True)
                    )
                ).scalar_one_or_none()

                if not account:
                    errors.append(f"Fila {row_num}: Empleado {codigo_empleado} no tiene cuenta de vacaciones activa")
                    error_count += 1
                    continue

                # Check if account already has ledger entries
                existing_entries = (
                    db.session.execute(
                        db.select(count(VacationLedger.id)).filter(VacationLedger.account_id == account.id)
                    ).scalar()
                    or 0
                )

                if existing_entries > 0:
                    errors.append(f"Fila {row_num}: Empleado {codigo_empleado} ya tiene movimientos en su cuenta")
                    error_count += 1
                    continue

                try:
                    # Create ledger entry for initial balance
                    ledger_entry = VacationLedger(
                        account_id=account.id,
                        empleado_id=empleado.id,
                        fecha=fecha_corte,
                        entry_type=VacationLedgerType.ADJUSTMENT,
                        quantity=Decimal(str(saldo_inicial)),
                        source="initial_balance_bulk",
                        reference_type="excel_import",
                        observaciones=str(observaciones) if observaciones else "Carga masiva de saldo inicial",
                        creado_por=current_user.usuario,
                    )

                    # Set account balance to initial balance
                    account.current_balance = Decimal(str(saldo_inicial))
                    account.last_accrual_date = fecha_corte
                    account.modificado_por = current_user.usuario

                    ledger_entry.balance_after = account.current_balance

                    db.session.add(ledger_entry)
                    success_count += 1

                except Exception as e:
                    errors.append(f"Fila {row_num}: Error al procesar {codigo_empleado}: {str(e)}")
                    error_count += 1
                    # Don't rollback here, continue adding successful entries
                    continue

            # Commit all changes
            try:
                db.session.commit()
                flash(
                    _("Carga completada: {} registros exitosos, {} errores.").format(success_count, error_count),
                    "success" if error_count == 0 else "warning",
                )

                if errors:
                    error_details = "<br>".join(errors[:10])  # Show first 10 errors
                    if len(errors) > 10:
                        error_details += f"<br>...y {len(errors) - 10} errores más"
                    flash(error_details, "warning")

            except Exception as e:
                db.session.rollback()
                flash(_("Error al guardar los cambios: {}").format(str(e)), "danger")

        except ImportError:
            flash(_("Error: La librería openpyxl no está instalada. Contacte al administrador."), "danger")
        except Exception as e:
            flash(_("Error al procesar el archivo Excel: {}").format(str(e)), "danger")

        return redirect(url_for("vacation.initial_balance_bulk"))

    return render_template("modules/vacation/initial_balance_bulk.html")
