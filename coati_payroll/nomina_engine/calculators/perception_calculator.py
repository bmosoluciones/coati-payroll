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
        self.percepciones_snapshot: dict[str, Any] | None = None

    def _snapshot_for(self, percepcion) -> dict[str, Any] | None:
        """Resolve the catalog snapshot entry for a perception, if available."""
        if not self.percepciones_snapshot:
            return None
        return self.percepciones_snapshot.get(percepcion.id) or self.percepciones_snapshot.get(percepcion.codigo)

    @staticmethod
    def _snapshot_valido(snapshot_entry: dict[str, Any] | None, fecha_calculo: date) -> bool:
        """Check validity dates from the snapshot when available."""
        if not snapshot_entry:
            return True
        if snapshot_entry.get("vigente_desde"):
            desde = date.fromisoformat(snapshot_entry["vigente_desde"])
            if desde > fecha_calculo:
                return False
        if snapshot_entry.get("valido_hasta"):
            hasta = date.fromisoformat(snapshot_entry["valido_hasta"])
            if hasta < fecha_calculo:
                return False
        return True

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

            snapshot_entry = self._snapshot_for(percepcion)
            if not self._snapshot_valido(snapshot_entry, fecha_calculo):
                continue

            # When the perception exists in the catalog snapshot, prefer the
            # frozen formula/amount so recalculation reproduces the original
            # payroll even if the live catalog changed since.
            snap_val = snapshot_entry or {}
            formula_tipo = snap_val.get("formula_tipo", percepcion.formula_tipo)
            monto_default = snap_val.get("monto_default", percepcion.monto_default)
            porcentaje = snap_val.get("porcentaje", percepcion.porcentaje)
            formula = snap_val.get("formula", percepcion.formula)
            base_calculo = snap_val.get("base_calculo", getattr(percepcion, "base_calculo", None))

            # Check validity dates against the live object only when there is no snapshot
            if not snapshot_entry:
                if percepcion.vigente_desde and percepcion.vigente_desde > fecha_calculo:
                    continue
                if percepcion.valido_hasta and percepcion.valido_hasta < fecha_calculo:
                    continue

            # Calculate perception amount
            monto = self.concept_calculator.calculate(
                emp_calculo,
                formula_tipo,
                monto_default,
                porcentaje,
                formula,
                planilla_percepcion.monto_predeterminado,
                planilla_percepcion.porcentaje,
                codigo_concepto=percepcion.codigo,
                base_calculo=base_calculo,
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
