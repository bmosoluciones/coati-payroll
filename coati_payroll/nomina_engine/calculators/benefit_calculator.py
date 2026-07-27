# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Benefit calculator for payroll processing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

from coati_payroll.model import Planilla
from ..domain.employee_calculation import EmpleadoCalculo
from ..domain.calculation_items import PrestacionItem
from .concept_calculator import ConceptCalculator


class BenefitCalculator:
    """Calculator for employer benefits (prestaciones)."""

    def __init__(self, concept_calculator: ConceptCalculator):
        self.concept_calculator = concept_calculator

    def calculate(self, emp_calculo: EmpleadoCalculo, planilla: Planilla, fecha_calculo: date) -> list[PrestacionItem]:
        """Calculate all benefits for an employee."""
        prestaciones = []
        planilla_prestaciones = cast(list[Any], planilla.planilla_prestaciones)

        for planilla_prestacion in planilla_prestaciones:
            if not planilla_prestacion.activo:
                continue

            prestacion = planilla_prestacion.prestacion
            if not prestacion or not prestacion.activo:
                continue

            # Check validity dates
            if prestacion.vigente_desde and prestacion.vigente_desde > fecha_calculo:
                continue
            if prestacion.valido_hasta and prestacion.valido_hasta < fecha_calculo:
                continue

            # Calculate benefit amount
            monto = self.concept_calculator.calculate(
                emp_calculo,
                prestacion.formula_tipo,
                prestacion.monto_default,
                prestacion.porcentaje,
                prestacion.formula,
                planilla_prestacion.monto_predeterminado,
                planilla_prestacion.porcentaje,
                codigo_concepto=prestacion.codigo,
                base_calculo=getattr(prestacion, "base_calculo", None),
                unidad_calculo=getattr(prestacion, "unidad_calculo", None),
            )

            # Apply ceiling if defined
            if prestacion.tope_aplicacion and monto > Decimal(str(prestacion.tope_aplicacion)):
                monto = Decimal(str(prestacion.tope_aplicacion))

            if monto > 0:
                item = PrestacionItem(
                    codigo=prestacion.codigo,
                    nombre=prestacion.nombre,
                    monto=monto,
                    prioridad=planilla_prestacion.orden or 0,
                    prestacion_id=prestacion.id,
                )
                prestaciones.append(item)

        return prestaciones
