"""Quick test script to verify AST security improvements."""

from decimal import Decimal
from coati_payroll.formula_engine.ast import ExpressionEvaluator
from coati_payroll.formula_engine.exceptions import CalculationError


def test_basic_operations():
    """Test basic arithmetic operations."""
    print("Testing basic operations...")
    variables = {"a": Decimal("10"), "b": Decimal("5"), "c": Decimal("2")}

    evaluator = ExpressionEvaluator(variables)

    tests = [
        ("a + b", Decimal("15")),
        ("a - b", Decimal("5")),
        ("a * b", Decimal("50")),
        ("a / b", Decimal("2")),
        ("a // b", Decimal("2")),
        ("a % b", Decimal("0")),
        ("a ** c", Decimal("100")),
        ("-a", Decimal("-10")),
        ("+b", Decimal("5")),
    ]

    for expr, expected in tests:
        result = evaluator.evaluate(expr)
        assert result == expected, f"Failed: {expr} = {result}, expected {expected}"
        print(f"  ✓ {expr} = {result}")

    print("✓ Basic operations passed\n")


def test_safe_functions():
    """Test whitelisted functions."""
    print("Testing safe functions...")
    variables = {"x": Decimal("10"), "y": Decimal("5"), "z": Decimal("3.14159")}

    evaluator = ExpressionEvaluator(variables)

    tests = [
        ("max(x, y)", Decimal("10")),
        ("min(x, y)", Decimal("5")),
        ("abs(-x)", Decimal("10")),
        ("round(z, 2)", Decimal("3.14")),
    ]

    for expr, expected in tests:
        result = evaluator.evaluate(expr)
        assert result == expected, f"Failed: {expr} = {result}, expected {expected}"
        print(f"  ✓ {expr} = {result}")

    print("✓ Safe functions passed\n")


def test_security_violations():
    """Test that unsafe operations are rejected."""
    print("Testing security violations...")
    variables = {"x": Decimal("10")}
    evaluator = ExpressionEvaluator(variables)

    unsafe_expressions = [
        '__import__("os").system("echo hacked")',
        'open("/etc/passwd").read()',
        "[x for x in range(100)]",
        "lambda: x",
        "x.__class__",
        'eval("1+1")',
        'exec("print(1)")',
    ]

    for expr in unsafe_expressions:
        try:
            evaluator.evaluate(expr)
            print(f"  ✗ SECURITY FAILURE: {expr} was not rejected!")
            assert False, f"Security violation not caught: {expr}"
        except (CalculationError, SyntaxError):
            print(f"  ✓ Rejected: {expr[:50]}...")

    print("✓ Security violations properly rejected\n")


def test_division_by_zero():
    """Test safe division by zero handling."""
    print("Testing division by zero...")
    variables = {"x": Decimal("10"), "zero": Decimal("0")}
    evaluator = ExpressionEvaluator(variables)

    result = evaluator.evaluate("x / zero")
    assert result == Decimal("0"), f"Expected 0, got {result}"
    print(f"  ✓ x / zero = {result} (safe handling)")

    print("✓ Division by zero handled safely\n")


def test_undefined_variable():
    """Test undefined variable error."""
    print("Testing undefined variable...")
    variables = {"x": Decimal("10")}
    evaluator = ExpressionEvaluator(variables)

    try:
        evaluator.evaluate("x + undefined_var")
        print("  ✗ Undefined variable not caught!")
        assert False
    except CalculationError as e:
        if "undefined" in str(e).lower():
            print(f"  ✓ Undefined variable caught: {str(e)[:60]}...")
        else:
            raise

    print("✓ Undefined variable properly handled\n")


if __name__ == "__main__":
    print("=" * 70)
    print("AST Security Test Suite")
    print("=" * 70 + "\n")

    try:
        test_basic_operations()
        test_safe_functions()
        test_security_violations()
        test_division_by_zero()
        test_undefined_variable()

        print("=" * 70)
        print("✓ ALL TESTS PASSED - AST Security is working correctly!")
        print("=" * 70)
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"✗ TEST FAILED: {e}")
        print("=" * 70)
        raise
