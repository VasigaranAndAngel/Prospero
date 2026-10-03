import weakref

from query_placeholder_tokens import (
    _TOKENS,
    register_query_placeholder_token,
    unregister_query_placeholder_token,
)


def test_register_query_placeholder_token() -> None:
    token_name = "test.register_token"

    @register_query_placeholder_token(token_name)
    def foo(*_) -> str: ...

    assert token_name in _TOKENS
    assert _TOKENS[token_name].func == foo


def test_register_query_placeholder_token_placeholder() -> None:
    token_name = "test.register_token2"
    ph = "P Holder"

    @register_query_placeholder_token(token_name, placeholder=ph)
    def foo(*_) -> str: ...

    assert token_name in _TOKENS
    assert _TOKENS[token_name].call(None, None) == f"'{token_name}' {ph}"  # pyright: ignore[reportArgumentType]


def test_unregister_query_placeholder_token() -> None:
    tn = "test.unregister"

    @register_query_placeholder_token(tn)
    def foo() -> str: ...

    ref = weakref.ref(foo)
    assert _TOKENS[tn].func == ref()
    del foo
    assert _TOKENS[tn].func == ref()

    unregister_query_placeholder_token(tn)
    assert tn not in _TOKENS
    assert ref() == None  # make sure its removed entirely
