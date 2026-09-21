"""### Providers

Providers are the result provider for the UI. The UI can call search or search_async to get the
results from all providers.

NOTE: Name of each provider class treated as the id of the provider. the `name` attribute in provider
instances are only for show in UI. They are not treated as id.
"""

import logging
from collections.abc import Callable, Collection

from arg_parser import args

from ._base_provider import BaseProvider
from ._loading_request import LoadingRequest
from .application_provider import AppProvider
from .base_result_and_widgets import (
    BaseResult,
    BaseResultBoxWidget,
    ExecutionAction,
    ResultAttributes,
    ResultBox,
)
from .calculator_provider import CalcProvider
from .command_provider import CommandProvider
from .debug_provider import DebugProvider

logger = logging.getLogger(__name__)

# TODO: get enabled providers list from config and setup according to it.
DISABLED_PROVIDERS: list[type[BaseProvider]] = [] if args.debug else [DebugProvider]
"Disabled provider types."

PROVIDERS = [AppProvider, CalcProvider, CommandProvider, DebugProvider]
"All the providers."

PROVIDERS_I = [provider() for provider in PROVIDERS if provider not in DISABLED_PROVIDERS]
"Enabled provider instances."


def search(query: str) -> Collection[BaseResult]:
    """Gives the query to all provider instances and returns the results.

    Args:
        query (str): The query

    Returns:
        Collection[BaseResult]: Returns a collection of results.
    """
    results: Collection[BaseResult] = []
    for provider in PROVIDERS_I:
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
    for provider in PROVIDERS_I:
        provider.search_async(query, callback)


def _enable_disable_provider(provider: str, enable: bool):
    for p in PROVIDERS_I:
        if type(p).__name__ == provider:
            p.enable_hook() if enable else p.disable_hook()
            return p
    err_msg = f"Cannot {'enable' if enable else 'disable'} '{provider}' provider. Not found."
    logger.error(err_msg)
    raise Exception(err_msg)


def enable_provider(provider_name: str) -> None:
    if provider_name not in map(lambda x: type(x).__name__, PROVIDERS_I):
        p = next(filter(lambda x: x.__name__ == provider_name, PROVIDERS))
        PROVIDERS_I.append(p())
        DISABLED_PROVIDERS.remove(p)
    _ = _enable_disable_provider(provider_name, True)


def disable_provider(provider_name: str) -> None:
    provider = _enable_disable_provider(provider_name, False)
    PROVIDERS_I.remove(provider)
    DISABLED_PROVIDERS.append(type(provider))


__all__ = [
    "AppProvider",
    "CalcProvider",
    "CommandProvider",
    "DebugProvider",
    "PROVIDERS",
    "PROVIDERS_I",
    "DISABLED_PROVIDERS",
    "BaseResult",
    "BaseResultBoxWidget",
    "ExecutionAction",
    "ResultAttributes",
    "ResultBox",
    "LoadingRequest",
    "search",
    "search_async",
    "enable_provider",
    "disable_provider",
]
