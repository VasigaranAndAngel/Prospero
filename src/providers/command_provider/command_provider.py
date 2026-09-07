import logging
import subprocess
import sys
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, overload, override

from fuzzy_finder import BaseChoice, IncrementalMatcher

from .._base_provider import BaseProvider
from ..base_result_and_widgets import BaseResult, BaseResultBoxWidget, ExecutionActions
from ._shutdown import shutdown_respect_hybrid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Command:
    command_type: Literal["shell", "func"]
    shell_command: str | None
    func: Callable[[], None] | None
    description: str

    if TYPE_CHECKING:

        @overload
        def __init__(
            self,
            command_type: Literal["shell", "func"],
            shell_command: str,
            func: None,
            description: str,
        ) -> None: ...

        @overload
        def __init__(
            self,
            command_type: Literal["func"],
            shell_command: None,
            func: Callable[[], None],
            description: str,
        ) -> None: ...

        def __init__(
            self,
            command_type: Literal["shell", "func"],
            shell_command: str | None,
            func: Callable[[], None] | None,
            description: str,
        ) -> None: ...

    def __call__(self, *args: object, **kwds: object) -> None:
        if self.command_type == "func" and self.func is not None:
            logger.debug(f"Executing {self}")
            self.func()
        if self.command_type == "shell" and self.shell_command is not None:
            res = subprocess.run(
                self.shell_command,
                creationflags=subprocess.CREATE_NO_WINDOW,  # Windows only
                stdout=subprocess.DEVNULL,  # mac and linux
                stderr=subprocess.DEVNULL,  # mac and linux
            )
            logger.debug(res.stderr)  # TODO: remove?

    @override
    def __str__(self) -> str:
        return f"{self.command_type} command: {self.shell_command or self.func}"

    @override
    def __repr__(self) -> str:
        return self.__str__()


_COMMANDS: dict[str, Command] = {
    "Quit": (x := Command("func", None, sys.exit, "Quits the application")),
    "q": x,
    "Power: Shutdown": Command("func", None, shutdown_respect_hybrid, "Shuts down the computer"),
    "Power: Restart": Command("shell", "shutdown.exe /r /t 0", None, "Restarts the computer"),
    "Power: Hibernate": Command("shell", "shutdown.exe /h", None, "Hibernates the computer"),
    "Power: Sleep": Command(
        "shell", "", None, "Puts the computer to sleep"
    ),  # TODO: sleeping isn't easy
    "Power: Lock": Command(
        "shell", "rundll32.exe user32.dll,LockWorkStation", None, "Locks the current user account"
    ),
}


@dataclass
class CommandResult(BaseResult):
    func: Callable[[], None] | None = None

    @override
    def execute(self, action: ExecutionActions) -> None:
        if action is ExecutionActions.Enter and self.func is not None:
            self.func()

    @override
    def __hash__(self) -> int:
        return super().__hash__()


@dataclass
class CommandChoice(BaseChoice):
    func: Callable[[], None]
    description: str
    result_widget_factory: Callable[[str, BaseResult], BaseResultBoxWidget] | None = None


class CommandProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Command Provider")
        self._matcher: IncrementalMatcher[CommandChoice] = IncrementalMatcher([], 5)
        self._matcher.update_choices(
            [
                CommandChoice(name, command, command.description)
                for name, command in _COMMANDS.items()
            ]
        )

    @override
    def search(self, query: str) -> Collection[CommandResult]:
        results = self._matcher.search(query)
        return [
            CommandResult(
                res.choice.text, res.score, res.positions, res.choice.description, res.choice.func
            )
            for res in results
        ]
