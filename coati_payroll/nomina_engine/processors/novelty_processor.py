# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Novelty processor for loading employee novelties."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from coati_payroll.model import Empleado
from ..repositories.novelty_repository import NoveltyRepository


class NoveltyProcessor:
    """Processor for loading employee novelties."""

    def __init__(self, novelty_repository: NoveltyRepository):
        self.novelty_repo = novelty_repository

    def load_novelties(
        self, empleado: Empleado, periodo_inicio: date, periodo_fin: date, nomina_id: str | None = None
    ) -> dict[str, Decimal]:
        """Load novelties for the employee in this period."""
        novedades, _, _ = self.load_novelties_with_absences(empleado, periodo_inicio, periodo_fin, nomina_id=nomina_id)
        return novedades

    def load_novelties_with_absences(
        self, empleado: Empleado, periodo_inicio: date, periodo_fin: date, nomina_id: str | None = None
    ) -> tuple[dict[str, Decimal], dict[str, Decimal], set[str]]:
        """Load novelties and summarize absence units for the employee in this period."""
        novedades: dict[str, Decimal] = {}
        ausencia_resumen = {"dias": Decimal("0.00"), "horas": Decimal("0.00")}
        codigos_descuento: set[str] = set()

        nomina_novedades = self.novelty_repo.get_by_employee_and_period(
            empleado.id, periodo_inicio, periodo_fin, nomina_id=nomina_id
        )

        for novedad in nomina_novedades:
            codigo = novedad.codigo_concepto
            valor = Decimal(str(novedad.valor_cantidad or 0))
            if valor < 0:
                valor = Decimal("0.00")
            novedades[codigo] = novedades.get(codigo, Decimal("0")) + valor

            if novedad.es_inasistencia and novedad.descontar_pago_inasistencia:
                codigos_descuento.add(codigo)
                if novedad.tipo_valor == "dias":
                    ausencia_resumen["dias"] += valor
                elif novedad.tipo_valor == "horas":
                    ausencia_resumen["horas"] += valor

        return novedades, ausencia_resumen, codigos_descuento
