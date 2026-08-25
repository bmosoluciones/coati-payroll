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

        snapshot_rate = self._get_snapshot_rate(
            tipos_cambio_snapshot,
            empleado.moneda_id,
            planilla.moneda_id,
        )
        if snapshot_rate is not None:
            return self._validate_positive_rate(snapshot_rate, empleado, planilla)

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

        return self._validate_positive_rate(Decimal(str(rate)), empleado, planilla)

    @staticmethod
    def _validate_positive_rate(rate: Decimal, empleado: Empleado, planilla: Planilla) -> Decimal:
        """Reject zero or negative rates before they can corrupt payroll amounts."""
        if rate <= 0:
            from ..validators import CalculationError

            raise CalculationError(
                f"Tipo de cambio inválido para empleado {empleado.primer_nombre} {empleado.primer_apellido}: "
                f"{rate}. La tasa de {empleado.moneda.codigo if empleado.moneda else 'desconocido'} "
                f"a {planilla.moneda.codigo if planilla.moneda else 'desconocido'} debe ser mayor que cero."
            )
        return rate

    @staticmethod
    def _get_snapshot_rate(
        snapshot: dict[str, Any] | None,
        source_currency_id: str,
        destination_currency_id: str,
    ) -> Decimal | None:
        """Return a snapshot rate only when it targets the requested currency."""
        if not snapshot:
            return None

        snapshot_rate = snapshot.get(source_currency_id)
        if not snapshot_rate or not snapshot_rate.get("tasa"):
            return None

        snapshot_destination = snapshot_rate.get("moneda_destino_id")
        if snapshot_destination and snapshot_destination != destination_currency_id:
            return None

        return Decimal(str(snapshot_rate["tasa"]))
