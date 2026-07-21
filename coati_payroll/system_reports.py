# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""System reports definitions and implementations.

This module contains all pre-defined system reports that are optimized
and built into the application core. Each system report has a unique
identifier and an implementation function.
"""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from sqlalchemy import func, true
from sqlalchemy.sql.functions import count

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.model import (
    db,
    Empleado,
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    VacationAccount,
    VacationLedger,
)
from coati_payroll.enums import TipoDetalle

# ============================================================================
# System Report Registry
# ============================================================================

# Registry of all system reports
# Key: system_report_id
# Value: implementation function
SYSTEM_REPORTS: Dict[str, Callable] = {}


def register_system_report(report_id: str):
    """Decorator to register a system report implementation.

    Args:
        report_id: Unique identifier for the system report
    """

    def decorator(func: Callable):
        SYSTEM_REPORTS[report_id] = func
        return func

    return decorator


def get_system_report(report_id: str) -> Optional[Callable]:
    """Get system report implementation by ID.

    Args:
        report_id: System report identifier

    Returns:
        Report implementation function or None
    """
    return SYSTEM_REPORTS.get(report_id)


# ============================================================================
# Employee Reports
# ============================================================================


@register_system_report("employee_list")
def employee_list_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """General list of employees.

    Parameters:
        - activo (optional): Filter by active status
        - empresa_id (optional): Filter by company
    """
    stmt = db.select(Empleado)

    # Apply filters
    if "activo" in parameters:
        stmt = stmt.filter(Empleado.activo == parameters["activo"])

    if "empresa_id" in parameters:
        stmt = stmt.filter(Empleado.empresa_id == parameters["empresa_id"])

    results = db.session.execute(stmt.order_by(Empleado.primer_apellido, Empleado.primer_nombre)).scalars().all()

    return [
        {
            "Código": emp.codigo_empleado,
            "Nombres": f"{emp.primer_nombre} {emp.segundo_nombre or ''}".strip(),
            "Apellidos": f"{emp.primer_apellido} {emp.segundo_apellido or ''}".strip(),
            "Identificación": emp.identificacion_personal,
            "Cargo": emp.cargo or "",
            "Área": emp.area or "",
            "Salario Base": float(emp.salario_base) if emp.salario_base else 0.0,
            "Fecha Alta": emp.fecha_alta.isoformat() if emp.fecha_alta else "",
            "Activo": "Sí" if emp.activo else "No",
        }
        for emp in results
    ]


@register_system_report("employee_active_inactive")
def employee_active_inactive_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Active and inactive employees report.

    Shows current status of all employees with relevant dates.
    """
    results = (
        db.session.execute(db.select(Empleado).order_by(Empleado.activo.desc(), Empleado.primer_apellido))
        .scalars()
        .all()
    )

    return [
        {
            "Código": emp.codigo_empleado,
            "Nombre Completo": f"{emp.primer_nombre} {emp.primer_apellido}",
            "Identificación": emp.identificacion_personal,
            "Estado": "Activo" if emp.activo else "Inactivo",
            "Fecha Alta": emp.fecha_alta.isoformat() if emp.fecha_alta else "",
            "Fecha Baja": emp.fecha_baja.isoformat() if emp.fecha_baja else "",
            "Cargo": emp.cargo or "",
        }
        for emp in results
    ]


@register_system_report("employee_by_department")
def employee_by_department_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Employees by department/area.

    Groups employees by area and provides summary statistics.
    """
    results = (
        db.session.execute(
            db.select(Empleado).filter(Empleado.activo.is_(true())).order_by(Empleado.area, Empleado.primer_apellido)
        )
        .scalars()
        .all()
    )

    return [
        {
            "Área": emp.area or "Sin Asignar",
            "Código": emp.codigo_empleado,
            "Nombre": f"{emp.primer_nombre} {emp.primer_apellido}",
            "Cargo": emp.cargo or "",
            "Centro de Costos": emp.centro_costos or "",
            "Salario Base": float(emp.salario_base) if emp.salario_base else 0.0,
        }
        for emp in results
    ]


@register_system_report("employee_hires_terminations")
def employee_hires_terminations_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Hires and terminations by period.

    Parameters:
        - fecha_inicio: Start date
        - fecha_fin: End date
    """
    fecha_inicio = _coerce_report_date(parameters.get("fecha_inicio"))
    fecha_fin = _coerce_report_date(parameters.get("fecha_fin"))
    hires = _employees_in_date_range(Empleado.fecha_alta, fecha_inicio, fecha_fin)
    terminations = _employees_in_date_range(Empleado.fecha_baja, fecha_inicio, fecha_fin, required=True)
    results = [_format_employment_event(emp, "Alta", emp.fecha_alta) for emp in hires]
    results.extend(_format_employment_event(emp, "Baja", emp.fecha_baja) for emp in terminations)
    return sorted(results, key=lambda item: item["Fecha"])


def _coerce_report_date(value):
    """Convert an ISO date value from report parameters when necessary."""
    return datetime.fromisoformat(value).date() if isinstance(value, str) else value


def _employees_in_date_range(field, fecha_inicio, fecha_fin, required: bool = False):
    """Load employees whose date field falls within an optional range."""
    statement = db.select(Empleado)
    if required:
        statement = statement.filter(field.isnot(None))
    if fecha_inicio:
        statement = statement.filter(field >= fecha_inicio)
    if fecha_fin:
        statement = statement.filter(field <= fecha_fin)
    return db.session.execute(statement).scalars().all()


def _format_employment_event(employee, event_type: str, event_date) -> dict[str, Any]:
    """Build the common report row for a hire or termination."""
    return {
        "Tipo": event_type,
        "Fecha": event_date.isoformat() if event_date else "",
        "Código": employee.codigo_empleado,
        "Nombre": f"{employee.primer_nombre} {employee.primer_apellido}",
        "Cargo": employee.cargo or "",
        "Área": employee.area or "",
    }


# ============================================================================
# Payroll Reports
# ============================================================================


@register_system_report("payroll_by_period")
def payroll_by_period_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Payroll summary by period.

    Parameters:
        - periodo_inicio: Start date of period
        - periodo_fin: End date of period
        - planilla_id (optional): Filter by payroll template
    """
    stmt = db.select(Nomina)

    if "periodo_inicio" in parameters:
        fecha = parameters["periodo_inicio"]
        if isinstance(fecha, str):
            fecha = datetime.fromisoformat(fecha).date()
        stmt = stmt.filter(Nomina.periodo_inicio >= fecha)

    if "periodo_fin" in parameters:
        fecha = parameters["periodo_fin"]
        if isinstance(fecha, str):
            fecha = datetime.fromisoformat(fecha).date()
        stmt = stmt.filter(Nomina.periodo_fin <= fecha)

    if "planilla_id" in parameters:
        stmt = stmt.filter(Nomina.planilla_id == parameters["planilla_id"])

    results = db.session.execute(stmt.order_by(Nomina.periodo_inicio.desc())).scalars().all()

    return [
        {
            "Código": nomina.codigo_nomina,
            "Descripción": nomina.descripcion or "",
            "Período Inicio": nomina.periodo_inicio.isoformat() if nomina.periodo_inicio else "",
            "Período Fin": nomina.periodo_fin.isoformat() if nomina.periodo_fin else "",
            "Fecha Pago": nomina.fecha_pago.isoformat() if nomina.fecha_pago else "",
            "Estado": nomina.estado,
            "Total Bruto": float(nomina.total_bruto) if nomina.total_bruto else 0.0,
            "Total Deducciones": float(nomina.total_deducciones) if nomina.total_deducciones else 0.0,
            "Total Neto": float(nomina.total_neto) if nomina.total_neto else 0.0,
        }
        for nomina in results
    ]


@register_system_report("payroll_employee_detail")
def payroll_employee_detail_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detailed payroll by employee.

    Parameters:
        - nomina_id: Payroll run ID
    """
    nomina_id = parameters.get("nomina_id")

    if not nomina_id:
        return []

    results = db.session.execute(
        db.select(NominaEmpleado, Empleado)
        .join(Empleado, NominaEmpleado.empleado_id == Empleado.id)
        .filter(NominaEmpleado.nomina_id == nomina_id)
        .order_by(Empleado.primer_apellido, Empleado.primer_nombre)
    ).all()

    return [
        {
            "Código Empleado": empleado.codigo_empleado,
            "Nombre": f"{empleado.primer_nombre} {empleado.primer_apellido}",
            "Salario Base": float(nomina_emp.salario_base) if nomina_emp.salario_base else 0.0,
            "Total Percepciones": float(nomina_emp.total_percepciones) if nomina_emp.total_percepciones else 0.0,
            "Salario Bruto": float(nomina_emp.salario_bruto) if nomina_emp.salario_bruto else 0.0,
            "Total Deducciones": float(nomina_emp.total_deducciones) if nomina_emp.total_deducciones else 0.0,
            "Salario Neto": float(nomina_emp.salario_neto) if nomina_emp.salario_neto else 0.0,
            "Total Prestaciones": float(nomina_emp.total_prestaciones) if nomina_emp.total_prestaciones else 0.0,
        }
        for nomina_emp, empleado in results
    ]


@register_system_report("payroll_perceptions_summary")
def payroll_perceptions_summary_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Summary of perceptions by period.

    Parameters:
        - nomina_id: Payroll run ID
    """
    nomina_id = parameters.get("nomina_id")

    if not nomina_id:
        return []

    results = db.session.execute(
        db.select(
            NominaDetalle.concepto_codigo,
            NominaDetalle.concepto_nombre,
            count(NominaDetalle.id).label("cantidad_empleados"),
            func.sum(NominaDetalle.monto).label("total"),
        )
        .filter(NominaDetalle.nomina_id == nomina_id, NominaDetalle.tipo == TipoDetalle.INGRESO)
        .group_by(NominaDetalle.concepto_codigo, NominaDetalle.concepto_nombre)
        .order_by(NominaDetalle.concepto_codigo)
    ).all()

    return [
        {
            "Código Concepto": row.concepto_codigo,
            "Concepto": row.concepto_nombre,
            "Cantidad Empleados": row.cantidad_empleados,
            "Total": float(row.total) if row.total else 0.0,
        }
        for row in results
    ]


@register_system_report("payroll_deductions_summary")
def payroll_deductions_summary_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Summary of deductions by period.

    Parameters:
        - nomina_id: Payroll run ID
    """
    nomina_id = parameters.get("nomina_id")

    if not nomina_id:
        return []

    results = db.session.execute(
        db.select(
            NominaDetalle.concepto_codigo,
            NominaDetalle.concepto_nombre,
            count(NominaDetalle.id).label("cantidad_empleados"),
            func.sum(NominaDetalle.monto).label("total"),
        )
        .filter(NominaDetalle.nomina_id == nomina_id, NominaDetalle.tipo == TipoDetalle.DEDUCCION)
        .group_by(NominaDetalle.concepto_codigo, NominaDetalle.concepto_nombre)
        .order_by(NominaDetalle.concepto_codigo)
    ).all()

    return [
        {
            "Código Concepto": row.concepto_codigo,
            "Concepto": row.concepto_nombre,
            "Cantidad Empleados": row.cantidad_empleados,
            "Total": float(row.total) if row.total else 0.0,
        }
        for row in results
    ]


# ============================================================================
# Vacation Reports
# ============================================================================


@register_system_report("vacation_balance_by_employee")
def vacation_balance_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Vacation balance by employee.

    Shows current vacation balances for all employees.
    """
    results = db.session.execute(
        db.select(VacationAccount, Empleado)
        .join(Empleado, VacationAccount.empleado_id == Empleado.id)
        .filter(Empleado.activo.is_(true()))
        .order_by(Empleado.primer_apellido, Empleado.primer_nombre)
    ).all()

    return [
        {
            "Código Empleado": empleado.codigo_empleado,
            "Nombre": f"{empleado.primer_nombre} {empleado.primer_apellido}",
            "Días Acumulados": float(account.accrued_days) if account.accrued_days else 0.0,
            "Días Usados": float(account.used_days) if account.used_days else 0.0,
            "Balance Días": float(account.balance_days) if account.balance_days else 0.0,
        }
        for account, empleado in results
    ]


@register_system_report("vacation_taken_by_period")
def vacation_taken_by_period_report(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Vacations taken by period.

    Parameters:
        - fecha_inicio: Start date
        - fecha_fin: End date
    """
    fecha_inicio = parameters.get("fecha_inicio")
    fecha_fin = parameters.get("fecha_fin")

    if isinstance(fecha_inicio, str):
        fecha_inicio = datetime.fromisoformat(fecha_inicio).date()
    if isinstance(fecha_fin, str):
        fecha_fin = datetime.fromisoformat(fecha_fin).date()

    stmt = (
        db.select(VacationLedger, Empleado)
        .join(Empleado, VacationLedger.empleado_id == Empleado.id)
        .filter(VacationLedger.entry_type == "usage")
    )

    if fecha_inicio:
        stmt = stmt.filter(VacationLedger.entry_date >= fecha_inicio)
    if fecha_fin:
        stmt = stmt.filter(VacationLedger.entry_date <= fecha_fin)

    results = db.session.execute(stmt.order_by(VacationLedger.entry_date.desc())).all()

    return [
        {
            "Fecha": entry.entry_date.isoformat() if entry.entry_date else "",
            "Código Empleado": empleado.codigo_empleado,
            "Nombre": f"{empleado.primer_nombre} {empleado.primer_apellido}",
            "Días Usados": float(abs(entry.days_change)) if entry.days_change else 0.0,
            "Descripción": entry.description or "",
        }
        for entry, empleado in results
    ]


# ============================================================================
# Report Metadata
# ============================================================================

# Metadata for each system report
SYSTEM_REPORT_METADATA: Dict[str, Dict[str, Any]] = {
    "employee_list": {
        "name": "Listado General de Empleados",
        "description": "Lista completa de empleados con información básica",
        "category": "employee",
        "base_entity": "Employee",
        "parameters": [
            {"name": "activo", "type": "boolean", "required": False},
            {"name": "empresa_id", "type": "string", "required": False},
        ],
    },
    "employee_active_inactive": {
        "name": "Empleados Activos e Inactivos",
        "description": "Reporte de estado de empleados activos e inactivos",
        "category": "employee",
        "base_entity": "Employee",
        "parameters": [],
    },
    "employee_by_department": {
        "name": "Empleados por Departamento",
        "description": "Listado de empleados agrupados por área o departamento",
        "category": "employee",
        "base_entity": "Employee",
        "parameters": [],
    },
    "employee_hires_terminations": {
        "name": "Altas y Bajas de Empleados",
        "description": "Reporte de contrataciones y terminaciones por período",
        "category": "employee",
        "base_entity": "Employee",
        "parameters": [
            {"name": "fecha_inicio", "type": "date", "required": True},
            {"name": "fecha_fin", "type": "date", "required": True},
        ],
    },
    "payroll_by_period": {
        "name": "Nómina por Período",
        "description": "Resumen de nóminas por período de pago",
        "category": "payroll",
        "base_entity": "Nomina",
        "parameters": [
            {"name": "periodo_inicio", "type": "date", "required": False},
            {"name": "periodo_fin", "type": "date", "required": False},
            {"name": "planilla_id", "type": "string", "required": False},
        ],
    },
    "payroll_employee_detail": {
        "name": "Detalle de Nómina por Empleado",
        "description": "Detalle completo de nómina desglosado por empleado",
        "category": "payroll",
        "base_entity": "NominaEmpleado",
        "parameters": [{"name": "nomina_id", "type": "string", "required": True}],
    },
    "payroll_perceptions_summary": {
        "name": "Resumen de Percepciones",
        "description": "Resumen agregado de percepciones por concepto",
        "category": "payroll",
        "base_entity": "NominaDetalle",
        "parameters": [{"name": "nomina_id", "type": "string", "required": True}],
    },
    "payroll_deductions_summary": {
        "name": "Resumen de Deducciones",
        "description": "Resumen agregado de deducciones por concepto",
        "category": "payroll",
        "base_entity": "NominaDetalle",
        "parameters": [{"name": "nomina_id", "type": "string", "required": True}],
    },
    "vacation_balance_by_employee": {
        "name": "Balance de Vacaciones por Empleado",
        "description": "Saldo actual de vacaciones para cada empleado",
        "category": "vacation",
        "base_entity": "VacationAccount",
        "parameters": [],
    },
    "vacation_taken_by_period": {
        "name": "Vacaciones Tomadas por Período",
        "description": "Registro de vacaciones utilizadas en un período",
        "category": "vacation",
        "base_entity": "VacationLedger",
        "parameters": [
            {"name": "fecha_inicio", "type": "date", "required": True},
            {"name": "fecha_fin", "type": "date", "required": True},
        ],
    },
}


def get_system_report_metadata(report_id: str) -> Optional[Dict[str, Any]]:
    """Get metadata for a system report.

    Args:
        report_id: System report identifier

    Returns:
        Report metadata or None
    """
    return SYSTEM_REPORT_METADATA.get(report_id)
