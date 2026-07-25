import math
import re
from collections.abc import Callable, Iterable
from decimal import Decimal

from .value import NA_VALUE, Value

_DECIMAL_FLOAT_PAT = re.compile(r"^((-)?\d+)?\.(-)?\d+$")
_DECIMAL_INT_PAT = re.compile(r"^(-)?\d+$")
_NUMBER_AND_UNIT_PAT = re.compile(r"^(-?\d*\.?\d+)\s?([a-zA-Z]*)$")
_MULTI_PAT = re.compile(r"^(.+)(?<!\*)[\*xX](?!\*)(.+)$")
_SCIENTIFIC_PAT = re.compile(r"^[+-]?\d+\.?\d*[eE][+-]?\d+$")
_PERCENT_PAT = re.compile(r"^(\d+)?(\.)?\d%$")
_BINARY_PAT = re.compile(r"^0?b(?=[01.])([01]+)?(?:\.([01]+))?\s?([a-z]+)?$")
_OCTAL_PAT = re.compile(r"^0?o(?=[0-7.])([0-7]+)?(?:\.([0-7]+))?\s?([a-z]+)?$")
_HEX_PAT = re.compile(r"^0?x(?=\d|[a-f.])([0-9a-f]+)?(?:\.([0-9a-f]+))?(?:\s([a-z]+))?$")

use_cache: bool = False

if use_cache:
    _cache_data: dict[str, Value] = dict()  # pyright: ignore[reportUnreachable]


def average(args: tuple[int | float]) -> int | float:
    return sum(args) / len(args)


def _log(x: int | float | Iterable[int | float]) -> int | float:
    if isinstance(x, Iterable):
        return math.log(*x)
    return math.log(x)


_FUNCTIONS: dict[str, tuple[Callable[[object], int | float], bool]] = {  # pyright: ignore[reportAssignmentType]
    "sqrt": (math.sqrt, False),
    "abs": (abs, False),
    "round": (round, False),
    "min": (min, True),
    "max": (max, True),
    "total": (sum, True),
    "sum": (sum, True),
    "average": (average, True),
    "mean": (average, True),
    "log": (_log, False),
    "sin": (math.sin, False),
    "cos": (math.cos, False),
    "tan": (math.tan, False),
}
"dict[func_name, tuple[function, iterable_arg_required]]"

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,  # conflicts with average, mean
}


class ArithmeticEvalError(Exception):
    pass


def _split_parenthesis(expression: str) -> tuple[tuple[str, str, str] | None, bool]:
    lvl = 0
    start_index: int | None = None
    end_index = len(expression)  # pretend there is a ")" at the end
    found_comma = False
    for i, c in enumerate(expression):
        if c == "(":
            if lvl == 0:
                start_index = i
            lvl += 1
        elif c == ")":
            lvl -= 1
            if lvl == 0:
                end_index = i
                break
        elif c == "," and lvl == 1:
            found_comma = True

    if start_index is not None:
        return (
            expression[:start_index],
            expression[start_index + 1 : end_index],
            expression[end_index + 1 :],
        ), found_comma
    return None, found_comma


def _cache(func: Callable[[str], Value]) -> Callable[[str], Value]:  # pyright: ignore[reportUnusedFunction]
    def wrapper(exp: str):
        if use_cache:
            if exp in _cache_data:
                return _cache_data[exp]
            else:
                res = func(exp)
                _cache_data[exp] = res
                return res
        else:
            return func(exp)

    return wrapper


def evaluator(expression: str) -> list[Value] | Value:
    try:
        # region constant replacing
        for cons in _CONSTANTS.keys():
            if cons in expression:
                if cons == "e":  # handle special case (conflicts with average, mean, etc.)
                    idx = 0
                    while (idx := expression.find(cons, idx)) != -1:
                        bef_alpha = idx != 0 and expression[idx - 1].isalpha()
                        aft_alpha = idx < len(expression) - 1 and expression[idx + 1].isalpha()
                        if not bef_alpha and not aft_alpha:
                            expression = (
                                expression[:idx] + str(_CONSTANTS[cons]) + expression[idx + 1 :]
                            )
                        idx += 1
                    continue

                expression = expression.replace(cons, str(_CONSTANTS[cons]))
        # endregion

        expression = expression.strip(";").replace("_", "")  # get rid of unwanted ";" and all "_"

        if not expression:
            raise Exception("Nothing to evaluate.")

        if ";" in expression:  # if multi expression found
            expressions = expression.split(";")
        else:
            expressions = [expression]

        results: list[Value] = []
        for expression in expressions:
            expression, *conversions = re.split(" to | in | into | as ", expression.strip())
            try:
                if not expression.strip():
                    raise Exception("Nothing to evaluate.")
                res = _evaluator(expression)
                if conversions:
                    for conv in conversions:
                        res = res.convert_unit(conv.strip())
                results.append(res)
            except Exception as exp:
                if len(expressions) == 1:
                    raise ArithmeticEvalError(exp)
                results.append(NA_VALUE)

        return results[0] if len(results) < 2 else results
    except Exception as exp:
        raise ArithmeticEvalError(exp)


# @_cache
def _evaluator(expression: str) -> Value:
    expression = expression.strip()

    if match := _NUMBER_AND_UNIT_PAT.match(expression):
        return Value(float((x := match.groups())[0]), x[1] or None)

    if _SCIENTIFIC_PAT.match(expression):
        return Value(float(Decimal(expression)))

    for pat, base in {(_BINARY_PAT, 2), (_OCTAL_PAT, 8), (_HEX_PAT, 16)}:
        if match := pat.match(expression.lower()):
            groups = match.groups()
            val = int(groups[0], base)
            dec_val = 0
            if groups[1] is not None:
                dec_val = sum(int(d) * base ** -(i + 1) for i, d in enumerate(groups[1]))
            return Value(val + dec_val, groups[2])

    if _PERCENT_PAT.match(expression):
        return Value(float(expression.removesuffix("%")) / 100)

    for func_name in _FUNCTIONS.keys():
        if func_name in expression:
            pieces = expression.split(func_name, 1)
            args = pieces[1]
            append_exp = ""
            found_comma = "," in args

            if (x := pieces[1].strip()) and x[0] == "(":
                _pieces, found_comma = _split_parenthesis(pieces[1])
                if _pieces is not None and _pieces[0].strip() == "":
                    args = _pieces[1]
                    append_exp = _pieces[2]

            if found_comma:
                _args: int | float | tuple[int | float, ...] = tuple(
                    _evaluator(x).amount for x in args.split(",")
                )
            else:
                _args = _evaluator(args).amount
            func, req_iter = _FUNCTIONS[func_name]
            if req_iter and not isinstance(_args, Iterable):
                _args = (_args,)
            res = func(_args)
            expression = pieces[0] + str(res) + append_exp
            return _evaluator(expression)

    if ")" in expression and "(" not in expression:
        # pretend extra `)` is a mistake NOTE: test with all scenarios
        expression = expression.replace(")", "")

    if "(" in expression:
        pieces, _ = _split_parenthesis(expression)
        if pieces is not None:
            expression = pieces[0] + str(_evaluator(pieces[1])) + pieces[2]
            return _evaluator(expression)

    if "+" in expression:
        pieces = expression.split("+", 1)
        return _evaluator(pieces[0]) + _evaluator(pieces[1])

    if "-" in expression:
        # find rightmost BINARY minus (skip unary ones)
        idx = expression.rfind("-")
        while idx > 0:
            prev_char = expression[:idx].strip()[-1]
            # Binary minus if preceded by: digit, or alphanumeric
            if prev_char.isalnum():
                return _evaluator(expression[:idx]) - _evaluator(expression[idx + 1 :])
            # this minus is unary, look for the next one to the left
            idx = expression.rfind("-", 0, idx)

    if i := _MULTI_PAT.match(expression):
        return _evaluator(i.groups()[0]) * _evaluator(i.groups()[1])

    if "/" in expression:
        pieces = expression.rsplit("/", 1)
        return _evaluator(pieces[0]) / _evaluator(pieces[1])

    if "%" in expression:
        pieces = expression.rsplit("%", 1)
        return _evaluator(pieces[0]) % _evaluator(pieces[1])

    if expression.find(x := "**") != -1 or expression.find(x := "^") != -1:
        pieces = expression.split(x, 1)
        return _evaluator(pieces[0]) ** _evaluator(pieces[1])

    raise ArithmeticEvalError
