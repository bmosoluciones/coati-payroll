# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Regression tests for immutable employee compensation inputs."""

from decimal import Decimal
from types import SimpleNamespace

from coati_payroll.nomina_engine.services.payroll_execution_service import PayrollExecutionService


def test_recalculation_resolves_salary_and_currency_from_employee_snapshot():
    """A later salary/currency change cannot alter an old payroll calculation."""
    employee = SimpleNamespace(salario_base=Decimal("2500.00"), moneda_id="moneda-nueva")

    salary, currency_id = PayrollExecutionService._employee_snapshot_values(
        employee,
        {"salario_base": "1500.00", "moneda_id": "moneda-historica"},
    )

    assert salary == Decimal("1500.00")
    assert currency_id == "moneda-historica"
