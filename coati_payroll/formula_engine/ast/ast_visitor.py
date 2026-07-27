# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""AST Visitor pattern for safe expression evaluation.

This module implements a secure AST visitor that evaluates mathematical expressions
without using dynamic method dispatch (getattr). All node types are explicitly
handled to prevent any possibility of code injection or unexpected behavior.

Security Features:
- Explicit visitor methods for each allowed node type
- No dynamic method resolution (no getattr/setattr)
- Whitelist-based approach - unknown nodes are rejected
- All operations maintain Decimal precision
- Division by zero is handled safely

The visitor pattern ensures that only pre-approved AST node types can be processed,
and each type has an explicit, auditable handler method.
"""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
import ast
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

# <-------------------------------------------------------------------------> #
# Third party packages
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from ..exceptions import CalculationError, ValidationError
from .safe_operators import SAFE_FUNCTIONS, SAFE_OPERATORS
from .type_converter import to_decimal


class ASTVisitor(ABC):
    """Visitor pattern base class for AST traversal.

    This abstract base class defines the interface for AST visitors.
    Implementations must provide a visit() method that safely evaluates
    AST nodes and returns Decimal results.
    """

    @abstractmethod
    def visit(self, node: ast.AST) -> Any:  # Changed from Decimal to Any
        """Visit and evaluate an AST node.

        Args:
            node: The AST node to visit and evaluate

        Returns:
            The evaluated result (Decimal, date, or other supported type)

        Raises:
            CalculationError: If the node cannot be safely evaluated
        """


class SafeASTVisitor(ASTVisitor):
    """Safe visitor for evaluating mathematical expressions.

    This visitor implements a secure evaluation strategy:
    1. Explicit dispatch - no dynamic method resolution
    2. Whitelist approach - only known node types are processed
    3. Immutable context - variables are read-only during evaluation
    4. Decimal precision - all numeric operations maintain precision
    5. Safe error handling - division by zero returns 0

    Security Note:
    This class does NOT use getattr() or any dynamic dispatch mechanism.
    All node types are handled by explicit if/elif chains to prevent
    any possibility of method injection or unexpected behavior.
    """

    def __init__(self, variables: dict[str, Decimal], strict_mode: bool = False):
        """Initialize visitor with variable context.

        Args:
            variables: Dictionary of variable names to Decimal values.
                      This dictionary is not modified during evaluation.
            strict_mode: If True, raises CalculationError on division by zero.
                        If False, returns Decimal("0") for backward compatibility.
        """
        self.variables = variables
        self.strict_mode = strict_mode

    def visit(self, node: ast.AST) -> Any:  # Changed from Decimal to Any
        """Visit and evaluate an AST node using explicit dispatch.

        This method uses explicit type checking with match/case instead of
        dynamic method resolution (getattr) for security and maintainability.
        Each node type is explicitly handled, making the code easier to audit
        and preventing any possibility of method injection.

        Args:
            node: AST node to evaluate

        Returns:
            Result of evaluation (Decimal for numbers, date for dates, etc.)

        Raises:
            CalculationError: If the node type is not supported or evaluation fails
        """
        match node:
            case ast.Constant():
                return self.visit_constant(node)
            case ast.Name():
                return self.visit_name(node)
            case ast.BinOp():
                return self.visit_binop(node)
            case ast.UnaryOp():
                return self.visit_unaryop(node)
            case ast.Call():
                return self.visit_call(node)
            case _:
                raise CalculationError(
                    f"Unsupported AST node type: {type(node).__name__}. "
                    "Only Constant, Name, BinOp, UnaryOp, and Call nodes are allowed."
                )

    def visit_constant(self, node: ast.Constant) -> Any:
        """Visit a constant node (numeric literal or string/boolean/None).

        Args:
            node: AST Constant node

        Returns:
            The constant value as a Decimal (if numeric/boolean), or as-is (if string/None)

        Raises:
            CalculationError: If the constant cannot be converted to Decimal when expected
        """
        val = node.value
        if isinstance(val, (int, float)):
            return to_decimal(val)
        if isinstance(val, bool):
            return to_decimal(val)
        if val is None:
            return None
        if isinstance(val, str):
            # Try to convert to Decimal if it's a numeric string, otherwise keep as string
            try:
                return to_decimal(val)
            except ValidationError:
                return val
        # Any other type (like list or dict if constructible) should be passed to to_decimal to raise ValidationError
        return to_decimal(val)

    def visit_name(self, node: ast.Name) -> Any:  # Changed from Decimal to Any
        """Visit a variable name node.

        Args:
            node: AST Name node representing a variable reference

        Returns:
            The value of the variable from the context (can be Decimal, date, string, etc.)

        Raises:
            CalculationError: If the variable is not defined in the context
        """
        if node.id not in self.variables:
            raise CalculationError(
                f"Undefined variable: '{node.id}'. Available variables: {', '.join(sorted(self.variables.keys()))}"
            )
        return self.variables[node.id]

    def visit_binop(self, node: ast.BinOp) -> Decimal:
        """Visit a binary operation node (e.g., a + b, x * y).

        Args:
            node: AST BinOp node representing a binary operation

        Returns:
            The result of the binary operation as a Decimal

        Raises:
            CalculationError: If the operator is not whitelisted or operation fails
        """
        left = self.visit(node.left)
        right = self.visit(node.right)

        op_type = type(node.op)
        op_func = SAFE_OPERATORS.get(op_type)
        if not op_func:
            raise CalculationError(
                f"Operator '{op_type.__name__}' is not allowed. Allowed operators: +, -, *, /, //, %, **"
            )

        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            if self.strict_mode:
                raise CalculationError("Division by zero detected while evaluating expression.")
            return Decimal("0")

        try:
            result = op_func(left, right)
            return to_decimal(result)
        except (OverflowError, ValueError) as e:
            raise CalculationError(f"Arithmetic error in operation '{left} {op_type.__name__} {right}': {e}") from e
        except Exception as e:
            raise CalculationError(f"Unexpected error in binary operation: {e}") from e

    def visit_unaryop(self, node: ast.UnaryOp) -> Decimal:
        """Visit a unary operation node (e.g., -x, +y).

        Args:
            node: AST UnaryOp node representing a unary operation

        Returns:
            The result of the unary operation as a Decimal

        Raises:
            CalculationError: If the unary operator is not allowed
        """
        operand = self.visit(node.operand)

        op_type = type(node.op)
        if op_type == ast.UAdd:
            return to_decimal(+operand)
        if op_type == ast.USub:
            return to_decimal(-operand)
        raise CalculationError(
            f"Unary operator '{op_type.__name__}' is not allowed. " "Only unary + and - are permitted."
        )

    def visit_call(self, node: ast.Call) -> Any:  # Changed return type from Decimal to Any
        """Visit a function call node (e.g., max(a, b), round(x, 2)).

        Args:
            node: AST Call node representing a function call

        Returns:
            The result of the function call (Decimal for math functions, date for date functions)

        Raises:
            CalculationError: If the function is not whitelisted or call fails
        """
        if not isinstance(node.func, ast.Name):
            raise CalculationError(
                "Only direct named function calls are allowed. Attribute access and lambda functions are prohibited."
            )

        func_name = node.func.id
        if func_name not in SAFE_FUNCTIONS:
            raise CalculationError(
                f"Function '{func_name}' is not in the whitelist. "
                f"Allowed functions: {', '.join(sorted(SAFE_FUNCTIONS.keys()))}"
            )

        if node.keywords:
            raise CalculationError(
                f"Keyword arguments are not allowed in function '{func_name}'. " "Use positional arguments only."
            )

        args = [self.visit(arg) for arg in node.args]

        try:
            if func_name == "round" and len(args) > 1:
                # Validate that precision is an exact integer
                if args[1] != args[1].to_integral_value():
                    raise CalculationError(f"round() precision must be an integer, got {args[1]}")
                prec = int(args[1])
                if prec < 0 or prec > 10:
                    raise CalculationError(f"round() precision must be between 0 and 10, got {prec}")
                result = SAFE_FUNCTIONS[func_name](args[0], prec)
            else:
                result = SAFE_FUNCTIONS[func_name](*args)

            # For date functions, return as-is. For numeric functions, convert to Decimal
            if func_name in ("days_between", "max_date", "min_date"):
                return result
            return to_decimal(result)
        except TypeError as e:
            raise CalculationError(f"Invalid arguments for function '{func_name}': {e}") from e
        except ValueError as e:
            raise CalculationError(f"Invalid value in function '{func_name}': {e}") from e
        except Exception as e:
            raise CalculationError(f"Error calling function '{func_name}': {e}") from e
