# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Helpers for recurring fiscal-calendar dates."""

from calendar import monthrange
from datetime import date


def fiscal_start_date(year: int, month: int, day: int) -> date:
    """Return a valid recurring fiscal start date for ``year``.

    A configured day can be valid in its original year but not in every
    subsequent year (notably February 29). Such recurring anniversaries use
    the last day of the target month instead of failing payroll processing.
    """
    return date(year, month, min(day, monthrange(year, month)[1]))
