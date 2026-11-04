import logging
from collections.abc import Collection
from typing import override

from query_placeholder_tokens import (
    register_query_placeholder_token,
    unregister_query_placeholder_token,
)

from .._base_provider import BaseProvider
from ..base_result_and_widgets import BaseResult, ExecutionAction
from .nl_calc.arithmetic_split_method import ArithmeticEvalError, evaluator

logger = logging.getLogger(__name__)


class CalcResult(BaseResult):
    @override
    def execute(self, action: ExecutionAction) -> None:
        if action is not ExecutionAction.Trigger:
            return

        try:
            import pyperclip  # if pyperclip is available, use it.
        except ImportError:
            pyperclip = None  # pyright: ignore[reportAssignmentType]

        if pyperclip is not None:
            try:
                pyperclip.copy(self.text)
                return
            except pyperclip.PyperclipException:
                # Installed, but no backend (xclip/xsel/wl-copy missing) on this system.
                logger.debug("pyperclip has no usable clipboard backend; falling back to Qt")

        # Importing PySide6 here so it will not be imported when launching in cli mode.
        from PySide6.QtGui import QGuiApplication

        if QGuiApplication.instance() is None:
            logger.warning("No clipboard available; result was not copied")
            return
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
