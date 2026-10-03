"""
This is file is only for register tokens from all over the project. Query Box will use registered
tokens to render the placeholder.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeVar, overload

if TYPE_CHECKING:
    from ui._query_box._placeholder_formatter import _Metrics  # pyright: ignore[reportPrivateUsage]


__all__ = ["register_query_placeholder_token", "unregister_query_placeholder_token"]

_CallableE = Callable[[], str]
_CallableM = Callable[["_Metrics"], str]
_CallableS = Callable[[str], str]
_CallableMS = Callable[["_Metrics", str], str]

_TokenFunc = TypeVar("_TokenFunc", bound=_CallableE | _CallableM | _CallableS | _CallableMS)

_TOKENS: dict[str, "Registration"] = {}
_TOKEN_UPDATE_HOOK: set[Callable[[str], None]] = set()
# ^^^ This will be redefined in _placeholder_formatter.py


@dataclass(frozen=True)
class Registration:
    """A single registered token. `func` takes exactly the args the flags ask for, see `call()`."""

    func: Callable[..., str]
    update_interval: int | None
    metrics_required: bool
    spec_required: bool

    def call(self, m: "_Metrics", spec: str) -> str:
        args: list[object] = []
        if self.metrics_required:
            args.append(m)
        if self.spec_required:
            args.append(spec)
        return self.func(*args)


# region overloads for type support
@overload
def register_query_placeholder_token(  # pyright: ignore[reportOverlappingOverload]
    token: str,
    update_interval: int | None = None,
    placeholder: str | None = None,
    metrics_required: Literal[False] = ...,
    spec_required: Literal[False] = ...,
) -> Callable[[_CallableE], _CallableE]: ...


@overload
def register_query_placeholder_token(
    token: str,
    update_interval: int | None = None,
    placeholder: str | None = None,
    metrics_required: Literal[True] = ...,
    spec_required: Literal[False] = ...,
) -> Callable[[_CallableM], _CallableM]: ...


@overload
def register_query_placeholder_token(
    token: str,
    update_interval: int | None = None,
    placeholder: str | None = None,
    metrics_required: Literal[False] = ...,
    spec_required: Literal[True] = ...,
) -> Callable[[_CallableS], _CallableS]: ...


@overload
def register_query_placeholder_token(
    token: str,
    update_interval: int | None = None,
    placeholder: str | None = None,
    metrics_required: Literal[True] = ...,
    spec_required: Literal[True] = ...,
) -> Callable[[_CallableMS], _CallableMS]: ...


# endregion


def register_query_placeholder_token(
    token: str,
    update_interval: int | None = None,
    placeholder: str | None = None,
    metrics_required: bool = False,
    spec_required: bool = False,
) -> Callable[[_TokenFunc], _TokenFunc]:
    """Register `func` under `token` and return it unchanged.

    `func` must accept `(m, spec)`, `(m,)`, `(spec,)` or `()` according to `metrics_required` and
    `spec_required`. When `placeholder` is given, `func` is never called and the rendered text is
    the placeholder instead.
    """

    def _decorator(func: _TokenFunc) -> _TokenFunc:
        if token in _TOKENS:
            raise ValueError(f"Token {token!r} is already registered")

        def _stub(*_args: object) -> str:
            return f"'{token}' {placeholder}"

        _TOKENS[token] = Registration(
            func=_stub if placeholder is not None else func,
            update_interval=update_interval,
            metrics_required=metrics_required,
            spec_required=spec_required,
        )
        return func

    return _decorator


def unregister_query_placeholder_token(token: str) -> None:
    """Unregisters a registered token by token name."""
    if token in _TOKENS:
        del _TOKENS[token]


def token_update(token: str) -> None:
    """Updates a specific token.

    This will not update any token but calls the hook which will format and emit if the given token
    is in use.
    """
    for f in _TOKEN_UPDATE_HOOK:
        f(token)
