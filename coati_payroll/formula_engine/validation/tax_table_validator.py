# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tax table validation for formula engine."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from decimal import Decimal
from typing import Any

# <-------------------------------------------------------------------------> #
# Third party packages
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from ..ast.type_converter import to_decimal
from ..exceptions import ValidationError


class TaxTableValidator:
    """Validates tax tables for integrity."""

    def __init__(self, strict_mode: bool = False):
        """Initialize validator.

        Args:
            strict_mode: If True, warnings are treated as errors
        """
        self.strict_mode = strict_mode

    def validate_table(self, table_name: str, table: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        """Validate a tax table for critical integrity issues.

        Args:
            table_name: Name of the tax table being validated
            table: List of tax bracket dictionaries

        Returns:
            Tuple of (errors, warnings) lists

        Raises:
            ValidationError: If table has critical errors
        """
        errors: list[str] = []
        warnings: list[str] = []

        if not table:
            raise ValidationError(
                f"La tabla de impuestos '{table_name}' está vacía. " "Debe contener al menos un tramo."
            )

        # Validate each bracket structure
        for i, bracket in enumerate(table):
            if not isinstance(bracket, dict):
                raise ValidationError(f"El tramo {i} de la tabla '{table_name}' debe ser un diccionario")

            min_val = bracket.get("min")
            max_val = bracket.get("max")

            if min_val is None:
                raise ValidationError(f"El tramo {i} de la tabla '{table_name}' debe tener un valor 'min'")

            try:
                min_decimal = to_decimal(min_val)
            except ValidationError as e:
                raise ValidationError(
                    f"El valor 'min' del tramo {i} de la tabla '{table_name}' es inválido: {e}"
                ) from e

            if max_val is not None:
                try:
                    max_decimal = to_decimal(max_val)
                    if max_decimal < min_decimal:
                        raise ValidationError(
                            f"El tramo {i} de la tabla '{table_name}' tiene 'max' ({max_val}) "
                            f"menor que 'min' ({min_val}). El límite superior debe ser mayor o igual al inferior."
                        )
                except ValidationError as e:
                    raise ValidationError(
                        f"El valor 'max' del tramo {i} de la tabla '{table_name}' es inválido: {e}"
                    ) from e

            # Validate fixed and over values
            fixed = bracket.get("fixed", 0)
            over = bracket.get("over", 0)
            rate = bracket.get("rate", 0)

            try:
                fixed_decimal = to_decimal(fixed)
                over_decimal = to_decimal(over)
                rate_decimal = to_decimal(rate)

                if fixed_decimal < 0:
                    errors.append(
                        f"El tramo {i} de la tabla '{table_name}' tiene 'fixed' negativo ({fixed}). "
                        "El valor 'fixed' no puede ser negativo."
                    )

                if over_decimal < 0:
                    errors.append(
                        f"El tramo {i} de la tabla '{table_name}' tiene 'over' negativo ({over}). "
                        "El valor 'over' no puede ser negativo."
                    )

                if over_decimal > min_decimal:
                    errors.append(
                        f"El tramo {i} de la tabla '{table_name}' tiene 'over' ({over}) mayor que 'min' ({min_val}). "
                        "El valor 'over' debe ser menor o igual a 'min'."
                    )

                if rate_decimal < 0:
                    errors.append(
                        f"El tramo {i} de la tabla '{table_name}' tiene 'rate' negativo ({rate}). "
                        "El valor 'rate' no puede ser negativo."
                    )

                if rate_decimal > Decimal("1"):
                    errors.append(
                        f"El tramo {i} de la tabla '{table_name}' tiene 'rate' ({rate}) mayor que 1. "
                        "El valor 'rate' debe expresarse como fracción decimal entre 0 y 1 "
                        "(por ejemplo, 0.15 para el 15%)."
                    )
            except ValidationError as e:
                errors.append(f"Valores inválidos en tramo {i} de tabla '{table_name}': {e}")

        # Validate ordering and overlaps
        for i in range(len(table) - 1):
            current = table[i]
            next_bracket = table[i + 1]

            current_min = to_decimal(current.get("min", 0))
            current_max = current.get("max")
            next_min = to_decimal(next_bracket.get("min", 0))

            # Check ordering: next bracket's min should be >= current bracket's min
            if next_min < current_min:
                raise ValidationError(
                    f"La tabla de impuestos '{table_name}' no está ordenada. "
                    f"El tramo {i + 1} tiene 'min'={next_min} que es menor que el 'min'={current_min} "
                    f"del tramo {i}. Los tramos deben estar ordenados de menor a mayor."
                )

            # Check for overlaps and gaps
            if current_max is not None:
                current_max_decimal = to_decimal(current_max)

                # Check for overlap or gap
                if current_max_decimal > next_min:
                    # Overlap detected
                    overlap_start = next_min
                    overlap_end = current_max_decimal
                    raise ValidationError(
                        f"La tabla de impuestos '{table_name}' tiene tramos solapados. "
                        f"Los tramos {i} y {i + 1} se solapan en el rango [{overlap_start}, {overlap_end}]. "
                        f"El tramo {i} termina en {current_max_decimal} y el tramo {i + 1} comienza en {next_min}. "
                        "Los tramos no deben solaparse."
                    )
                if current_max_decimal < next_min:
                    # Check for significant gap
                    gap_size = next_min - current_max_decimal
                    tolerance = Decimal("0.01")  # Allow 1 cent gap for rounding

                    if gap_size > tolerance:
                        warnings.append(
                            f"La tabla de impuestos '{table_name}' tiene un gap significativo entre "
                            f"los tramos {i} y {i + 1}. "
                            f"El tramo {i} termina en {current_max_decimal} y el tramo {i + 1} comienza en {next_min}. "
                            f"Hay un gap de {gap_size} que no está cubierto por ningún tramo."
                        )
            else:
                # Current bracket is open-ended, but there's a next bracket - this is an error
                raise ValidationError(
                    f"La tabla de impuestos '{table_name}' tiene un tramo abierto (sin 'max') en la posición {i}, "
                    f"pero hay tramos adicionales después. El tramo abierto debe ser el último de la tabla."
                )

        # Validate that only the last bracket can be open-ended
        for i in range(len(table) - 1):
            if table[i].get("max") is None:
                raise ValidationError(
                    f"La tabla de impuestos '{table_name}' tiene un tramo abierto (sin 'max') en la posición {i}, "
                    "pero no es el último tramo. Solo el último tramo puede ser abierto."
                )

        # Raise errors if any critical errors found
        if errors:
            raise ValidationError(f"Errores críticos en la tabla de impuestos '{table_name}': {'; '.join(errors)}")

        return errors, warnings

    def validate_all(self, tax_tables: dict[str, Any]) -> list[str]:
        """Validate all tax tables in the schema.

        Args:
            tax_tables: Dictionary of tax table names to table definitions

        Returns:
            List of warning messages (non-critical issues)

        Raises:
            ValidationError: If any tax table has critical validation errors
        """
        if not isinstance(tax_tables, dict):
            raise ValidationError("'tax_tables' debe ser un diccionario")

        all_warnings: list[str] = []

        for table_name, table in tax_tables.items():
            if not isinstance(table, list):
                raise ValidationError(f"La tabla de impuestos '{table_name}' debe ser una lista de tramos")

            _, warnings = self.validate_table(table_name, table)
            all_warnings.extend(warnings)

        return all_warnings
