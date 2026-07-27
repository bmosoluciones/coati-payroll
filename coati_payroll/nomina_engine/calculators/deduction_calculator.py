# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Deduction calculator for payroll processing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal


from coati_payroll.model import Planilla
from ..domain.employee_calculation import EmpleadoCalculo
from ..domain.calculation_items import DeduccionItem
from .concept_calculator import ConceptCalculator
from ..results.warning_collector import WarningCollectorProtocol


class DeductionCalculator:
    """Calculator for deductions (salary subtractions)."""

    def __init__(self, concept_calculator: ConceptCalculator, warnings: WarningCollectorProtocol):
        self.concept_calculator = concept_calculator
        self.warnings = warnings

    def calculate(self, emp_calculo: EmpleadoCalculo, planilla: Planilla, fecha_calculo: date) -> list[DeduccionItem]:
        """Calculate all deductions for an employee, applying priority order."""
        emp_calculo.deducciones = []
        saldo_disponible = emp_calculo.salario_bruto

        # Sort planilla deductions by priority (lower number = higher priority)
        planilla_deducciones = list(planilla.planilla_deducciones)
        planilla_deducciones.sort(key=lambda x: getattr(x, "prioridad", 100))

        for planilla_deduccion in planilla_deducciones:
            if not planilla_deduccion.activo:
                continue

            deduccion = planilla_deduccion.deduccion
            if not deduccion or not deduccion.activo:
                continue

            if deduccion.codigo in emp_calculo.inasistencia_codigos_descuento:
                continue

            # Check validity dates
            if deduccion.vigente_desde and deduccion.vigente_desde > fecha_calculo:
                continue
            if deduccion.valido_hasta and deduccion.valido_hasta < fecha_calculo:
                continue

            # Calculate deduction amount
            monto = self.concept_calculator.calculate(
                emp_calculo,
                deduccion.formula_tipo,
                deduccion.monto_default,
                deduccion.porcentaje,
                deduccion.formula,
                planilla_deduccion.monto_predeterminado,
                planilla_deduccion.porcentaje,
                codigo_concepto=deduccion.codigo,
                base_calculo=getattr(deduccion, "base_calculo", None),
                unidad_calculo=getattr(deduccion, "unidad_calculo", None),
            )

            if monto > 0:
                monto_aplicar = max(Decimal("0.00"), min(monto, saldo_disponible))

                if monto_aplicar <= 0:
                    if planilla_deduccion.es_obligatoria:
                        self.warnings.append(
                            f"Empleado {emp_calculo.empleado.primer_nombre} "
                            f"{emp_calculo.empleado.primer_apellido}: "
                            f"Deducción obligatoria {deduccion.codigo} no se pudo aplicar "
                            f"(saldo insuficiente: {saldo_disponible})."
                        )
                    else:
                        self.warnings.append(
                            f"Empleado {emp_calculo.empleado.primer_nombre} "
                            f"{emp_calculo.empleado.primer_apellido}: "
                            f"Deducción {deduccion.codigo} omitida por saldo insuficiente."
                        )
                    continue

                item = DeduccionItem(
                    codigo=deduccion.codigo,
                    nombre=deduccion.nombre,
                    monto=monto_aplicar,
                    prioridad=planilla_deduccion.prioridad,
                    es_obligatoria=planilla_deduccion.es_obligatoria,
                    deduccion_id=deduccion.id,
                )
                emp_calculo.deducciones.append(item)
                saldo_disponible -= monto_aplicar

        return emp_calculo.deducciones
