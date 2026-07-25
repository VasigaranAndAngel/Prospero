import pytest

from providers.calculator_provider.nl_calc.arithmetic_split_method import (
    ArithmeticEvalError,
    evaluator,
)


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("2**2", 4),
        ("2.0**2.0", 4),
        ("2 * 5", 10),
        ("2.4 * 1", 2.4),
        ("2 * -2", -4),
        ("-2 * -2", 4),
        ("4 / 2", 2),
        ("5 / 1", 5),
        ("-5 / 1", -5),
        ("5 + 5", 10),
        ("-5 + -5", -10),
        ("5 + 5 + 5", 15),
    ],
)
def test_exponential(expression: str, expected: int | float) -> None:
    assert evaluator(expression) == expected


@pytest.mark.parametrize(
    "expression, expected", [("(5 + 5", 10), ("(2 - (2)", 0), ("(5 * 5 - (2*2)", 21)]
)
def test_parenthesis(expression: str, expected: int | float) -> None:
    assert evaluator(expression) == expected


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("2 + 2", 4),
        ("10 - 4", 6),
        ("6 * 7", 42),
        ("20 / 4", 5),
        ("10 % 3", 1),
    ],
)
def test_basic_ops(expression: str, expected: int | float):
    assert evaluator(expression) == expected


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("(((2) + 2) + 2)", 6),
        ("2 + 2 * (3 - 1)", 6),
        ("(2 + 2) * (3 - 1)", 8),
    ],
)
def test_precedence_and_grouping(expression: str, expected: int | float):
    assert evaluator(expression) == expected


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("2 ^ 10", 1024),
        ("2 ** 10", 1024),
        ("2 ^ 3 ^ 2", 512),
    ],
)
def test_exponents(expression: str, expected: int | float):
    assert evaluator(expression) == expected


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("-5 + 3", -2),
        ("-(3 + 4)", -7),
        ("3 + -4", -1),
        ("3 - -4", 7),
        ("2 * -3", -6),
    ],
)
def test_unary_minus(expression: str, expected: int | float):
    assert evaluator(expression) == expected


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("sqrt 16", 4),
        ("abs -5", 5),
        ("round 3.14159", pytest.approx(3)),
        ("min 3, 5, 2", 2),
        ("max 3, 5, 2, 9, 1", 9),
        ("log 100", pytest.approx(4.605, abs=2e-4)),
        ("log 8, 2", pytest.approx(3)),
        ("sin 0", 0),
    ],
)
def test_functions(expression: str, expected: int | float):
    assert evaluator(expression) == expected


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("pi", pytest.approx(3.14159265, rel=1e-6)),
        ("e", pytest.approx(2.71828182, rel=1e-6)),
    ],
)
def test_constants(expression: str, expected: int | float):
    assert evaluator(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        # ("2 * (3 + 4"),
        # ("(2+3))"),
        (""),
        ("5 / 0"),
        ("bogus 5"),
    ],
)
def test_errors(expression: str):
    with pytest.raises(ArithmeticEvalError):
        _ = evaluator(expression)


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("1%", 0.01),
        ("1 * 10%", 0.1),
        ("10 * 10%", 1),
    ],
)
def test_percentage(expression: str, expected: float | int) -> None:
    res = evaluator(expression)
    assert res == expected
