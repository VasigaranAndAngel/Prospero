import math

import pytest

from providers.calculator_provider.nl_calc.arithmetic_split_method import (
    ArithmeticEvalError,
    evaluator,
)


class TestBasicArithmetic:
    """Test basic arithmetic operations: +, -, *, /, %, **, ^"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2+3", 5),
            ("10+5", 15),
            ("0.5+0.5", 1.0),
            ("-5+10", 5),
            ("100+200+300", 600),
        ],
    )
    def test_addition(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("5-3", 2),
            ("10-20", -10),
            ("0.5-0.3", pytest.approx(0.2)),
            ("-5-5", -10),
            ("100-50-25", 25),
        ],
    )
    def test_subtraction(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("3*4", 12),
            ("2.5*4", 10.0),
            ("-3*4", -12),
            ("0*100", 0),
            ("2*3*4", 24),
        ],
    )
    def test_multiplication(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("10/2", 5.0),
            ("7/2", 3.5),
            ("1/3", 1 / 3),
            ("-10/2", -5.0),
            ("100/5/2", 10.0),
        ],
    )
    def test_division(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("10%3", 1),
            ("20%7", 6),
            ("5%2", 1),
            ("-10%3", 2),
        ],
    )
    def test_modulo(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2**3", 8),
            ("2^3", 8),
            ("5**2", 25),
            ("10**0", 1),
            ("2**10", 1024),
        ],
    )
    def test_exponentiation(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestOrderOfOperations:
    """Test operator precedence and associativity"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2+3*4", 14),  # multiplication before addition
            ("2*3+4", 10),
            ("10-2*3", 4),
            ("20/4+2", 7),
            ("2+3*4-1", 13),
        ],
    )
    def test_multiplication_division_before_addition_subtraction(
        self, expression: str, expected: int | float
    ):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2**3*4", 32),  # exponentiation before multiplication
            ("2*3**2", 18),
            ("2**2**2", 16),  # right associative
        ],
    )
    def test_exponentiation_precedence(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2+3+4", 9),  # left to right
            ("10-3-2", 5),
            ("100/10/2", 5.0),
        ],
    )
    def test_left_associativity(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestParentheses:
    """Test parentheses for grouping and precedence override"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("(2+3)*4", 20),
            ("2*(3+4)", 14),
            ("(10-2)*3", 24),
            ("((2+3)*4)", 20),
            ("(2+3)*(4+5)", 45),
            ("((2+3)*(4+5))", 45),
        ],
    )
    def test_parentheses_grouping(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("(2**3)**2", 64),
            ("2**(3*2)", 64),
            ("(10/5)*2", 4.0),
            ("(1+1)", 2),
            ("(min (1, 2, 3))", 1),
        ],
    )
    def test_parentheses_override_precedence(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    def test_nested_parentheses(self):
        assert evaluator("((2+3)*(4+(5*2)))") == 70


class TestMathFunctions:
    """Test built-in mathematical functions"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sqrt 4", 2.0),
            ("sqrt 9", 3.0),
            ("sqrt 2", pytest.approx(1.414213)),
            ("sqrt 0.25", 0.5),
            ("sqrt(4)", 2.0),
            ("sqrt(9)", 3.0),
            ("sqrt(2)", pytest.approx(1.414213)),
            ("sqrt(0.25)", 0.5),
        ],
    )
    def test_sqrt(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("abs -5", 5),
            ("abs 5", 5),
            ("abs -3.14", 3.14),
            ("abs 0", 0),
            ("abs(-5)", 5),
            ("abs(5)", 5),
            ("abs(-3.14)", 3.14),
            ("abs(0)", 0),
        ],
    )
    def test_abs(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("round 3.14", 3),
            ("round 3.6", 4),
            ("round 2.5", 2),
            ("round -2.5", -2),
            ("round(3.14)", 3),
            ("round(3.6)", 4),
            ("round(2.5)", 2),
            ("round(-2.5)", -2),
        ],
    )
    def test_round(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("min 3,1,4,1,5", 1),
            ("min 10,20", 10),
            ("min -5,-2,-10", -10),
            ("min 0.1,0.01", 0.01),
            ("min(3,1,4,1,5)", 1),
            ("min(10,20)", 10),
            ("min(-5,-2,-10)", -10),
            ("min(0.1,0.01)", 0.01),
        ],
    )
    def test_min(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("max 3,1,4,1,5", 5),
            ("max 10,20", 20),
            ("max -5,-2,-10", -2),
            ("max 0.1,0.01", 0.1),
            ("max(3,1,4,1,5)", 5),
            ("max(10,20)", 20),
            ("max(-5,-2,-10)", -2),
            ("max(0.1,0.01)", 0.1),
        ],
    )
    def test_max(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sum 1,2,3,4,5", 15),
            ("total 10,20,30", 60),
            ("sum 0.1,0.2,0.3", pytest.approx(0.6)),
            ("sum(1,2,3,4,5)", 15),
            ("total(10,20,30)", 60),
            ("sum(0.1,0.2,0.3)", pytest.approx(0.6)),
        ],
    )
    def test_sum_and_total(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("average 2,4,6", 4.0),
            ("mean 10,20,30", 20.0),
            ("average 1,2,3,4,5", 3.0),
            ("average(2,4,6)", 4.0),
            ("mean(10,20,30)", 20.0),
            ("average(1,2,3,4,5)", 3.0),
        ],
    )
    def test_average_and_mean(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("log 1", pytest.approx(0.0)),
            ("log 2.718281828", pytest.approx(1.0, rel=1e-5)),
            ("log 10", pytest.approx(2.302585)),
            ("log(1)", pytest.approx(0.0)),
            ("log(2.718281828)", pytest.approx(1.0, rel=1e-5)),
            ("log(10)", pytest.approx(2.302585)),
        ],
    )
    def test_log(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sin 0", pytest.approx(0.0)),
            ("sin 3.14159", pytest.approx(0.0, abs=0.001)),
            ("sin 1.5708", pytest.approx(1.0, abs=0.001)),
            ("sin(0)", pytest.approx(0.0)),
            ("sin(3.14159)", pytest.approx(0.0, abs=0.001)),
            ("sin(1.5708)", pytest.approx(1.0, abs=0.001)),
        ],
    )
    def test_sin(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("cos(0)", pytest.approx(1.0)),
            ("cos(3.14159)", pytest.approx(-1.0, abs=0.001)),
            ("cos 0", pytest.approx(1.0)),
            ("cos 3.14159", pytest.approx(-1.0, abs=0.001)),
        ],
    )
    def test_cos(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("tan(0)", pytest.approx(0.0)),
            ("tan(0.7854)", pytest.approx(1.0, abs=0.001)),
            ("tan 0", pytest.approx(0.0)),
            ("tan 0.7854", pytest.approx(1.0, abs=0.001)),
        ],
    )
    def test_tan(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestConstants:
    """Test mathematical constants"""

    def test_pi(self):
        result = evaluator("pi")
        assert result == pytest.approx(math.pi)

    # def test_e(self):
    #     result = evaluator("e")
    #     assert result == pytest.approx(math.e)

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2*pi", pytest.approx(2 * math.pi)),
            ("pi/2", pytest.approx(math.pi / 2)),
            # ("e**2", pytest.approx(math.e**2)),
            # ("pi+e", pytest.approx(math.pi + math.e)),
        ],
    )
    def test_constants_in_expressions(self, expression: str, expected: int | float):
        assert evaluator(expression) == pytest.approx(expected)


class TestComplexExpressions:
    """Test complex expressions combining multiple operations"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2+3*4-5", 9),
            ("sqrt(16)+2*3", 10.0),
            ("(2+3)*(4+5)", 45),
            ("max(1,2,3)+min(4,5,6)", 7),
            ("abs(-5)*2+3", 13),
        ],
    )
    def test_mixed_operations(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sqrt(3**2+4**2)", 5.0),  # Pythagorean triple
            ("(10+5)/(3+2)", 3.0),
            ("2*3+4*5-6/2", 23.0),
        ],
    )
    def test_deeply_nested_expressions(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("0", 0),
            ("0.0", 0.0),
            ("-0", 0),
            ("0+0", 0),
        ],
    )
    def test_zero_values(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("1", 1),
            ("-1", -1),
            ("-123", -123),
            ("0.001", 0.001),
        ],
    )
    def test_single_numbers(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("1+2+3+4+5+6+7+8+9+10", 55),
            ("2*2*2*2*2", 32),
        ],
    )
    def test_long_expressions(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("  5  +  3  ", 8),  # whitespace
            ("( 2 + 3 ) * 4", 20),  # whitespace around parentheses
        ],
    )
    def test_whitespace_handling(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestNegativeNumbers:
    """Test handling of negative numbers"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("-5", -5),
            ("-3.14", -3.14),
            ("--5", ArithmeticEvalError),
        ],
    )
    def test_negative_numbers(self, expression: str, expected: int | float | Exception):
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                _ = evaluator(expression)
        else:
            assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("-5+-3", -8),
            ("-5--3", -2),
            ("-5*-3", 15),
            ("-10/-2", 5.0),
        ],
    )
    def test_operations_with_negatives(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestErrorHandling:
    """Test error cases and invalid expressions"""

    @pytest.mark.parametrize(
        "expression",
        [
            "10/0",  # division by zero
            "5/0",
        ],
    )
    def test_division_by_zero(self, expression: str):
        with pytest.raises(ArithmeticEvalError):
            _ = evaluator(expression)

    @pytest.mark.parametrize(
        "expression",
        [
            "sqrt(-1)",  # invalid for real numbers
            "log(0)",  # logarithm of zero
            "log(-1)",  # logarithm of negative
        ],
    )
    def test_invalid_math_operations(self, expression: str):
        with pytest.raises(ArithmeticEvalError):
            _ = evaluator(expression)

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("(2+3", 5),  # unmatched parenthesis
            ("2+3)", 5),  # unmatched parenthesis (handled by code)
        ],
    )
    def test_parenthesis_forgive(self, expression: str, expected: int | float):
        # Note: The code removes unmatched `)`, so "2+3)" will evaluate
        assert evaluator(expression) == expected


class TestFunctionWithParentheses:
    """Test functions used with parentheses and in complex expressions"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sqrt(4+5)", pytest.approx(3.0)),
            ("abs(-2-3)", 5),
            ("max(1+2,3+4,5)", 7),
            ("min(10*2,5*3)", 15),
        ],
    )
    def test_functions_with_expressions(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sqrt(sqrt(16))", 2.0),
            ("abs(abs(-5))", 5),
            ("round(round(3.14159))", 3),
        ],
    )
    def test_nested_functions(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sqrt(4)*2", 4.0),
            ("abs(-10)/2", 5.0),
            ("max(2,3)*4", 12),
            ("sqrt(16)+sqrt(9)", 7.0),
        ],
    )
    def test_functions_in_arithmetic(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestFloatingPoint:
    """Test floating-point number handling and precision"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("0.1+0.2", pytest.approx(0.3)),
            ("1.5*2.5", 3.75),
            ("0.333333*3", 0.999999),
            ("1.1+2.2+3.3", pytest.approx(6.6)),
        ],
    )
    def test_float_arithmetic(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("0.5", 0.5),
            ("0.001", 0.001),
            ("-3.14159", -3.14159),
            (".5", 0.5),
        ],
    )
    def test_float_parsing(self, expression: str, expected: int | float):
        assert evaluator(expression) == pytest.approx(expected)

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("1.0+2", 3.0),
            ("5+2.5", 7.5),
            ("10/3", pytest.approx(3.333333)),
        ],
    )
    def test_mixed_int_float_arithmetic(self, expression: str, expected: int | float):
        assert evaluator(expression) == pytest.approx(expected)


class TestConstantsAdvanced:
    """Test constants in complex expressions"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("pi*2", pytest.approx(2 * math.pi)),
            ("e**2", pytest.approx(math.e**2)),
            ("sin(pi/2)", pytest.approx(1.0)),
            ("cos(pi)", pytest.approx(-1.0, abs=0.0001)),
        ],
    )
    def test_constants_in_complex_expressions(self, expression: str, expected: int | float):
        assert evaluator(expression) == pytest.approx(expected)

    def test_multiple_constants(self):
        result = evaluator("pi+e")
        expected = math.pi + math.e
        assert result == pytest.approx(expected)


class TestAllFunctionsWithDifferentArgCounts:
    """Test functions that accept variable numbers of arguments"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sum(1)", 1),
            ("sum(1,2)", 3),
            ("sum(1,2,3,4,5)", 15),
        ],
    )
    def test_sum_variable_args(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("min(5)", 5),
            ("min(3,2,1)", 1),
            ("min(10,5,8,3,9)", 3),
        ],
    )
    def test_min_variable_args(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("max(5)", 5),
            ("max(3,2,1)", 3),
            ("max(10,5,8,3,9)", 10),
        ],
    )
    def test_max_variable_args(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("average(10)", 10.0),
            ("average(5,5)", 5.0),
            ("average(1,2,3,4,5)", 3.0),
        ],
    )
    def test_average_variable_args(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestOperatorCombinations:
    """Test various combinations of operators"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2+3-4", 1),
            ("10-5+3", 8),
            ("2*3/6", 1.0),
            ("10/2*3", 15.0),
        ],
    )
    def test_sequential_operators(self, expression: str, expected: int | float):
        assert evaluator(expression) == pytest.approx(expected)

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2*3+4*5", 26),
            ("10/2-3*1", 2.0),
            ("2+3*4-5*2", 4),
        ],
    )
    def test_mixed_precedence_operators(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestPowerOperators:
    """Test both ^ and ** power operators"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2**3", 8),
            ("2^3", 8),
            ("5**2", 25),
            ("5^2", 25),
        ],
    )
    def test_both_power_symbols(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2^2^3", 256),  # right associative: 2^(2^3) = 2^8 = 256
            ("2**2**3", 256),
        ],
    )
    def test_power_right_associativity(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestSpecialMathCases:
    """Test special mathematical cases"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("0**0", 1),  # commonly defined as 1
            ("1**100", 1),
            ("0**5", 0),
        ],
    )
    def test_special_power_cases(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sqrt(0)", 0.0),
            ("abs(-0)", 0),
            ("max(0,-1,-2)", 0),
        ],
    )
    def test_zero_in_functions(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("1/2/2", 0.25),
            ("100/10/10", 1.0),
        ],
    )
    def test_chained_division(self, expression: str, expected: int | float):
        assert evaluator(expression) == pytest.approx(expected)


class TestRealWorldExpressions:
    """Test real-world mathematical expressions"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            # Circle area with radius 5
            ("pi*5**2", pytest.approx(78.539816)),
            # Pythagorean theorem: 3-4-5 triangle
            ("sqrt(3**2+4**2)", 5.0),
            # Celsius to Fahrenheit: (0°C)
            ("0*9/5+32", 32.0),
            # Quadratic formula discriminant
            ("2**2-4*1*1", 0),
            # Average of numbers
            ("(10+20+30)/3", 20.0),
        ],
    )
    def test_real_world_math(self, expression: str, expected: int | float):
        assert evaluator(expression) == pytest.approx(expected)


class TestModuloEdgeCases:
    """Test modulo operation edge cases"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("10%10", 0),
            ("5%10", 5),
            ("0%5", 0),
        ],
    )
    def test_modulo_edge_cases(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestFunctionNameParsing:
    """Test that function names are correctly identified and parsed"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sum(2,3)+5", 10),
            ("total(1,2,3)+4", 10),
            ("5+sum(2,3)", 10),
        ],
    )
    def test_function_position_in_expression(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sum(1,2)+sum(3,4)", 10),
            ("max(1,2)+min(3,4)", 5),
        ],
    )
    def test_multiple_functions_in_expression(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestBoundaryValuesAndLargeNumbers:
    """Test with boundary values and large numbers"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("1000000+1", 1000001),
            ("999999*2", 1999998),
            ("1000000/1000", 1000.0),
        ],
    )
    def test_large_numbers(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("0.0001+0.0001", pytest.approx(0.0002)),
            ("0.000001*1000000", pytest.approx(1.0)),
        ],
    )
    def test_small_numbers(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestSubtractionEdgeCases:
    """Test subtraction with negative numbers and edge cases"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("5-0", 5),
            ("0-5", -5),
            ("5--5", 10),  # 5 minus negative 5
        ],
    )
    def test_subtraction_edge_cases(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestComplexNestedExpressions:
    """Test deeply nested and complex expressions"""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("((((1+2)*3)-4)/5)", pytest.approx(1.0)),
            ("(2+(3*(4+(5*(6)))))", 104),
            ("((10-5)*(3+2))+(4*2)", 33),
        ],
    )
    def test_deeply_nested_parentheses(self, expression: str, expected: int | float):
        assert evaluator(expression) == pytest.approx(expected)

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("sqrt(max(4,9,16))", 4.0),
            ("min(abs(-5),sqrt(16),3)", 3),
            ("round(average(1.1,2.2,3.3))", 2),
        ],
    )
    def test_functions_within_complex_expressions(self, expression: str, expected: int | float):
        assert evaluator(expression) == pytest.approx(expected)


# class TestReturnTypes:
#     """Test that return types are correct (int vs float)"""

#     @pytest.mark.parametrize(
#         "expression,expected_type",
#         [
#             ("5", int),
#             ("5.0", float),
#             ("2+3", int),
#             ("2.0+3", float),
#             ("5/1", float),  # division always returns float
#             ("sqrt(4)", float),  # sqrt returns float
#         ],
#     )
#     def test_return_types(self, expression: str, expected_type: type):
#         result = evaluator(expression)
#         assert isinstance(result, expected_type)


@pytest.fixture
def performance_test_data():
    """Fixture providing test data for performance tests"""
    return {
        "simple": "2+3",
        "moderate": "2+3*4-5/2",
        "complex": "((2+3)*(4-1)+sqrt(16)*average(1,2,3))*2",
    }


class TestPerformance:
    """Test that evaluator completes in reasonable time"""

    def test_simple_expression_performance(self, performance_test_data: dict[str, str]):
        """Simple expressions should be very fast"""
        import time

        start = time.time()
        for _ in range(1000):
            _ = evaluator(performance_test_data["simple"])
        elapsed = time.time() - start
        assert elapsed < 1.0, f"1000 simple expressions took {elapsed}s"

    def test_complex_expression_performance(self, performance_test_data: dict[str, str]):
        """Complex expressions should still be reasonable"""
        import time

        start = time.time()
        for _ in range(100):
            _ = evaluator(performance_test_data["complex"])
        elapsed = time.time() - start
        assert elapsed < 1.0, f"100 complex expressions took {elapsed}s"


class TestPerformanceOutput:
    def test_simple_expression_performance(self, performance_test_data: dict[str, str]):
        import time

        start = time.time()
        for _ in range(100_000):
            _ = evaluator(performance_test_data["simple"])
        elapsed = time.time() - start
        print(f"\n100_000 complex expressions took {elapsed}s")

    def test_complex_expression_performance(self, performance_test_data: dict[str, str]):
        import time

        start = time.time()
        for _ in range(100_000):
            _ = evaluator(performance_test_data["complex"])
        elapsed = time.time() - start
        print(f"\n100_000 complex expressions took {elapsed}s")


class TestUnitValues:
    def test_simple_units(self):
        # TODO: test simple unit values
        pass


class TestMultiCalculation:
    @pytest.mark.parametrize(
        "expression, expected",
        [
            ("1 + 5", 6),
            ("5; 4;", [5, 4]),
            ("1;2;3;4", [1, 2, 3, 4]),
            ("1+2; 2+3", [3, 5]),
            ("sqrt 4; min 2, 3, 4", [2, 2]),
        ],
    )
    def test_simple_multi_expressions(
        self, expression: str, expected: int | float | list[int | float]
    ):
        assert evaluator(expression) == expected


class TestOtherBaseNotations:
    @pytest.mark.parametrize(
        "expression, expected",
        [
            ("0b1", 1),
            ("b1", 1),
            ("0b10", 2),
            ("b10", 2),
            ("b10.10", 2.5),
            ("b10.11", 2.75),
            ("b10.111", 2.875),
        ],
    )
    def test_binary_base_notation(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression, expected",
        [
            ("0o1", 0o1),
            ("o1", 0o1),
            ("0o27", 0o27),
            ("o75", 0o75),
            ("o10.10", 8.125),
            ("o10.11", 8.140625),
            ("o10.111", 8.142578125),
        ],
    )
    def test_octal_base_notation(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected

    @pytest.mark.parametrize(
        "expression, expected",
        [
            ("0x1", 1),
            ("x1", 1),
            ("0x10", 16),
            ("x10", 16),
            ("x10.10", 16.0625),
            ("x10.11", 16.06640625),
            ("x10.111", 16.066650390625),
        ],
    )
    def test_hex_base_notation(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected


class TestUnderscore:
    @pytest.mark.parametrize(
        "expression, expected",
        [
            ("1_000_000", 1_000_000),
            ("1_", 1),
            ("_1", 1),
            ("_5 _+ 5_", 10),
        ],
    )
    def test_underscore(self, expression: str, expected: int | float):
        assert evaluator(expression) == expected
