# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Execution result DTO."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

# <-------------------------------------------------------------------------> #
# Third party packages
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #


class ExecutionResult:
    """Result of formula execution."""

    def __init__(
        self,
        variables: dict[str, Any],  # Changed from Decimal to Any
        step_results: dict[str, Any],
        final_output: Any,  # Changed from Decimal to Any
    ):
        self.variables = variables
        self.step_results = step_results
        self.final_output = final_output

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary format with 2 decimal places rounding."""
        return {
            "variables": self._process_value(self.variables),
            "results": self._process_value(self.step_results),
            "output": self._process_value(self.final_output),
        }

    @staticmethod
    def _process_value(value: Any) -> Any:
        """Round decimals while preserving nested result structures."""
        if isinstance(value, Decimal):
            rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return format(rounded, "f")
        if isinstance(value, dict):
            return {key: ExecutionResult._process_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [ExecutionResult._process_value(item) for item in value]
        return value
