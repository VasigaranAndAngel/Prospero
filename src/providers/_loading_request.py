from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class LoadingRequest:
    """A class to act as a ticket that tells UI to show loading indication.

    remove-hooks are implemented here because it's easy for providers to remove the LoadingRequest
    from main window with remove() method. MainWindow handles removing the LoadingRequest by adding
    and removing remove-hooks.
    """

    _remove_hooks: list[Callable[["LoadingRequest"], None]] = field(
        default_factory=list, init=False, repr=False, hash=False, compare=False
    )
    score: int

    def remove(self) -> None:
        """This will call all remove hooks with self as parameter.

        Use self.add_to_remove_hooks() to add to the hooks list.
        """
        for func in self._remove_hooks:
            func(self)

    def add_to_remove_hooks(self, func: Callable[["LoadingRequest"], None]) -> None:
        """Adds to remove hooks list

        Added callables will be called with self (current instance) as parameter when self.remove()
        is called.
        """
        self._remove_hooks.append(func)

    def remove_from_remove_hooks(self, func: Callable[["LoadingRequest"], None]) -> None:
        """Removes a hook from the remove-hook-list."""
        if func in self._remove_hooks:
            self._remove_hooks.remove(func)
