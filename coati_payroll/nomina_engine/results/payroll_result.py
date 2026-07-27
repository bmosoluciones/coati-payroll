# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Payroll execution result DTO."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from coati_payroll.model import Nomina

if TYPE_CHECKING:
    from ..domain.employee_calculation import EmpleadoCalculo
    from ..domain.payroll_context import PayrollContext


@dataclass
class PayrollResult:
    """Result of a payroll execution."""

    context: "PayrollContext"
    nomina: Optional[Nomina] = None
    employee_calculations: list["EmpleadoCalculo"] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def add_errors(self, errors: list[str]) -> None:
        """Add multiple error messages."""
        self.errors.extend(errors)

    def set_success(self, nomina: Nomina, calculations: list["EmpleadoCalculo"]) -> None:
        """Set the result as successful, clearing any previous errors/warnings."""
        self.nomina = nomina
        self.employee_calculations = calculations
        self.errors.clear()
        self.warnings.clear()
