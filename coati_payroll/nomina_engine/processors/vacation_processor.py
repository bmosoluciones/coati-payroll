# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Vacation processor for vacation accrual and usage."""

from __future__ import annotations

from coati_payroll.log import log
from coati_payroll.model import Empleado, NominaEmpleado, Planilla

from ..domain.employee_calculation import EmpleadoCalculo
from ..results.warning_collector import WarningCollectorProtocol


class VacationProcessor:
    """Processor for vacation accrual and usage."""

    def __init__(
        self,
        planilla: Planilla,
        periodo_inicio,
        periodo_fin,
        usuario: str | None = None,
        warnings: WarningCollectorProtocol | None = None,
        apply_side_effects: bool = True,
        snapshot: dict | None = None,
        nomina_id: str | None = None,
    ):
        self.planilla = planilla
        self.periodo_inicio = periodo_inicio
        self.periodo_fin = periodo_fin
        self.usuario = usuario
        self.warnings = warnings if warnings is not None else []
        self.apply_side_effects = apply_side_effects
        self.snapshot = snapshot
        self.nomina_id = nomina_id

    def process_vacations(
        self, empleado: Empleado, emp_calculo: EmpleadoCalculo, nomina_empleado: NominaEmpleado
    ) -> dict | None:
        """Process vacation accrual and usage for an employee."""
        from coati_payroll.nomina_engine.validators import (
            NominaEngineError,
            ValidationError,
        )

        try:
            from coati_payroll.vacation_service import VacationService

            vacation_service = VacationService(
                planilla=self.planilla,
                periodo_inicio=self.periodo_inicio,
                periodo_fin=self.periodo_fin,
                apply_side_effects=self.apply_side_effects,
                snapshot=self.snapshot,
                nomina_id=self.nomina_id,
            )

            resumen_before = vacation_service.obtener_resumen_vacaciones(empleado)

            # Accumulate vacation time
            accrued = vacation_service.acumular_vacaciones_empleado(
                empleado=empleado,
                nomina_empleado=nomina_empleado,
                usuario=self.usuario,
            )

            # Process vacation novelties (time off taken)
            used = vacation_service.procesar_novedades_vacaciones(
                empleado=empleado,
                usuario=self.usuario,
            )
            resumen_after = vacation_service.obtener_resumen_vacaciones(empleado)
            return {
                "accrued": str(accrued),
                "used": str(used),
                "balance_before": str(resumen_before["balance"]) if resumen_before else None,
                "balance_after": str(resumen_after["balance"]) if resumen_after else None,
                "policy_codigo": resumen_after["policy_codigo"] if resumen_after else None,
            }

        except Exception as e:
            if isinstance(e, (ValidationError, NominaEngineError)):
                raise
            log.error("Error procesando vacaciones para empleado %s: %s", empleado.codigo_empleado, str(e))
            self.warnings.append(
                f"No se pudieron procesar vacaciones para {empleado.primer_nombre} "
                f"{empleado.primer_apellido}: {e!s}"
            )
            raise
