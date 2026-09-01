# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Main formula engine facade."""

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
from coati_payroll.i18n import _
from coati_payroll.log import TRACE_LEVEL_NUM, is_trace_enabled, log

from ..formula_engine.data_sources import AVAILABLE_DATA_SOURCES, get_formula_variable_name
from .ast.type_converter import to_decimal
from .exceptions import ValidationError
from .execution.execution_context import ExecutionContext
from .execution.step_executor import StepExecutor
from .execution.variable_store import VariableStore
from .results.execution_result import ExecutionResult
from .steps.step_factory import StepFactory
from .validation.schema_validator import SchemaValidator
from .validation.tax_table_validator import TaxTableValidator


class FormulaEngine:
    """Engine for executing JSON-based calculation rules for payroll.

    This engine provides a secure way to execute complex calculations for
    perceptions, deductions, taxes, and other payroll formulas defined in
    JSON format. It supports variables, formulas, conditionals, and rate
    table lookups.

    NOTE: Only Percepciones and Deducciones affect employee net pay.
    Prestaciones are employer costs calculated separately.
    """

    def __init__(self, schema: dict[str, Any], strict_mode: bool = True):
        """Initialize the formula engine with a calculation schema.

        Args:
            schema: JSON schema defining the calculation rules
            strict_mode: If True, warnings are treated as errors. Default: True

        Raises:
            ValidationError: If schema is invalid
        """
        self.schema = schema
        self.strict_mode = strict_mode
        # Initialize variables and results for backward compatibility with tests
        self.variables: dict[str, Decimal] = {}
        self.results: dict[str, Any] = {}

        # Validate schema
        schema_validator = SchemaValidator()
        schema_validator.validate(schema)

        # Validate tax tables
        tax_table_validator = TaxTableValidator(strict_mode)
        warnings = tax_table_validator.validate_all(schema.get("tax_tables", {}))

        # Handle warnings
        if warnings:
            if strict_mode:
                raise ValidationError(
                    f"Advertencias en tablas de impuestos (modo estricto activado): {', '.join(warnings)}"
                )
            for warning in warnings:
                log.warning("Validación de tabla de impuestos: %s", warning)

    def _trace(self, message: str) -> None:
        """Trace helper for logging."""
        if is_trace_enabled():
            try:
                log.log(TRACE_LEVEL_NUM, message)
            except Exception:
                pass

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the calculation schema with provided inputs.

        Args:
            inputs: Dictionary of input values

        Returns:
            Dictionary containing all results and the final output

        Raises:
            CalculationError: If execution fails
        """
        # Initialize components
        variable_store = VariableStore()
        step_factory = StepFactory()
        step_executor = StepExecutor()

        # Prepare initial variables
        initial_vars = self._prepare_initial_variables(inputs)
        variable_store.variables = initial_vars

        # Update instance variables for backward compatibility
        self.variables = initial_vars.copy()
        self.results = {}

        # Create execution context
        context = ExecutionContext(
            variables=initial_vars,
            tax_tables=self.schema.get("tax_tables", {}),
            strict_mode=self.strict_mode,
            trace_callback=self._trace,
        )

        meta = self.schema.get("meta", {})
        self._trace(
            _("Iniciando ejecución de esquema '%(name)s' pasos=%(count)s")
            % {"name": meta.get("name", "sin nombre"), "count": len(self.schema.get("steps", []))}
        )

        # Create and execute steps
        steps = [step_factory.create_step(step) for step in self.schema.get("steps", [])]

        step_results = {}
        for step in steps:
            result = step_executor.execute(step, context)
            step_results[step.name] = result

            # Update context with step result
            variable_value = step.get_variable_value(result)
            context = context.with_variable(step.name, variable_value)
            variable_store.set(step.name, variable_value, result)
            self.variables[step.name] = variable_value
            self.results[step.name] = result

            # A tax lookup returns the calculated tax plus the selected
            # bracket components.  Preserve each component in the execution
            # context under the step name so later formulas can reuse the
            # selected rate, fixed amount, or threshold without reimplementing
            # the lookup in an expression.
            if step.config.get("type") == "tax_lookup" and isinstance(result, dict):
                for component in ("rate", "fixed", "over"):
                    value = result.get(component)
                    if value is None:
                        continue
                    variable_name = f"{step.name}_{component}"
                    context = context.with_variable(variable_name, value)
                    variable_store.set(variable_name, value)
                    self.variables[variable_name] = value

            if context.trace_callback:
                context.trace_callback(
                    _("Resultado paso '%(name)s' => %(result)s") % {"name": step.name, "result": result}
                )

        # Get the final output
        output_name = self.schema.get("output", "")
        final_result = context.variables.get(output_name, Decimal("0"))

        self._trace(_("Resultado final '%(name)s' => %(value)s") % {"name": output_name, "value": final_result})

        # Create and return result
        execution_result = ExecutionResult(
            variables=context.variables,
            step_results=step_results,
            final_output=final_result,
        )

        return execution_result.to_dict()

    def _prepare_initial_variables(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Prepare initial variables from inputs and defaults.

        Args:
            inputs: Input values provided by caller

        Returns:
            Dictionary of variable names to values (Decimal for numbers, original type for dates/strings)
        """
        variables = {}
        for input_def in self.schema.get("inputs", []):
            name = input_def.get("name")
            default = input_def.get("default", 0)
            input_type = input_def.get("type", "decimal")

            # Get the value (from input or default)
            value = inputs.get(name, default)

            # Convert based on type
            if input_type in ("date", "string"):
                # Keep dates and strings as-is
                variables[name] = value
            else:
                # Convert numbers to Decimal
                variables[name] = to_decimal(value)

            source = "input" if name in inputs else "default"
            self._trace(
                _("Input '%(name)s' cargado desde %(source)s => %(value)s")
                % {"name": name, "source": source, "value": variables[name]}
            )

        return variables


def calculate_with_rule(
    rule_schema: dict[str, Any],
    employee_data: dict[str, Any],
    accumulated_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate using a rule schema with employee and accumulated data.

    This is a convenience function that combines employee data with
    accumulated annual data for payroll calculations.

    Args:
        rule_schema: The JSON calculation schema
        employee_data: Employee-specific data (salary, etc.)
        accumulated_data: Optional accumulated annual data

    Returns:
        Calculation results including the final output
    """
    inputs = {**employee_data}

    if accumulated_data:
        # Add accumulated values with prefix
        for key, value in accumulated_data.items():
            inputs[f"acumulado_{key}"] = value

    engine = FormulaEngine(rule_schema)
    return engine.execute(inputs)


def get_available_sources_for_ui() -> list[dict]:
    """Get available data sources formatted for the UI dropdown.

    Returns:
        List of dictionaries with source information for the schema editor
    """
    sources = []
    data_sources = AVAILABLE_DATA_SOURCES if isinstance(AVAILABLE_DATA_SOURCES, dict) else {}
    for category, data in data_sources.items():
        data_dict = data if isinstance(data, dict) else {}
        fields = data_dict.get("fields", {})
        if not isinstance(fields, dict):
            continue
        for field_name, field_info in fields.items():
            if not isinstance(field_info, dict):
                continue
            sources.append(
                {
                    "value": get_formula_variable_name(category, field_name, field_info),
                    "label": f"{data_dict.get('label', category)} - {field_info.get('label', field_name)}",
                    "type": field_info.get("type"),
                    "description": field_info.get("description"),
                    "category": category,
                }
            )
    return sources
