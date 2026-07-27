# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Repository for Exchange Rate operations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from coati_payroll.model import TipoCambio
from .base_repository import BaseRepository


class ExchangeRateRepository(BaseRepository[TipoCambio]):
    """Repository for TipoCambio operations."""

    def get_by_id(self, tipo_cambio_id: str) -> Optional[TipoCambio]:
        """Get exchange rate by ID."""
        return self.session.get(TipoCambio, tipo_cambio_id)

    def get_rate(self, moneda_origen_id: str, moneda_destino_id: str, fecha: date) -> Optional[Decimal]:
        """Get exchange rate for currency pair on or before given date."""
        from sqlalchemy import select

        tipo_cambio = (
            self.session.execute(
                select(TipoCambio)
                .filter(
                    TipoCambio.moneda_origen_id == moneda_origen_id,
                    TipoCambio.moneda_destino_id == moneda_destino_id,
                    TipoCambio.fecha <= fecha,
                )
                .order_by(TipoCambio.fecha.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

        if tipo_cambio:
            return Decimal(str(tipo_cambio.tasa))
        return None

    def save(self, tipo_cambio: TipoCambio) -> TipoCambio:
        """Save exchange rate."""
        self.session.add(tipo_cambio)
        return tipo_cambio
