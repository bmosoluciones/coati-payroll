# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Validator for Employee."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from coati_payroll.model import Empleado
from ..domain.payroll_context import PayrollContext
from ..results.validation_result import ValidationResult
from ..validators.base_validator import BaseValidator


class EmployeeValidator(BaseValidator):
    """Validates that an employee is eligible for payroll processing."""

    def validate(self, context: PayrollContext) -> ValidationResult:
        """Validate employee - this method signature is required by BaseValidator."""
        # This validator is called per-employee, not per-context
        # So we provide a separate method
        result = ValidationResult()
        return result

    def validate_employee(
        self,
        empleado: Empleado,
        planilla_empresa_id: str | None,
        periodo_inicio: date,
        periodo_fin: date,
        planilla_empleado=None,
        allow_historical_inactive: bool = False,
        salario_base_override: Decimal | None = None,
        moneda_id_override: str | None = None,
    ) -> ValidationResult:
        """Validate employee for payroll processing."""
        result = ValidationResult()

        if not empleado.activo and not allow_historical_inactive:
            result.add_error(f"Empleado {empleado.codigo_empleado} no está activo")

        if planilla_empleado is not None:
            fecha_inicio = getattr(planilla_empleado, "fecha_inicio", None)
            fecha_fin = getattr(planilla_empleado, "fecha_fin", None)
            if fecha_inicio and fecha_inicio > periodo_fin:
                result.add_error(
                    f"Empleado {empleado.codigo_empleado}: la asignación inicia "
                    f"({fecha_inicio}) después del fin del período ({periodo_fin})"
                )
            if fecha_fin and fecha_fin < periodo_inicio:
                result.add_error(
                    f"Empleado {empleado.codigo_empleado}: la asignación terminó "
                    f"({fecha_fin}) antes del inicio del período ({periodo_inicio})"
                )

        if empleado.fecha_alta:
            if empleado.fecha_alta > periodo_fin:
                result.add_error(
                    f"Empleado {empleado.codigo_empleado}: fecha de ingreso ({empleado.fecha_alta}) "
                    f"es posterior al período a procesar ({periodo_fin})"
                )
        else:
            result.add_error(f"Empleado {empleado.codigo_empleado} no tiene fecha de ingreso definida")

        if empleado.fecha_baja:
            if empleado.fecha_baja < periodo_inicio:
                result.add_error(
                    f"Empleado {empleado.codigo_empleado}: fecha de salida ({empleado.fecha_baja}) "
                    f"es anterior al inicio del período ({periodo_inicio})"
                )
            if empleado.fecha_alta and empleado.fecha_baja < empleado.fecha_alta:
                result.add_error(
                    f"Empleado {empleado.codigo_empleado}: fecha de salida ({empleado.fecha_baja}) "
                    f"es anterior a la fecha de ingreso ({empleado.fecha_alta})"
                )

        if not empleado.identificacion_personal:
            result.add_error(f"Empleado {empleado.codigo_empleado} no tiene identificación personal")

        salario = salario_base_override if salario_base_override is not None else empleado.salario_base
        if salario is None or salario <= Decimal("0.00"):
            result.add_error(f"Empleado {empleado.codigo_empleado} tiene salario base inválido ({salario})")

        if not empleado.empresa_id:
            result.add_error(f"Empleado {empleado.codigo_empleado} no está asignado a ninguna empresa")

        if planilla_empresa_id and empleado.empresa_id:
            if empleado.empresa_id != planilla_empresa_id:
                result.add_error(
                    f"Empleado {empleado.codigo_empleado} pertenece a empresa diferente a la planilla. "
                    f"Empleado empresa_id={empleado.empresa_id}, Planilla empresa_id={planilla_empresa_id}"
                )

        if not (moneda_id_override or empleado.moneda_id):
            result.add_error(f"Empleado {empleado.codigo_empleado} no tiene moneda definida")

        return result
