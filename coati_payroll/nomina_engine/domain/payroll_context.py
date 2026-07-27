# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Payroll execution context - immutable domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..results.validation_result import ValidationResult


@dataclass(frozen=True)
class PayrollContext:
    """Context for payroll execution.

    Note: While the dataclass is frozen (field reassignment raises AttributeError),
    the errors and warnings lists are mutable. Append operations are allowed for
    collecting validation results during processing.
    """

    planilla_id: str
    periodo_inicio: date
    periodo_fin: date
    fecha_calculo: date
    usuario: Optional[str] = None
    excluded_nomina_id: Optional[str] = None
    validation_result: "ValidationResult | None" = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize default validation_result if None."""
        if self.validation_result is None:
            from ..results.validation_result import ValidationResult

            object.__setattr__(self, "validation_result", ValidationResult())
