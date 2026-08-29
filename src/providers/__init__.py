"""### Providers

Providers are the result provider for the UI. The UI can call search or search_async to get the
results from all providers.
"""

from collections.abc import Callable, Collection

from ._base_result import BaseResult, ExecutionActions
from ._loading_request import LoadingRequest
from .application_provider import AppProvider
from .calculator_provider import CalcProvider
from .command_provider import CommandProvider
from .debug_provider import DebugProvider

PROVIDERS = [AppProvider, CalcProvider, CommandProvider, DebugProvider]
"All the providers."

_PROVIDERS_I = [provider() for provider in PROVIDERS]
"All the provider instances."


def search(query: str) -> Collection[BaseResult]:
    """Gives the query to all provider instances and returns the results.

    Args:
        query (str): The query

    Returns:
        Collection[BaseResult]: Returns a collection of results.
    """
    results: Collection[BaseResult] = []
    for provider in _PROVIDERS_I:
        results.extend(provider.search(query))
    return results


def search_async(
    query: str, callback: Callable[[Collection[BaseResult] | LoadingRequest], None]
) -> None:
    """Gives the query to all provider instances and searches in different thread.

    The provider will execute the search method in different thread and calls the callback when
    search is done. This if for get rid of blocking UI thread. Some providers would call the
    callback with LoadingRequest for tell UI to show loading indicator.

    Args:
        query (str): The query
        callback (Callable): A callable to be called with results or LoadingRequest as parameter.
    """
    for provider in _PROVIDERS_I:
        provider.search_async(query, callback)


__all__ = [
    "AppProvider",
    "CalcProvider",
    "CommandProvider",
    "DebugProvider",
    "PROVIDERS",
    "BaseResult",
    "ExecutionActions",
    "LoadingRequest",
]
