# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Employee CRUD routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import false, true

from coati_payroll.forms import EmployeeForm
from coati_payroll.i18n import _
from coati_payroll.model import CampoPersonalizado, Empleado, Moneda, db
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.vistas.constants import MSG_EMPLEADO_NO_ENCONTRADO, PER_PAGE

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")


def get_currency_choices():
    """Get list of currencies for select fields."""
    currencies = db.session.execute(db.select(Moneda).filter_by(activo=True).order_by(Moneda.codigo)).scalars().all()
    return [("", _("Seleccionar..."))] + [(c.id, f"{c.codigo} - {c.nombre}") for c in currencies]


def get_empresa_choices():
    """Get list of companies for select fields."""
    from coati_payroll.model import Empresa

    empresas = (
        db.session.execute(db.select(Empresa).filter_by(activo=True).order_by(Empresa.razon_social)).scalars().all()
    )
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

    def normalize_custom_field_type(tipo_dato: str) -> str:
        return {
            "texto": "text",
            "entero": "integer",
            "decimal": "decimal",
            "booleano": "boolean",
        }.get(tipo_dato, tipo_dato)

    datos_adicionales = {}
    for field in custom_fields:
        field_name = f"custom_{field.nombre_campo}"
        raw_value = request.form.get(field_name, "")
        tipo_dato = normalize_custom_field_type(field.tipo_dato)

        match tipo_dato:
            case "text":
                stripped = raw_value.strip() if raw_value else ""
                datos_adicionales[field.nombre_campo] = stripped or None
            case "integer":
                try:
                    datos_adicionales[field.nombre_campo] = int(raw_value) if raw_value else None
                except ValueError:
                    datos_adicionales[field.nombre_campo] = None
            case "decimal":
                try:
                    clean_value = raw_value.strip() if raw_value else ""
                    if clean_value:
                        decimal_value = Decimal(clean_value)
                        # Store exact text representation to avoid float precision loss in JSON.
                        datos_adicionales[field.nombre_campo] = format(decimal_value, "f")
                    else:
                        datos_adicionales[field.nombre_campo] = None
                except (ValueError, InvalidOperation):
                    datos_adicionales[field.nombre_campo] = None
            case "boolean":
                # Checkbox will send value only if checked
                datos_adicionales[field.nombre_campo] = field_name in request.form
            case _:
                # Unknown type, store as text
                datos_adicionales[field.nombre_campo] = raw_value or None
    return datos_adicionales


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
    query = db.select(Empleado)

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
        employee = Empleado()
        # Set codigo_empleado only if provided (otherwise default will be used)
        if form.codigo_empleado.data and form.codigo_empleado.data.strip():
            employee.codigo_empleado = form.codigo_empleado.data.strip()
        employee.primer_nombre = form.primer_nombre.data
        employee.segundo_nombre = form.segundo_nombre.data
        employee.primer_apellido = form.primer_apellido.data
        employee.segundo_apellido = form.segundo_apellido.data
        employee.genero = form.genero.data or None
        employee.nacionalidad = form.nacionalidad.data
        employee.tipo_identificacion = form.tipo_identificacion.data or None
        employee.identificacion_personal = form.identificacion_personal.data
        employee.id_seguridad_social = form.id_seguridad_social.data or None
        employee.id_fiscal = form.id_fiscal.data or None
        employee.tipo_sangre = form.tipo_sangre.data or None
        employee.fecha_nacimiento = form.fecha_nacimiento.data
        employee.fecha_alta = form.fecha_alta.data
        employee.fecha_baja = form.fecha_baja.data
        employee.activo = form.activo.data
        employee.cargo = form.cargo.data
        employee.area = form.area.data
        employee.centro_costos = form.centro_costos.data
        employee.salario_base = form.salario_base.data or Decimal("0.00")
        employee.moneda_id = form.moneda_id.data or None
        employee.empresa_id = form.empresa_id.data or None
        employee.correo = form.correo.data
        employee.telefono = form.telefono.data
        employee.direccion = form.direccion.data
        employee.estado_civil = form.estado_civil.data or None
        employee.banco = form.banco.data
        employee.numero_cuenta_bancaria = form.numero_cuenta_bancaria.data
        employee.tipo_contrato = form.tipo_contrato.data or None
        employee.creado_por = current_user.usuario

        # Initial implementation data
        employee.anio_implementacion_inicial = form.anio_implementacion_inicial.data
        employee.mes_ultimo_cierre = form.mes_ultimo_cierre.data
        employee.salario_acumulado = form.salario_acumulado.data or Decimal("0.00")
        employee.impuesto_acumulado = form.impuesto_acumulado.data or Decimal("0.00")

        # Store last three salaries in JSON format using helper function
        employee.ultimos_tres_salarios = process_last_three_salaries(form)

        # Process custom fields
        employee.datos_adicionales = process_custom_fields_from_request(custom_fields)

        db.session.add(employee)
        db.session.commit()
        flash(_("Empleado creado exitosamente."), "success")
        return redirect(url_for("employee.index"))

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
    employee = db.session.get(Empleado, id_)
    if not employee:
        flash(_(MSG_EMPLEADO_NO_ENCONTRADO), "error")
        return redirect(url_for("employee.index"))

    form = EmployeeForm(obj=employee)
    form.moneda_id.choices = get_currency_choices()
    form.empresa_id.choices = get_empresa_choices()
    custom_fields = get_custom_fields()

    if form.validate_on_submit():
        # Update codigo_empleado only if provided
        if form.codigo_empleado.data and form.codigo_empleado.data.strip():
            employee.codigo_empleado = form.codigo_empleado.data.strip()
        employee.primer_nombre = form.primer_nombre.data
        employee.segundo_nombre = form.segundo_nombre.data
        employee.primer_apellido = form.primer_apellido.data
        employee.segundo_apellido = form.segundo_apellido.data
        employee.genero = form.genero.data or None
        employee.nacionalidad = form.nacionalidad.data
        employee.tipo_identificacion = form.tipo_identificacion.data or None
        employee.identificacion_personal = form.identificacion_personal.data
        employee.id_seguridad_social = form.id_seguridad_social.data or None
        employee.id_fiscal = form.id_fiscal.data or None
        employee.tipo_sangre = form.tipo_sangre.data or None
        employee.fecha_nacimiento = form.fecha_nacimiento.data
        employee.fecha_alta = form.fecha_alta.data
        employee.fecha_baja = form.fecha_baja.data
        employee.activo = form.activo.data
        employee.cargo = form.cargo.data
        employee.area = form.area.data
        employee.centro_costos = form.centro_costos.data
        employee.salario_base = form.salario_base.data or Decimal("0.00")
        employee.moneda_id = form.moneda_id.data or None
        employee.empresa_id = form.empresa_id.data or None
        employee.correo = form.correo.data
        employee.telefono = form.telefono.data
        employee.direccion = form.direccion.data
        employee.estado_civil = form.estado_civil.data or None
        employee.banco = form.banco.data
        employee.numero_cuenta_bancaria = form.numero_cuenta_bancaria.data
        employee.tipo_contrato = form.tipo_contrato.data or None
        employee.modificado_por = current_user.usuario

        # Initial implementation data
        employee.anio_implementacion_inicial = form.anio_implementacion_inicial.data
        employee.mes_ultimo_cierre = form.mes_ultimo_cierre.data
        employee.salario_acumulado = form.salario_acumulado.data or Decimal("0.00")
        employee.impuesto_acumulado = form.impuesto_acumulado.data or Decimal("0.00")

        # Store last three salaries in JSON format using helper function
        employee.ultimos_tres_salarios = process_last_three_salaries(form)

        # Process custom fields
        employee.datos_adicionales = process_custom_fields_from_request(custom_fields)

        db.session.commit()
        flash(_("Empleado actualizado exitosamente."), "success")
        return redirect(url_for("employee.index"))

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
    employee = db.session.get(Empleado, id_)
    if not employee:
        flash(_(MSG_EMPLEADO_NO_ENCONTRADO), "error")
        return redirect(url_for("employee.index"))

    db.session.delete(employee)
    db.session.commit()
    flash(_("Empleado eliminado exitosamente."), "success")
    return redirect(url_for("employee.index"))
