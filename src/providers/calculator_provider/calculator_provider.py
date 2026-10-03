from collections.abc import Collection
from typing import override

from query_placeholder_tokens import (
    register_query_placeholder_token,
    unregister_query_placeholder_token,
)

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
        self._last_result: str = ""
        self._current_result: str = ""

        @register_query_placeholder_token("provider.calc.result")
        def result() -> str:
            return self._current_result

        @register_query_placeholder_token("provider.calc.last_result")
        def last_result() -> str:
            return self._last_result

    @override
    def search(self, query: str) -> Collection[CalcResult]:
        try:
            if query.strip():
                res = evaluator(query)
                res_txt = str(res)
                self._last_result = self._current_result = res_txt
                return [CalcResult(text=res_txt, score=1000)]
            else:
                self._current_result = ""
                return []
        except ArithmeticEvalError:
            self._current_result = ""
            return []

    @override
    def disable_hook(self) -> None:
        unregister_query_placeholder_token("provider.calc.result")
        unregister_query_placeholder_token("provider.calc.last_result")
        return super().disable_hook()
