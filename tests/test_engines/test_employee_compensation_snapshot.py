# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Regression tests for immutable employee compensation inputs."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from coati_payroll.nomina_engine.services.payroll_execution_service import PayrollExecutionService
from coati_payroll.nomina_engine.validators.employee_validator import EmployeeValidator


def test_recalculation_resolves_salary_and_currency_from_employee_snapshot():
    """A later salary/currency change cannot alter an old payroll calculation."""
    employee = SimpleNamespace(salario_base=Decimal("2500.00"), moneda_id="moneda-nueva")

    salary, currency_id = PayrollExecutionService._employee_snapshot_values(
        employee,
        {"salario_base": "1500.00", "moneda_id": "moneda-historica"},
    )

    assert salary == Decimal("1500.00")
    assert currency_id == "moneda-historica"


def test_historical_recalculation_accepts_an_employee_deactivated_after_payroll():
    """Termination after the period must not invalidate its historical rerun."""
    employee = SimpleNamespace(
        activo=False,
        codigo_empleado="E-1",
        fecha_alta=date(2024, 1, 1),
        fecha_baja=None,
        identificacion_personal="ID-1",
        salario_base=Decimal("0.00"),
        empresa_id="empresa-1",
        moneda_id=None,
    )

    result = EmployeeValidator().validate_employee(
        employee,
        "empresa-1",
        date(2025, 1, 1),
        date(2025, 1, 31),
        allow_historical_inactive=True,
        salario_base_override=Decimal("1500.00"),
        moneda_id_override="moneda-historica",
    )

    assert result.is_valid
