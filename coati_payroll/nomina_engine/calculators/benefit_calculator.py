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
        self.prestaciones_snapshot: dict[str, Any] | None = None

    def _snapshot_for(self, prestacion) -> dict[str, Any] | None:
        """Resolve the catalog snapshot entry for a benefit, if available."""
        if not self.prestaciones_snapshot:
            return None
        return self.prestaciones_snapshot.get(prestacion.id) or self.prestaciones_snapshot.get(prestacion.codigo)

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

            snapshot_entry = self._snapshot_for(prestacion)
            if not self._snapshot_valido(snapshot_entry, fecha_calculo):
                continue

            # When the benefit exists in the catalog snapshot, prefer the
            # frozen formula/amount so recalculation reproduces the original
            # payroll even if the live catalog changed since.
            formula_tipo = snapshot_entry.get("formula_tipo", prestacion.formula_tipo) if snapshot_entry else prestacion.formula_tipo
            monto_default = snapshot_entry.get("monto_default", prestacion.monto_default) if snapshot_entry else prestacion.monto_default
            porcentaje = snapshot_entry.get("porcentaje", prestacion.porcentaje) if snapshot_entry else prestacion.porcentaje
            formula = snapshot_entry.get("formula", prestacion.formula) if snapshot_entry else prestacion.formula
            base_calculo = snapshot_entry.get("base_calculo", getattr(prestacion, "base_calculo", None)) if snapshot_entry else getattr(prestacion, "base_calculo", None)

            # Check validity dates against the live object only when there is no snapshot
            if not snapshot_entry:
                if prestacion.vigente_desde and prestacion.vigente_desde > fecha_calculo:
                    continue
                if prestacion.valido_hasta and prestacion.valido_hasta < fecha_calculo:
                    continue

            # Calculate benefit amount
            monto = self.concept_calculator.calculate(
                emp_calculo,
                formula_tipo,
                monto_default,
                porcentaje,
                formula,
                planilla_prestacion.monto_predeterminado,
                planilla_prestacion.porcentaje,
                codigo_concepto=prestacion.codigo,
                base_calculo=base_calculo,
                unidad_calculo=getattr(prestacion, "unidad_calculo", None),
            )

            # Apply ceiling if defined (snapshot value takes precedence)
            tope_aplicacion = snapshot_entry.get("tope_aplicacion") if snapshot_entry else None
            if tope_aplicacion is not None:
                if monto > Decimal(str(tope_aplicacion)):
                    monto = Decimal(str(tope_aplicacion))
            elif prestacion.tope_aplicacion and monto > Decimal(str(prestacion.tope_aplicacion)):
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
