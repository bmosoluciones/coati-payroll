# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Perception calculator for payroll processing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
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
        salario_gravable_periodo = Decimal(
            str(
                getattr(
                    emp_calculo,
                    "salario_neto_inasistencia",
                    getattr(emp_calculo, "salario_gravable", 0),
                )
                or 0
            )
        )

        for planilla_percepcion in planilla_percepciones:
            item = self._calculate_item(
                planilla_percepcion,
                emp_calculo,
                fecha_calculo,
                salario_gravable_periodo=salario_gravable_periodo,
            )
            if item is not None:
                percepciones.append(item)
                if item.gravable:
                    salario_gravable_periodo += item.monto_gravable or Decimal("0.00")

        return percepciones

    def _calculate_item(
        self,
        association,
        emp_calculo,
        fecha_calculo,
        salario_gravable_periodo: Decimal = Decimal("0.00"),
    ) -> PercepcionItem | None:
        """Calculate one active perception association."""
        if not association.activo:
            return None

        percepcion = association.percepcion
        if not percepcion or not percepcion.activo:
            return None

        snapshot_entry = self._snapshot_for(percepcion)
        if not self._snapshot_valido(snapshot_entry, fecha_calculo):
            return None

        snap_val = snapshot_entry or {}
        formula_tipo = snap_val.get("formula_tipo", percepcion.formula_tipo)
        monto_default = snap_val.get("monto_default", percepcion.monto_default)
        porcentaje = snap_val.get("porcentaje", percepcion.porcentaje)
        formula = snap_val.get("formula", percepcion.formula)
        base_calculo = snap_val.get("base_calculo", getattr(percepcion, "base_calculo", None))
        unidad_calculo = snap_val.get("unidad_calculo", getattr(percepcion, "unidad_calculo", None))
        techo_anual = snap_val.get("techo_anual", getattr(percepcion, "techo_anual", None))
        tope_base_gravable = snap_val.get("tope_base_gravable", getattr(percepcion, "tope_base_gravable", None))
        monto_exento = Decimal(str(snap_val.get("monto_exento", getattr(percepcion, "monto_exento", 0)) or 0))
        variables = getattr(emp_calculo, "variables_calculo", {})
        acumulado_anual = variables.get(f"percepcion_{percepcion.codigo}_acumulado", 0)

        if not snapshot_entry and not self._live_perception_is_valid(percepcion, fecha_calculo):
            return None

        monto = self.concept_calculator.calculate(
            emp_calculo,
            formula_tipo,
            monto_default,
            porcentaje,
            formula,
            association.monto_predeterminado,
            association.porcentaje,
            codigo_concepto=percepcion.codigo,
            base_calculo=base_calculo,
            unidad_calculo=unidad_calculo,
            techo_anual=techo_anual,
            tope_base_gravable=tope_base_gravable,
            acumulado_anual=acumulado_anual,
        )
        if monto <= 0:
            return None

        monto_exento_aplicado = min(monto, max(Decimal("0.00"), monto_exento))
        monto_gravable = max(Decimal("0.00"), monto - monto_exento_aplicado)
        if tope_base_gravable is not None and snap_val.get("gravable", percepcion.gravable):
            base_ytd = Decimal(str(variables.get("salario_gravable_acumulado", 0) or 0))
            limite_restante = max(
                Decimal("0.00"), Decimal(str(tope_base_gravable)) - base_ytd - salario_gravable_periodo
            )
            monto_gravable = min(monto_gravable, limite_restante)

        return PercepcionItem(
            codigo=percepcion.codigo,
            nombre=percepcion.nombre,
            monto=monto,
            prioridad=association.orden or 0,
            # Taxability is part of the payroll catalog snapshot.  Reading it
            # from the mutable catalog breaks historical recalculations when a
            # perception is later reclassified.
            gravable=snap_val.get("gravable", percepcion.gravable),
            percepcion_id=percepcion.id,
            monto_exento=monto_exento_aplicado,
            monto_gravable=monto_gravable,
        )

    @staticmethod
    def _live_perception_is_valid(percepcion, fecha_calculo: date) -> bool:
        """Check validity dates on the live catalog entry."""
        if percepcion.vigente_desde and percepcion.vigente_desde > fecha_calculo:
            return False
        if percepcion.valido_hasta and percepcion.valido_hasta < fecha_calculo:
            return False
        return True
