# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Exchange rate calculator for payroll processing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from coati_payroll.model import Empleado, Planilla
from ..repositories.exchange_rate_repository import ExchangeRateRepository


class ExchangeRateCalculator:
    """Calculator for exchange rates."""

    def __init__(self, exchange_rate_repository: ExchangeRateRepository):
        self.exchange_rate_repo = exchange_rate_repository

    def get_exchange_rate(
        self,
        empleado: Empleado,
        planilla: Planilla,
        fecha_calculo: date,
        tipos_cambio_snapshot: dict[str, Any] | None = None,
    ) -> Decimal:
        """Get exchange rate for employee's currency to planilla currency."""
        if not empleado.moneda_id:
            return Decimal("1.00")

        if empleado.moneda_id == planilla.moneda_id:
            return Decimal("1.00")

        if tipos_cambio_snapshot:
            snapshot_rate = tipos_cambio_snapshot.get(empleado.moneda_id)
            if snapshot_rate and snapshot_rate.get("tasa"):
                # Validate that the snapshot rate is for the correct destination currency
                snapshot_dest = snapshot_rate.get("moneda_destino_id")
                if snapshot_dest and snapshot_dest != planilla.moneda_id:
                    pass  # Wrong destination — fall through to DB lookup
                else:
                    return Decimal(str(snapshot_rate["tasa"]))

        rate = self.exchange_rate_repo.get_rate(empleado.moneda_id, planilla.moneda_id, fecha_calculo)
        if rate is None:
            from ..validators import CalculationError

            raise CalculationError(
                f"No se encontró tipo de cambio para empleado "
                f"{empleado.primer_nombre} {empleado.primer_apellido}. "
                f"Se requiere un tipo de cambio de {empleado.moneda.codigo if empleado.moneda else 'desconocido'} "
                f"a {planilla.moneda.codigo if planilla.moneda else 'desconocido'} "
                f"para la fecha {fecha_calculo.strftime('%d/%m/%Y')}."
            )

        return Decimal(str(rate))
