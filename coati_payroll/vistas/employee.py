# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Employee CRUD routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import cast

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import false, true

from coati_payroll.forms import EmployeeForm, SalaryChangeForm
from coati_payroll.i18n import _
from coati_payroll.model import CampoPersonalizado, Empleado, HistorialSalario, Moneda, db, utc_now
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.tenant import (
    active_empresa_id,
    accessible_empresas,
    require_company_access,
    scope_company_query,
    scoped_or_404,
)
from coati_payroll.vistas.constants import PER_PAGE

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")
EMPLOYEE_INDEX_ENDPOINT = "employee.index"
SALARY_CHANGES_INDEX_ENDPOINT = "employee.salary_changes_index"


def get_currency_choices():
    """Get list of currencies for select fields."""
    currencies = db.session.execute(db.select(Moneda).filter_by(activo=True).order_by(Moneda.codigo)).scalars().all()
    return [("", _("Seleccionar..."))] + [(c.id, f"{c.codigo} - {c.nombre}") for c in currencies]


def get_empresa_choices():
    """Get list of companies for select fields."""

    empresas = accessible_empresas()
    selected = active_empresa_id()
    if selected:
        empresas = [empresa for empresa in empresas if empresa.id == selected]
    return [("", _("Seleccionar..."))] + [(e.id, f"{e.codigo} - {e.razon_social}") for e in empresas]


def get_custom_fields():
    """Get all active custom fields ordered by 'orden'."""
    return (
        db.session.execute(db.select(CampoPersonalizado).filter_by(activo=True).order_by(CampoPersonalizado.orden))
        .scalars()
        .all()
    )


def process_custom_fields_from_request(custom_fields):
    """Process custom field values from form request and return as dict.

    Args:
        custom_fields: List of CampoPersonalizado objects

    Returns:
        Dictionary with custom field names as keys and their converted values
    """

    datos_adicionales = {}
    for field in custom_fields:
        field_name = f"custom_{field.nombre_campo}"
        raw_value = request.form.get(field_name, "")
        datos_adicionales[field.nombre_campo] = _convert_custom_field_value(
            field.tipo_dato, raw_value, field_name in request.form
        )
    return datos_adicionales


def _convert_custom_field_value(tipo_dato: str, raw_value: str, checkbox_checked: bool):
    """Convert one custom field value to its JSON-safe representation."""
    normalized_type = {
        "texto": "text",
        "entero": "integer",
        "decimal": "decimal",
        "booleano": "boolean",
    }.get(tipo_dato, tipo_dato)
    converter = _CUSTOM_FIELD_CONVERTERS.get(normalized_type, _convert_default_field)
    return converter(raw_value, checkbox_checked)


def _convert_text_field(raw_value: str, _checkbox_checked: bool):
    stripped = raw_value.strip() if raw_value else ""
    return stripped or None


def _convert_integer_field(raw_value: str, _checkbox_checked: bool):
    try:
        return int(raw_value) if raw_value else None
    except ValueError:
        return None


def _convert_decimal_field(raw_value: str, _checkbox_checked: bool):
    try:
        clean_value = raw_value.strip() if raw_value else ""
        return format(Decimal(clean_value), "f") if clean_value else None
    except (ValueError, InvalidOperation):
        return None


def _convert_boolean_field(_raw_value: str, checkbox_checked: bool):
    return checkbox_checked


def _convert_default_field(raw_value: str, _checkbox_checked: bool):
    return raw_value or None


_CUSTOM_FIELD_CONVERTERS = {
    "text": _convert_text_field,
    "integer": _convert_integer_field,
    "decimal": _convert_decimal_field,
    "boolean": _convert_boolean_field,
}


def process_last_three_salaries(form):
    """Process last three salary fields from form and return as dict.

    Stores salaries as strings to preserve Decimal precision in JSON.

    Args:
        form: EmployeeForm instance with salary fields

    Returns:
        Dictionary with last three salaries as strings, or None if empty
    """
    ultimos_salarios = {}
    if form.ultimo_salario_1.data:
        ultimos_salarios["salario_1"] = str(form.ultimo_salario_1.data)
    if form.ultimo_salario_2.data:
        ultimos_salarios["salario_2"] = str(form.ultimo_salario_2.data)
    if form.ultimo_salario_3.data:
        ultimos_salarios["salario_3"] = str(form.ultimo_salario_3.data)
    return ultimos_salarios if ultimos_salarios else None


def _update_employee_from_form(employee, form, custom_fields, *, is_new: bool) -> Decimal:
    """Apply form values to an employee and return the previous base salary."""
    salario_actual = employee.salario_base or Decimal("0.00")
    if form.codigo_empleado.data and form.codigo_empleado.data.strip():
        employee.codigo_empleado = form.codigo_empleado.data.strip()

    fields = (
        "primer_nombre",
        "segundo_nombre",
        "primer_apellido",
        "segundo_apellido",
        "nacionalidad",
        "identificacion_personal",
        "fecha_nacimiento",
        "fecha_alta",
        "fecha_baja",
        "activo",
        "cargo",
        "area",
        "centro_costos",
        "correo",
        "telefono",
        "direccion",
        "banco",
        "numero_cuenta_bancaria",
    )
    optional_fields = (
        "genero",
        "tipo_identificacion",
        "id_seguridad_social",
        "id_fiscal",
        "tipo_sangre",
        "estado_civil",
        "tipo_contrato",
        "moneda_id",
        "empresa_id",
    )
    for field_name in fields:
        setattr(employee, field_name, getattr(form, field_name).data)
    for field_name in optional_fields:
        setattr(employee, field_name, getattr(form, field_name).data or None)

    if is_new:
        employee.salario_base = form.salario_base.data or Decimal("0.00")
    employee.salario_acumulado = form.salario_acumulado.data or Decimal("0.00")
    employee.impuesto_acumulado = form.impuesto_acumulado.data or Decimal("0.00")
    employee.ultimos_tres_salarios = process_last_three_salaries(form)
    employee.datos_adicionales = process_custom_fields_from_request(custom_fields)
    if is_new:
        employee.creado_por = current_user.usuario
    else:
        employee.modificado_por = current_user.usuario
    return salario_actual


@employee_bp.route("/", methods=["GET"])
@require_read_access()
def index():
    """List all employees with pagination and filters."""
    page = request.args.get("page", 1, type=int)

    # Get filter parameters
    buscar = request.args.get("buscar", type=str)
    estado = request.args.get("estado", type=str)
    area = request.args.get("area", type=str)
    cargo = request.args.get("cargo", type=str)

    # Build query with filters
    query = scope_company_query(db.select(Empleado), Empleado.empresa_id)

    if buscar:
        search_term = f"%{buscar}%"
        query = query.filter(
            db.or_(
                Empleado.primer_nombre.ilike(search_term),
                Empleado.segundo_nombre.ilike(search_term),
                Empleado.primer_apellido.ilike(search_term),
                Empleado.segundo_apellido.ilike(search_term),
                Empleado.codigo_empleado.ilike(search_term),
                Empleado.identificacion_personal.ilike(search_term),
            )
        )

    if estado == "activo":
        query = query.filter(Empleado.activo.is_(true()))
    elif estado == "inactivo":
        query = query.filter(Empleado.activo.is_(false()))

    if area:
        query = query.filter(Empleado.area.ilike(f"%{area}%"))

    if cargo:
        query = query.filter(Empleado.cargo.ilike(f"%{cargo}%"))

    query = query.order_by(Empleado.primer_apellido, Empleado.primer_nombre)

    pagination = db.paginate(
        query,
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )

    return render_template(
        "modules/employee/index.html",
        employees=pagination.items,
        pagination=pagination,
        buscar=buscar,
        estado=estado,
        area=area,
        cargo=cargo,
    )


@employee_bp.route("/new", methods=["GET", "POST"])
@require_write_access()
def new():
    """Create a new employee. Admin and HR can create employees."""
    form = EmployeeForm()
    form.moneda_id.choices = get_currency_choices()
    form.empresa_id.choices = get_empresa_choices()
    custom_fields = get_custom_fields()

    if form.validate_on_submit():
        require_company_access(form.empresa_id.data)
        employee = Empleado()
        _update_employee_from_form(employee, form, custom_fields, is_new=True)

        db.session.add(employee)
        db.session.commit()
        flash(_("Empleado creado exitosamente."), "success")
        return redirect(url_for(EMPLOYEE_INDEX_ENDPOINT))

    # Default date to today
    if not form.fecha_alta.data:
        form.fecha_alta.data = date.today()
    if not form.salario_base.data:
        form.salario_base.data = Decimal("0.00")

    return render_template(
        "modules/employee/form.html",
        form=form,
        title=_("Nuevo Empleado"),
        custom_fields=custom_fields,
        custom_values={},
    )


@employee_bp.route("/edit/<string:id_>", methods=["GET", "POST"])
@require_write_access()
def edit(id_: str):
    """Edit an existing employee. Admin and HR can edit employees."""
    employee = scoped_or_404(Empleado, id_, Empleado.empresa_id)

    form = EmployeeForm(obj=employee)
    form.moneda_id.choices = get_currency_choices()
    form.empresa_id.choices = get_empresa_choices()
    custom_fields = get_custom_fields()

    if form.validate_on_submit():
        salario_actual = employee.salario_base or Decimal("0.00")
        salario_propuesto = form.salario_base.data or Decimal("0.00")
        _update_employee_from_form(employee, form, custom_fields, is_new=False)

        db.session.commit()

        if salario_propuesto != salario_actual:
            flash(
                _("Los cambios salariales se gestionan únicamente desde el flujo de cambios salariales."),
                "warning",
            )
            return redirect(url_for("employee.salary_change_new", employee_id=employee.id))

        flash(_("Empleado actualizado exitosamente."), "success")
        return redirect(url_for(EMPLOYEE_INDEX_ENDPOINT))

    # Pre-populate last three salaries from employee data
    if request.method != "POST":
        ultimos_salarios = employee.ultimos_tres_salarios or {}
        if ultimos_salarios.get("salario_1"):
            form.ultimo_salario_1.data = Decimal(str(ultimos_salarios["salario_1"]))
        if ultimos_salarios.get("salario_2"):
            form.ultimo_salario_2.data = Decimal(str(ultimos_salarios["salario_2"]))
        if ultimos_salarios.get("salario_3"):
            form.ultimo_salario_3.data = Decimal(str(ultimos_salarios["salario_3"]))

    # Get existing custom field values
    custom_values = employee.datos_adicionales or {}

    return render_template(
        "modules/employee/form.html",
        form=form,
        title=_("Editar Empleado"),
        employee=employee,
        custom_fields=custom_fields,
        custom_values=custom_values,
    )


@employee_bp.route("/delete/<string:id_>", methods=["POST"])
@require_write_access()
def delete(id_: str):
    """Delete an employee. Admin and HR can delete employees."""
    employee = scoped_or_404(Empleado, id_, Empleado.empresa_id)

    db.session.delete(employee)
    db.session.commit()
    flash(_("Empleado eliminado exitosamente."), "success")
    return redirect(url_for(EMPLOYEE_INDEX_ENDPOINT))


def _requires_different_approver(employee: Empleado) -> bool:
    """Return True when company size suggests four-eyes approval."""
    if not employee.empresa_id:
        return False

    company_employee_count = db.session.scalar(
        db.select(db.func.count(Empleado.id)).filter(Empleado.empresa_id == employee.empresa_id)
    )
    return (company_employee_count or 0) >= 50


@employee_bp.route("/salary-changes", methods=["GET"])
@require_read_access()
def salary_changes_index():
    """List salary changes with filters for auditability."""
    page = request.args.get("page", 1, type=int)
    empleado_id = request.args.get("empleado_id", type=str)
    estado = request.args.get("estado", type=str)

    query = scope_company_query(
        db.select(HistorialSalario).join(Empleado, HistorialSalario.empleado_id == Empleado.id),
        Empleado.empresa_id,
    )

    if empleado_id:
        query = query.filter(HistorialSalario.empleado_id == empleado_id)
    if estado:
        query = query.filter(HistorialSalario.estado == estado)

    query = query.order_by(HistorialSalario.fecha_efectiva.desc(), HistorialSalario.timestamp.desc())

    pagination = db.paginate(query, page=page, per_page=PER_PAGE, error_out=False)

    employee_choices = (
        db.session.execute(
            scope_company_query(db.select(Empleado), Empleado.empresa_id).order_by(
                Empleado.primer_apellido, Empleado.primer_nombre
            )
        )
        .scalars()
        .all()
    )

    return render_template(
        "modules/employee/salary_changes_index.html",
        salary_changes=pagination.items,
        pagination=pagination,
        employee_choices=employee_choices,
        empleado_id=empleado_id,
        estado=estado,
    )


@employee_bp.route("/salary-changes/new/<string:employee_id>", methods=["GET", "POST"])
@require_write_access()
def salary_change_new(employee_id: str):
    """Create salary change in draft status."""
    employee = scoped_or_404(Empleado, employee_id, Empleado.empresa_id)

    form = SalaryChangeForm()
    form.moneda_nueva_id.choices = get_currency_choices()
    if form.validate_on_submit():
        salary_change = HistorialSalario(
            empleado_id=employee.id,
            fecha_efectiva=form.fecha_efectiva.data,
            salario_anterior=employee.salario_base or Decimal("0.00"),
            moneda_anterior_id=employee.moneda_id,
            salario_nuevo=form.salario_nuevo.data or Decimal("0.00"),
            moneda_nueva_id=form.moneda_nueva_id.data or employee.moneda_id,
            motivo=form.motivo.data,
            estado="draft",
            creado_por=current_user.usuario,
        )
        db.session.add(salary_change)
        db.session.commit()
        flash(_("Cambio salarial guardado como borrador."), "success")
        return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))

    if not form.fecha_efectiva.data:
        form.fecha_efectiva.data = date.today()
    if not form.salario_nuevo.data:
        form.salario_nuevo.data = employee.salario_base
    if not form.moneda_nueva_id.data and employee.moneda_id:
        form.moneda_nueva_id.data = employee.moneda_id

    return render_template("modules/employee/salary_change_form.html", form=form, employee=employee)


@employee_bp.route("/salary-changes/<string:change_id>/approve", methods=["POST"])
@require_write_access()
def salary_change_approve(change_id: str):
    """Approve a draft salary change."""
    salary_change = db.session.get(HistorialSalario, change_id)
    if not salary_change:
        flash(_("Cambio salarial no encontrado."), "error")
        return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))
    require_company_access(salary_change.empleado.empresa_id if salary_change.empleado else None)

    if salary_change.estado != "draft":
        flash(_("Solo se pueden aprobar cambios en borrador."), "warning")
        return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))

    if salary_change.empleado is None:
        flash(_("Empleado no encontrado para este cambio salarial."), "error")
        return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))

    if (
        _requires_different_approver(cast(Empleado, salary_change.empleado))
        and salary_change.creado_por == current_user.usuario
    ):
        flash(_("Para empresas grandes, el aprobador debe ser distinto al creador."), "error")
        return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))

    salary_change.estado = "approved"
    salary_change.autorizado_por = current_user.usuario
    salary_change.aprobado_en = utc_now()
    db.session.commit()

    flash(_("Cambio salarial aprobado."), "success")
    return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))


@employee_bp.route("/salary-changes/<string:change_id>/apply", methods=["POST"])
@require_write_access()
def salary_change_apply(change_id: str):
    """Apply an approved salary change to employee record."""
    salary_change = db.session.get(HistorialSalario, change_id)
    if not salary_change:
        flash(_("Cambio salarial no encontrado."), "error")
        return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))
    require_company_access(salary_change.empleado.empresa_id if salary_change.empleado else None)

    if salary_change.estado != "approved":
        flash(_("Solo se pueden aplicar cambios aprobados."), "warning")
        return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))

    if salary_change.empleado is None:
        flash(_("Empleado no encontrado para este cambio salarial."), "error")
        return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))

    empleado = cast(Empleado, salary_change.empleado)
    empleado.salario_base = salary_change.salario_nuevo
    if salary_change.moneda_nueva_id:
        empleado.moneda_id = salary_change.moneda_nueva_id
    salary_change.aplicado_por = current_user.usuario
    salary_change.aplicado_en = utc_now()
    salary_change.estado = "applied"
    db.session.commit()

    flash(_("Cambio salarial aplicado exitosamente."), "success")
    return redirect(url_for(SALARY_CHANGES_INDEX_ENDPOINT))
