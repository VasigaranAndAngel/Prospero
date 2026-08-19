import logging
import subprocess
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, overload, override

from fuzzy_finder import BaseChoice, IncrementalMatcher

from .._base_provider import BaseProvider
from .._base_result import BaseResult, ExecutionActions
from ._shutdown import shutdown_respect_hybrid

logger = logging.getLogger(__name__)


@dataclass
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
    "Quit": (x := Command("func", None, quit, "Quits the application")),
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


class CommandResult(BaseResult):
    def __init__(
        self,
        result: str,
        score: int,
        highlighted_indexes: list[int],
        description: str | None,
        func: Callable[[], None],
    ) -> None:
        super().__init__(result, score, highlighted_indexes, description)

        self._func: Callable[[], None] = func

    @override
    def execute(self, action: ExecutionActions) -> None:
        if action is ExecutionActions.Enter:
            self._func()


class CommandChoice(BaseChoice):
    def __init__(self, text: str, func: Callable[[], None], description: str) -> None:
        super().__init__(text)

        self.func: Callable[[], None] = func
        self.description: str = description


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
