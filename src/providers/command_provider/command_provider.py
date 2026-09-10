import logging
import subprocess
import sys
from collections.abc import Callable, Collection
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Literal, overload, override

from constants import APPLICATION_NAME
from fuzzy_finder import BaseChoice, IncrementalMatcher
from helpers import task_schedule_handler

from .._base_provider import BaseProvider
from ..base_result_and_widgets import BaseResult, BaseResultBoxWidget, ExecutionAction
from ._shutdown import shutdown_respect_hybrid
from ._updater_result_widget import UpdaterResultWidget

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Command:
    command_type: Literal["shell", "func"] | None
    command: Callable[[], None] | str | None
    description: str
    result_widget_factory: Callable[[str, BaseResult], BaseResultBoxWidget] | None = None

    if TYPE_CHECKING:

        @overload
        def __init__(
            self,
            command_type: Literal["shell"],
            command: str,
            description: str,
            result_widget_factory: Callable[[str, BaseResult], BaseResultBoxWidget] | None = None,
        ) -> None: ...

        @overload
        def __init__(
            self,
            command_type: Literal["func"],
            command: Callable[[], None],
            description: str,
            result_widget_factory: Callable[[str, BaseResult], BaseResultBoxWidget] | None = None,
        ) -> None: ...

        @overload
        def __init__(
            self,
            command_type: None,
            command: None,
            description: str,
            result_widget_factory: Callable[[str, BaseResult], BaseResultBoxWidget] | None = None,
        ) -> None: ...

        def __init__(
            self,
            command_type: Literal["shell", "func"] | None,
            command: Callable[[], None] | str | None,
            description: str,
            result_widget_factory: Callable[[str, BaseResult], BaseResultBoxWidget] | None = None,
        ) -> None: ...

    def __call__(self, *args: object, **kwds: object) -> None:
        if self.command_type == "func" and isinstance(self.command, Callable):
            logger.debug(f"Executing {self}")
            self.command()
        if self.command_type == "shell" and isinstance(self.command, str):
            res = subprocess.run(
                self.command,
                creationflags=subprocess.CREATE_NO_WINDOW,  # Windows only
                stdout=subprocess.DEVNULL,  # mac and linux
                stderr=subprocess.DEVNULL,  # mac and linux
            )
            logger.debug(res.stderr)  # TODO: remove?

    @override
    def __str__(self) -> str:
        return f"{self.command_type} command: {self.command}"

    @override
    def __repr__(self) -> str:
        return self.__str__()


_COMMANDS: dict[str, Command] = {
    "Quit": (x := Command("func", sys.exit, "Quits the application")),
    "q": x,
    "Power: Shutdown": Command("func", shutdown_respect_hybrid, "Shuts down the computer"),
    "Power: Restart": Command("shell", "shutdown.exe /r /t 0", "Restarts the computer"),
    "Power: Hibernate": Command("shell", "shutdown.exe /h", "Hibernates the computer"),
    "Power: Sleep": Command("shell", "", "Puts the computer to sleep"),  # TODO: sleeping isn't easy
    "Power: Lock": Command(
        "shell", "rundll32.exe user32.dll,LockWorkStation", "Locks the current user account"
    ),
    "Updater": Command(None, None, f"Update {APPLICATION_NAME.title()}", UpdaterResultWidget),
    f"Add {APPLICATION_NAME.title()} to Scheduled Tasks": Command(
        "func",
        partial(task_schedule_handler.add_task, lambda x: None),
        f"Adds {APPLICATION_NAME.title()} to scheduled tasks to start on current user log on.",
    ),
    f"Remove {APPLICATION_NAME.title()} from Scheduled Tasks": Command(
        "func",
        partial(task_schedule_handler.remove_task, lambda x: None),
        f"Removes {APPLICATION_NAME.title()} from scheduled tasks.",
    ),
}


@dataclass
class CommandResult(BaseResult):
    func: Callable[[], None] | None = None

    @override
    def execute(self, action: ExecutionAction) -> None:
        if action in ExecutionAction.Trigger and self.func is not None:
            self.func()

    @override
    def __hash__(self) -> int:
        return super().__hash__()


@dataclass
class CommandChoice(BaseChoice):
    func: Callable[[], None] | None
    description: str
    result_widget_factory: Callable[[str, BaseResult], BaseResultBoxWidget] | None = None


class CommandProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Command Provider")
        self._matcher: IncrementalMatcher[CommandChoice] = IncrementalMatcher([], 5)
        self._matcher.update_choices(
            [
                CommandChoice(name, command, command.description, command.result_widget_factory)
                for name, command in _COMMANDS.items()
            ]
        )

    @override
    def search(self, query: str) -> Collection[CommandResult]:
        results = self._matcher.search(query)
        return [
            CommandResult(
                res.choice.text,
                res.score,
                res.positions,
                res.choice.description,
                result_widget_factory=res.choice.result_widget_factory,
                func=res.choice.func,
            )
            for res in results
        ]
