# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Centralized rounding helpers for monetary values."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def round_money(amount: Decimal | int | float | str | None) -> Decimal:
    """Round monetary amounts using the accounting policy.

    Args:
        amount: The amount to round. Accepts Decimal, int, float, str, or None.
            None raises ValueError to surface upstream data issues rather than
            silently producing zero-amount paystubs.
    Returns:
        Rounded Decimal value with 2 decimal places.
    """
    if amount is None:
        raise ValueError("round_money() received None — upstream data is missing a monetary value")
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
