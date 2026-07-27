# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Perception calculator for payroll processing."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from coati_payroll.model import Planilla
from ..domain.employee_calculation import EmpleadoCalculo
from ..domain.calculation_items import PercepcionItem
from .concept_calculator import ConceptCalculator


class PerceptionCalculator:
    """Calculator for perceptions (income additions)."""

    def __init__(self, concept_calculator: ConceptCalculator):
        self.concept_calculator = concept_calculator

    def calculate(self, emp_calculo: EmpleadoCalculo, planilla: Planilla, fecha_calculo: date) -> list[PercepcionItem]:
        """Calculate all perceptions for an employee."""
        percepciones = []
        planilla_percepciones = cast(list[Any], planilla.planilla_percepciones)

        for planilla_percepcion in planilla_percepciones:
            if not planilla_percepcion.activo:
                continue

            percepcion = planilla_percepcion.percepcion
            if not percepcion or not percepcion.activo:
                continue

            # Check validity dates
            if percepcion.vigente_desde and percepcion.vigente_desde > fecha_calculo:
                continue
            if percepcion.valido_hasta and percepcion.valido_hasta < fecha_calculo:
                continue

            # Calculate perception amount
            monto = self.concept_calculator.calculate(
                emp_calculo,
                percepcion.formula_tipo,
                percepcion.monto_default,
                percepcion.porcentaje,
                percepcion.formula,
                planilla_percepcion.monto_predeterminado,
                planilla_percepcion.porcentaje,
                codigo_concepto=percepcion.codigo,
                base_calculo=getattr(percepcion, "base_calculo", None),
                unidad_calculo=getattr(percepcion, "unidad_calculo", None),
            )

            if monto > 0:
                item = PercepcionItem(
                    codigo=percepcion.codigo,
                    nombre=percepcion.nombre,
                    monto=monto,
                    prioridad=planilla_percepcion.orden or 0,
                    gravable=percepcion.gravable,
                    percepcion_id=percepcion.id,
                )
                percepciones.append(item)

        return percepciones
