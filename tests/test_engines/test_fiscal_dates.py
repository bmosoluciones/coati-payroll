# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Regression tests for recurring fiscal calendar dates."""

from datetime import date

from coati_payroll.nomina_engine.utils.fiscal import fiscal_start_date


def test_fiscal_start_uses_last_day_for_leap_day_in_non_leap_year():
    """A Feb-29 fiscal configuration must remain processable every year."""
    assert fiscal_start_date(2024, 2, 29) == date(2024, 2, 29)
    assert fiscal_start_date(2025, 2, 29) == date(2025, 2, 28)
