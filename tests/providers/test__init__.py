import gc
import weakref

import pytest

from providers import (
    DISABLED_PROVIDERS,
    PROVIDERS,
    PROVIDERS_I,
    BaseProvider,  # pyright: ignore[reportPrivateLocalImportUsage]
    disable_provider,
    enable_provider,
)


def test_disabled_provider() -> None:
    "Check that disabled providers are not loaded."
    for p in PROVIDERS_I:
        assert type(p) not in DISABLED_PROVIDERS


def test_enable_provider() -> None:
    if not len(DISABLED_PROVIDERS) > 0:
        disable_provider(PROVIDERS[0].__name__)
    p = DISABLED_PROVIDERS[0]  # loaded first provider.
    enable_provider(p.__name__)
    assert any(isinstance(i, p) for i in PROVIDERS_I)
    assert p not in DISABLED_PROVIDERS


def test_disable_provider() -> None:
    "Check if enabling a provider removes and deletes the instance."
    if not len(PROVIDERS_I) > 0:
        enable_provider(PROVIDERS[0].__name__)
    p = PROVIDERS_I[0]  # first enabled provider.
    disable_provider(type(p).__name__)
    assert type(p) in DISABLED_PROVIDERS
    assert p not in PROVIDERS_I


@pytest.mark.parametrize(("provider"), PROVIDERS)
def test_all_providers_garbage_collected_after_disabled(provider: type[BaseProvider]) -> None:
    if provider in DISABLED_PROVIDERS:
        enable_provider(provider.__name__)

    provider_i = next(filter(lambda x: isinstance(x, provider), PROVIDERS_I))
    disable_provider(type(provider_i).__name__)
    ref = weakref.ref(provider_i)
    del provider_i
    _ = gc.collect()
    assert ref() is None, f"{provider.__name__} is not garbage collected: {gc.get_referrers(ref())}"
