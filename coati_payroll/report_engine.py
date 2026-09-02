# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Report execution engine for system and custom reports.

This module provides the core functionality for executing reports:
- Query building for custom reports with security constraints
- Expression evaluation for calculated columns
- Pagination and result limiting
- Integration with system report implementations
"""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, cast

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #


# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from coati_payroll.enums import ReportType, ReportExecutionStatus
from coati_payroll.formula_engine import ExpressionEvaluator
from coati_payroll.formula_engine.exceptions import CalculationError
from coati_payroll.model import (
    db,
    Report,
    ReportExecution,
    Empleado,
    Nomina,
    NominaEmpleado,
    VacationAccount,
    Empresa,
    Planilla,
)
from coati_payroll.log import log

# ============================================================================
# Whitelisted entities and fields for custom reports
# ============================================================================

# Entities that can be used as base for custom reports
ALLOWED_ENTITIES = {
    "Employee": Empleado,
    "Nomina": Nomina,
    "NominaEmpleado": NominaEmpleado,
    "VacationAccount": VacationAccount,
    "Empresa": Empresa,
    "Planilla": Planilla,
}

# Whitelisted fields per entity (for security)
ALLOWED_FIELDS = {
    "Employee": [
        "codigo_empleado",
        "primer_nombre",
        "segundo_nombre",
        "primer_apellido",
        "segundo_apellido",
        "genero",
        "nacionalidad",
        "identificacion_personal",
        "fecha_nacimiento",
        "fecha_alta",
        "fecha_baja",
        "activo",
        "cargo",
        "area",
        "centro_costos",
        "salario_base",
        "correo",
        "telefono",
        "tipo_contrato",
    ],
    "Nomina": [
        "codigo_nomina",
        "descripcion",
        "periodo_inicio",
        "periodo_fin",
        "fecha_pago",
        "estado",
        "total_bruto",
        "total_deducciones",
        "total_neto",
    ],
    "NominaEmpleado": [
        "salario_base",
        "total_percepciones",
        "salario_bruto",
        "total_deducciones",
        "salario_neto",
        "total_prestaciones",
    ],
    "VacationAccount": [
        "balance_days",
        "balance_hours",
        "accrued_days",
        "accrued_hours",
        "used_days",
        "used_hours",
    ],
    "Empresa": [
        "codigo",
        "razon_social",
        "nombre_comercial",
        "ruc",
        "activo",
    ],
    "Planilla": [
        "nombre",
        "descripcion",
        "activo",
    ],
}

# Whitelisted operators for filters
ALLOWED_OPERATORS = {
    "=": lambda field, value: field == value,
    "!=": lambda field, value: field != value,
    ">": lambda field, value: field > value,
    ">=": lambda field, value: field >= value,
    "<": lambda field, value: field < value,
    "<=": lambda field, value: field <= value,
    "like": lambda field, value: field.like(f"%{value}%"),
    "in": lambda field, value: field.in_(value if isinstance(value, list) else [value]),
    "is_null": lambda field, value: field.is_(None),
    "is_not_null": lambda field, value: field.isnot(None),
}

# Maximum rows per report execution
MAX_ROWS_PER_EXECUTION = 50000


# ============================================================================
# Custom Report Query Builder
# ============================================================================


class CustomReportBuilder:
    """Builds and executes queries for custom reports.

    Uses a whitelist-based approach for security:
    - Only allowed entities can be queried
    - Only allowed fields can be selected
    - Only allowed operators can be used in filters
    - No raw SQL or arbitrary code execution
    """

    def __init__(self, report: Report):
        """Initialize the report builder.

        Args:
            report: Report instance to build query for
        """
        self.report = report
        self.definition = report.definition or {}
        self.base_entity_name = report.base_entity
        self.base_entity = ALLOWED_ENTITIES.get(self.base_entity_name)

        if not self.base_entity:
            raise ValueError(f"Invalid base entity: {self.base_entity_name}")

    def validate_definition(self) -> List[str]:
        """Validate report definition for security.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate base entity
        if self.base_entity_name not in ALLOWED_ENTITIES:
            errors.append(f"Base entity '{self.base_entity_name}' is not allowed")

        # Validate columns
        columns = self.definition.get("columns", [])
        for col in columns:
            col_type = col.get("type")
            if col_type == "field":
                entity = col.get("entity", self.base_entity_name)
                field = col.get("field")

                if entity not in ALLOWED_FIELDS:
                    errors.append(f"Entity '{entity}' is not allowed")
                elif field not in ALLOWED_FIELDS[entity]:
                    errors.append(f"Field '{field}' is not allowed for entity '{entity}'")

            elif col_type == "expression":
                expression = col.get("expression")
                if not isinstance(expression, str) or not expression.strip():
                    errors.append("Expression columns require a non-empty expression")
                    continue
                try:
                    ExpressionEvaluator(
                        {field: Decimal("0") for fields in ALLOWED_FIELDS.values() for field in fields},
                        strict_mode=True,
                    ).evaluate(expression)
                except (CalculationError, ValueError, TypeError) as exc:
                    errors.append(f"Invalid expression: {exc}")

        # Validate filters
        filters = self.definition.get("filters", [])
        for filt in filters:
            field = filt.get("field")
            operator = filt.get("operator")

            if field not in ALLOWED_FIELDS.get(self.base_entity_name, []):
                errors.append(f"Filter field '{field}' is not allowed")

            if operator not in ALLOWED_OPERATORS:
                errors.append(f"Filter operator '{operator}' is not allowed")

        return errors

    def _apply_definition_filters(self, stmt):
        """Apply configured filters using only whitelisted fields/operators."""
        for filt in self.definition.get("filters", []):
            field_name = filt.get("field")
            operator = filt.get("operator")
            value = filt.get("value")
            if not field_name or operator not in ALLOWED_OPERATORS:
                continue
            field = getattr(self.base_entity, field_name, None)
            if field is not None:
                stmt = stmt.filter(ALLOWED_OPERATORS[operator](field, value))
        return stmt

    def _apply_runtime_filters(self, stmt, filters: Optional[Dict[str, Any]]):
        """Apply exact-match filters supplied at runtime."""
        allowed_fields = ALLOWED_FIELDS.get(self.base_entity_name, [])
        for field_name, value in (filters or {}).items():
            if field_name not in allowed_fields:
                continue
            field = getattr(self.base_entity, field_name, None)
            if field is not None:
                stmt = stmt.filter(field == value)
        return stmt

    def _apply_sorting(self, stmt):
        """Apply configured ordering on whitelisted fields."""
        allowed_fields = ALLOWED_FIELDS.get(self.base_entity_name, [])
        for sort in self.definition.get("sorting", []):
            field_name = sort.get("field")
            if field_name not in allowed_fields:
                continue
            field = getattr(self.base_entity, field_name, None)
            if field is None:
                continue
            stmt = stmt.order_by(field.desc() if sort.get("direction", "asc").lower() == "desc" else field.asc())
        return stmt

    @staticmethod
    def _apply_pagination(stmt, page: int, per_page: int):
        """Apply bounded pagination to a query."""
        stmt = stmt.limit(min(per_page, MAX_ROWS_PER_EXECUTION))
        return stmt.offset((page - 1) * per_page) if page > 1 else stmt

    def build_query(self, filters: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 100):
        """Build SQLAlchemy select statement for the report.

        Args:
            filters: Additional runtime filters from user
            page: Page number for pagination
            per_page: Results per page

        Returns:
            SQLAlchemy Select statement
        """
        # Start with base entity
        stmt = db.select(self.base_entity)

        stmt = self._apply_definition_filters(stmt)
        stmt = self._apply_runtime_filters(stmt, filters)
        stmt = self._apply_sorting(stmt)
        return self._apply_pagination(stmt, page, per_page)

    def execute(
        self, filters: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 100
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Execute the report and return results.

        Args:
            filters: Additional runtime filters
            page: Page number
            per_page: Results per page

        Returns:
            Tuple of (results as list of dicts, total count)
        """
        from sqlalchemy.sql.functions import count

        count_stmt = self._apply_runtime_filters(self._apply_definition_filters(db.select(self.base_entity)), filters)
        total_count = db.session.execute(db.select(count()).select_from(count_stmt.subquery())).scalar() or 0
        stmt = self.build_query(filters, page, per_page)
        results = db.session.execute(stmt).scalars().all()
        return self._serialize_results(results), total_count

    def _serialize_results(self, results) -> list[dict[str, Any]]:
        """Convert report rows to JSON-compatible dictionaries."""
        columns = self.definition.get("columns", [])
        output = []
        for row in results:
            row_dict = {}
            variables: dict[str, Decimal] = {}
            for allowed_field in ALLOWED_FIELDS.get(self.base_entity_name, []):
                allowed_value = getattr(row, allowed_field, None)
                if isinstance(allowed_value, (Decimal, int, float)) and not isinstance(allowed_value, bool):
                    variables[allowed_field] = Decimal(str(allowed_value))
            for col in columns:
                if col.get("type") != "field":
                    continue
                field_name = col.get("field")
                label = col.get("label", field_name)
                value = getattr(row, field_name, None)
                if isinstance(value, Decimal):
                    value = float(value)
                elif isinstance(value, datetime):
                    value = value.isoformat()
                row_dict[label] = value
            for col in columns:
                if col.get("type") != "expression":
                    continue
                expression = col.get("expression", "")
                label = col.get("label", expression)
                try:
                    value = ExpressionEvaluator(variables, strict_mode=True).evaluate(expression)
                    row_dict[label] = float(value) if isinstance(value, Decimal) else value
                except (CalculationError, ValueError, TypeError) as exc:
                    raise ValueError(f"Invalid report expression '{expression}': {exc}") from exc
            output.append(row_dict)
        return output


# ============================================================================
# Report Execution Manager
# ============================================================================


class ReportExecutionManager:
    """Manages report execution lifecycle and tracking."""

    def __init__(self, report: Report, user: str):
        """Initialize execution manager.

        Args:
            report: Report to execute
            user: Username of person executing the report
        """
        self.report = report
        self.user = user

    def execute(
        self, parameters: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 100
    ) -> Tuple[List[Dict[str, Any]], int, ReportExecution]:
        """Execute report and track execution.

        Args:
            parameters: Runtime parameters/filters
            page: Page number
            per_page: Results per page

        Returns:
            Tuple of (results, total_count, execution_record)
        """
        # Create execution record
        execution = ReportExecution(
            report_id=self.report.id,
            status=ReportExecutionStatus.RUNNING,
            parameters=parameters or {},
            executed_by=self.user,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(execution)
        db.session.commit()

        start_time = datetime.now(timezone.utc)

        try:
            if self.report.type == ReportType.CUSTOM:
                # Execute custom report
                builder = CustomReportBuilder(self.report)
                results, total_count = builder.execute(parameters, page, per_page)
            else:
                # Execute system report
                from coati_payroll.system_reports import get_system_report

                system_report_func = get_system_report(self.report.system_report_id)
                if not system_report_func:
                    raise ValueError(f"System report '{self.report.system_report_id}' not found")

                # Execute system report (they handle their own pagination)
                results = system_report_func(parameters or {})
                total_count = len(results)

                # Apply pagination to system report results
                if page > 1 or per_page < len(results):
                    start_idx = (page - 1) * per_page
                    end_idx = start_idx + per_page
                    results = results[start_idx:end_idx]

            # Update execution record
            end_time = datetime.now(timezone.utc)
            execution.status = ReportExecutionStatus.COMPLETED
            execution.completed_at = end_time
            execution.row_count = len(results)
            execution.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            db.session.commit()

            return results, total_count, execution

        except Exception as e:
            # Update execution record with error
            execution.status = ReportExecutionStatus.FAILED
            execution.completed_at = datetime.now(timezone.utc)
            execution.error_message = str(e)[:1000]  # Truncate to fit column

            db.session.commit()

            log.error("Report execution failed: %s", e)
            raise


# ============================================================================
# Permission Checking
# ============================================================================


def can_view_report(report: Report, user_role: str) -> bool:
    """Check if user role can view the report.

    Args:
        report: Report to check
        user_role: User's role (admin, hhrr, audit)

    Returns:
        True if user can view report
    """
    # Admin can always view
    if user_role == "admin":
        return True

    # Check report permissions
    permissions = cast(list[Any], report.permissions)
    for perm in permissions:
        if perm.role == user_role and perm.can_view:
            return True

    return False


def can_execute_report(report: Report, user_role: str) -> bool:
    """Check if user role can execute the report.

    Args:
        report: Report to check
        user_role: User's role

    Returns:
        True if user can execute report
    """
    # Admin can always execute
    if user_role == "admin":
        return True

    # Check report permissions
    permissions = cast(list[Any], report.permissions)
    for perm in permissions:
        if perm.role == user_role and perm.can_execute:
            return True

    return False


def can_export_report(report: Report, user_role: str) -> bool:
    """Check if user role can export the report.

    Args:
        report: Report to check
        user_role: User's role

    Returns:
        True if user can export report
    """
    # Admin can always export
    if user_role == "admin":
        return True

    # Check report permissions
    permissions = cast(list[Any], report.permissions)
    for perm in permissions:
        if perm.role == user_role and perm.can_export:
            return True

    return False
