# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Regression tests for exchange-rate safeguards in payroll calculations."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from coati_payroll.nomina_engine.calculators.exchange_rate_calculator import ExchangeRateCalculator
from coati_payroll.nomina_engine.validators import CalculationError


class StubExchangeRateRepository:
    """Minimal repository stub with a configurable persisted rate."""

    def __init__(self, rate):
        self.rate = rate

    def get_rate(self, *_args):
        return self.rate


@pytest.mark.parametrize("rate", [Decimal("0"), Decimal("-3.5")])
def test_payroll_rejects_non_positive_persisted_exchange_rates(rate):
    """A zero/negative master rate must not zero or invert an employee salary."""
    calculator = ExchangeRateCalculator(StubExchangeRateRepository(rate))
    employee = SimpleNamespace(
        moneda_id="usd",
        moneda=SimpleNamespace(codigo="USD"),
        primer_nombre="Ana",
        primer_apellido="Prueba",
    )
    planilla = SimpleNamespace(moneda_id="nio", moneda=SimpleNamespace(codigo="NIO"))

    with pytest.raises(CalculationError, match="debe ser mayor que cero"):
        calculator.get_exchange_rate(employee, planilla, date(2026, 1, 1))


def test_payroll_rejects_non_positive_snapshot_exchange_rate():
    """Recalculation must validate frozen rates just as it validates live rates."""
    calculator = ExchangeRateCalculator(StubExchangeRateRepository(Decimal("1.00")))
    employee = SimpleNamespace(
        moneda_id="usd",
        moneda=SimpleNamespace(codigo="USD"),
        primer_nombre="Ana",
        primer_apellido="Prueba",
    )
    planilla = SimpleNamespace(moneda_id="nio", moneda=SimpleNamespace(codigo="NIO"))
    snapshot = {"usd": {"tasa": "0", "moneda_destino_id": "nio"}}

    with pytest.raises(CalculationError, match="debe ser mayor que cero"):
        calculator.get_exchange_rate(employee, planilla, date(2026, 1, 1), snapshot)
