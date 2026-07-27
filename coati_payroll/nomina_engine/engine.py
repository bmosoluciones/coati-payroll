# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Main payroll engine orchestrator - refactored implementation."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from coati_payroll.model import db, Planilla, Nomina
from coati_payroll.log import TRACE_LEVEL_NUM, is_trace_enabled, log
from .domain.employee_calculation import EmpleadoCalculo
from .services.payroll_execution_service import PayrollExecutionService


class NominaEngine:
    """Engine for executing payroll runs.

    This engine processes a Planilla configuration and generates a complete
    Nomina with all employee calculations. It handles:

    1. Perceptions (ingresos) - add to gross salary
    2. Deductions (deducciones) - subtract from net salary, in priority order
    3. Benefits (prestaciones) - employer costs, don't affect employee pay
    4. Automatic deductions - loans and advances from Adelanto table
    5. Accumulated annual values - for progressive tax calculations
    """

    def __init__(
        self,
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        fecha_calculo: date | None = None,
        usuario: str | None = None,
        excluded_nomina_id: str | None = None,
    ):
        """Initialize the payroll engine.

        Args:
            planilla: The Planilla to execute
            periodo_inicio: Start date of the payroll period
            periodo_fin: End date of the payroll period
            fecha_calculo: Date of calculation (defaults to today)
            usuario: Username executing the payroll
            excluded_nomina_id: Nomina ID to ignore in overlap/duplicate validation.
                Used by recalculation flow to ignore the source nomina.
        """
        self.planilla = planilla
        self.periodo_inicio = periodo_inicio
        self.periodo_fin = periodo_fin
        self.fecha_calculo = fecha_calculo or date.today()
        self.usuario = usuario
        self.excluded_nomina_id = excluded_nomina_id
        self.nomina: Nomina | None = None
        self.empleados_calculo: list[EmpleadoCalculo] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

        # Initialize execution service
        self.execution_service = PayrollExecutionService(db.session)

    def _trace(self, message: str) -> None:
        """Trace helper for logging."""
        if is_trace_enabled():
            log.log(TRACE_LEVEL_NUM, message)

    def validar_planilla(self) -> bool:
        """Validate that the planilla is ready for execution.

        Returns:
            True if valid, False otherwise
        """
        from .domain.payroll_context import PayrollContext

        context = PayrollContext(
            planilla_id=self.planilla.id,
            periodo_inicio=self.periodo_inicio,
            periodo_fin=self.periodo_fin,
            fecha_calculo=self.fecha_calculo,
            usuario=self.usuario,
            excluded_nomina_id=self.excluded_nomina_id,
        )

        validation_result = self.execution_service.planilla_validator.validate(context)
        if not validation_result.is_valid:
            self.errors.extend(validation_result.errors)
            return False

        return True

    def ejecutar(self) -> Nomina | None:
        """Execute the payroll run.

        Returns:
            The generated Nomina record, or None if execution failed
        """
        # Validate planilla
        if not self.validar_planilla():
            return None

        try:
            # Execute payroll using service
            nomina, empleados_calculo, errors, warnings = self.execution_service.execute_payroll(
                self.planilla,
                self.periodo_inicio,
                self.periodo_fin,
                self.fecha_calculo,
                self.usuario,
                excluded_nomina_id=self.excluded_nomina_id,
            )

            self.nomina = nomina
            self.empleados_calculo = empleados_calculo
            self.errors = errors
            self.warnings = warnings

            if nomina and not self.errors:
                db.session.commit()
            elif nomina and self.errors:
                # Commit ERROR nomina for audit trail only — no side effects
                # were applied (they are deferred to after validation passes).
                db.session.commit()
            else:
                db.session.rollback()
        except Exception:
            db.session.rollback()
            raise

        return nomina


def ejecutar_nomina(
    planilla_id: str,
    periodo_inicio: date,
    periodo_fin: date,
    fecha_calculo: date | None = None,
    usuario: str | None = None,
    excluded_nomina_id: str | None = None,
) -> tuple[Nomina | None, list[str], list[str]]:
    """Execute a payroll run for a planilla.

    Convenience function for executing a payroll run.

    Args:
        planilla_id: ID of the Planilla to execute
        periodo_inicio: Start date of the payroll period
        periodo_fin: End date of the payroll period
        fecha_calculo: Date of calculation (defaults to today)
        usuario: Username executing the payroll

    Returns:
        Tuple of (Nomina or None, list of errors, list of warnings)
    """
    # Eagerly load all relationships needed for payroll processing
    from sqlalchemy.orm import joinedload
    from sqlalchemy import select
    from coati_payroll.model import PlanillaIngreso, PlanillaDeduccion, PlanillaPrestacion, PlanillaEmpleado

    planilla = (
        db.session.execute(
            select(Planilla)
            .options(
                joinedload(cast(Any, Planilla.planilla_percepciones)).joinedload(cast(Any, PlanillaIngreso.percepcion)),
                joinedload(cast(Any, Planilla.planilla_deducciones)).joinedload(cast(Any, PlanillaDeduccion.deduccion)),
                joinedload(cast(Any, Planilla.planilla_prestaciones)).joinedload(
                    cast(Any, PlanillaPrestacion.prestacion)
                ),
                joinedload(cast(Any, Planilla.planilla_empleados)).joinedload(cast(Any, PlanillaEmpleado.empleado)),
                joinedload(cast(Any, Planilla.planilla_reglas_calculo)),
                joinedload(cast(Any, Planilla.tipo_planilla)),
                joinedload(cast(Any, Planilla.moneda)),
            )
            .filter(Planilla.id == planilla_id)
        )
        .unique()
        .scalar_one_or_none()
    )

    if not planilla:
        return None, ["Planilla no encontrada."], []

    engine = NominaEngine(
        planilla=planilla,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        fecha_calculo=fecha_calculo,
        usuario=usuario,
        excluded_nomina_id=excluded_nomina_id,
    )

    nomina = engine.ejecutar()

    return nomina, engine.errors, engine.warnings
