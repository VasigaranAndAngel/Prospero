import logging
import subprocess
import sys
from collections.abc import Callable, Collection
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Literal, overload, override

from platform_specific import CREATE_NO_WINDOW

from constants import APPLICATION_NAME, VERSION
from fuzzy_finder import BaseChoice, IncrementalMatcher
from platform_specific import startup

from .._base_provider import BaseProvider
from ..base_result_and_widgets import (
    BaseResult,
    BaseResultBoxWidget,
    ExecutionAction,
    ResultAttributes,
)
from ._power import hibernate, lock, restart, shutdown, sleep
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
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
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
    "Power: Shutdown": Command("func", shutdown, "Shuts down the computer"),
    "Power: Restart": Command("func", restart, "Restarts the computer"),
    "Power: Hibernate": Command("func", hibernate, "Hibernates the computer"),
    "Power: Sleep": Command("func", sleep, "Puts the computer to sleep"),
    "Power: Lock": Command("func", lock, "Locks the current user account"),
    "Updater": Command(None, None, f"Update {APPLICATION_NAME.title()}", UpdaterResultWidget),
    f"Add {APPLICATION_NAME.title()} to Scheduled Tasks": Command(
        "func",
        partial(startup.add_task, lambda x: None),
        f"Adds {APPLICATION_NAME.title()} to scheduled tasks to start on current user log on.",
    ),
    f"Remove {APPLICATION_NAME.title()} from Scheduled Tasks": Command(
        "func",
        partial(startup.remove_task, lambda x: None),
        f"Removes {APPLICATION_NAME.title()} from scheduled tasks.",
    ),
    "Version": Command(None, None, f"Current version of {APPLICATION_NAME.title()} is {VERSION}"),
}


@dataclass(kw_only=True)
class CommandResult(BaseResult, BaseChoice):
    func: Callable[[], None] | None = None

    @override
    def execute(self, action: ExecutionAction) -> None:
        if action is ExecutionAction.Trigger and self.func is not None:
            self.func()

    @override
    def __hash__(self) -> int:
        return super().__hash__()


class CommandProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Command Provider")
        self._matcher: IncrementalMatcher[CommandResult] = IncrementalMatcher([], 5)
        choices = [
            CommandResult(
                text=name,
                description=command.description,
                result_widget_factory=command.result_widget_factory,
                func=command,
                attributes=ResultAttributes(suggestion_request=name)
            )
            for name, command in _COMMANDS.items()
        ]
        self._matcher.update_choices(choices)

    @override
    def search(self, query: str) -> Collection[CommandResult]:
        return self._matcher.search(query)
