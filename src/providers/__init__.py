from collections.abc import Collection

from ._base_result import BaseResult, ExecutionActions
from .application_provider import AppProvider
from .calculator_provider import CalcProvider
from .command_providers import CommandProvider
from .debug_provider import DebugProvider

PROVIDERS = [AppProvider, CalcProvider, CommandProvider, DebugProvider]

_PROVIDERS_I = [provider() for provider in PROVIDERS]


def search(query: str) -> Collection[BaseResult]:
    results: Collection[BaseResult] = []
    for provider in _PROVIDERS_I:
        results.extend(provider.search(query))
    return results


__all__ = [
    "AppProvider",
    "CalcProvider",
    "CommandProvider",
    "DebugProvider",
    "PROVIDERS",
    "BaseResult",
    "ExecutionActions",
]
