from collections.abc import Collection
from typing import override

from .._base_provider import BaseProvider
from ..base_result_and_widgets import BaseResult, ExecutionAction
from .nl_calc.arithmetic_split_method import ArithmeticEvalError, evaluator


class CalcResult(BaseResult):
    @override
    def execute(self, action: ExecutionAction) -> None:
        if action is ExecutionAction.Trigger:
            try:
                import pyperclip  # if pyperclip is available, use it.

                pyperclip.copy(self.text)
            except ImportError:
                # Importing PySide6 here so it will not imported when launching in cli mode
                from PySide6.QtGui import QGuiApplication

                QGuiApplication.clipboard().setText(self.text)


class CalcProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Calculation Provider")

    @override
    def search(self, query: str) -> Collection[CalcResult]:
        try:
            if query.strip():
                res = evaluator(query)
                return [CalcResult(text=str(res), score=1000)]
            else:
                return []
        except ArithmeticEvalError:
            return []
