from collections.abc import Collection
from typing import override

from .._base_provider import BaseProvider
from .._base_result import BaseResult, ExecutionActions
from .nl_calc.arithmetic_split_method import ArithmeticEvalError, evaluator


class CalcResult(BaseResult):
    @override
    def execute(self, action: ExecutionActions) -> None:
        try:
            import pyperclip  # if pyperclip is available, use it.

            pyperclip.copy(self.result)
        except ImportError:
            # Importing PySide6 here so it will not imported when launching in cli mode
            from PySide6.QtGui import QGuiApplication

            QGuiApplication.clipboard().setText(self.result)


class CalcProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Calculation Provider")

    @override
    def search(self, query: str) -> Collection[CalcResult]:
        try:
            if query.strip():
                res = evaluator(query)
                return [CalcResult(str(res), 1000, [], None)]
            else:
                return []
        except ArithmeticEvalError:
            return []
