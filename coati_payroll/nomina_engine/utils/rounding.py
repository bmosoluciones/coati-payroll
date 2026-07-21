# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Centralized rounding helpers for monetary values."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from coati_payroll.model import Moneda


def round_money(amount: Decimal | None, moneda: Moneda | None = None) -> Decimal:  # noqa: ARG001
    """Round monetary amounts using the accounting policy.

    Args:
        amount: The amount to round.
        moneda: Optional currency (reserved for future policy variations).

    Returns:
        Rounded Decimal value with 2 decimal places.
    """
    if amount is None:
        return Decimal("0.00")
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
