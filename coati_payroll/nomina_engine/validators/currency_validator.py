# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Validator for currency and exchange rates."""

from __future__ import annotations

from datetime import date

from ..domain.payroll_context import PayrollContext
from ..results.validation_result import ValidationResult
from ..validators.base_validator import BaseValidator
from ..repositories.exchange_rate_repository import ExchangeRateRepository


class CurrencyValidator(BaseValidator):
    """Validates currency and exchange rate availability."""

    def __init__(self, exchange_rate_repository: ExchangeRateRepository):
        self.exchange_rate_repo = exchange_rate_repository

    def validate(self, context: PayrollContext) -> ValidationResult:
        """Validate currency - this is a placeholder as currency validation is done per-employee."""
        result = ValidationResult()
        return result

    def validate_exchange_rate(self, moneda_origen_id: str, moneda_destino_id: str, fecha: date) -> ValidationResult:
        """Validate that exchange rate exists for currency pair and is positive."""
        result = ValidationResult()

        if moneda_origen_id == moneda_destino_id:
            return result  # Same currency, no exchange rate needed

        rate = self.exchange_rate_repo.get_rate(moneda_origen_id, moneda_destino_id, fecha)
        if rate is None:
            result.add_error(
                f"No se encontró tipo de cambio de {moneda_origen_id} a {moneda_destino_id} para la fecha {fecha}"
            )
        elif rate <= 0:
            result.add_error(
                f"Tipo de cambio inválido de {moneda_origen_id} a {moneda_destino_id}: {rate} "
                f"(debe ser un valor positivo)"
            )

        return result
