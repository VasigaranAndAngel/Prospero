"""Tests for change hooks on config values."""

from pydantic import Field

from config_models import BaseCategory, ChangeEvent, ConfigValue, Container
from config_models._config_value import takes_event
from configs._configs import Configs

# region takes_event


def bare() -> None:
    """Takes nothing."""


def with_event(event: ChangeEvent) -> None:
    """Takes the event. The signature is the test input, so the body does nothing."""
    del event


def with_optional_event(event: ChangeEvent | None) -> None:
    """Takes the event, but says it is optional."""
    del event


def with_unrelated_annotation(event: str) -> None:
    """Takes a parameter, but not a ChangeEvent."""
    del event


class Hooks:
    def bound_bare(self) -> None:
        """Takes nothing."""

    def bound_with_event(self, event: ChangeEvent) -> None:
        """Takes the event."""
        del event

    def bound_with_optional_event(self, event: ChangeEvent | None) -> None:
        """Takes the event, but says it is optional."""
        del event


def test_a_function_without_parameters_is_called_bare() -> None:
    assert takes_event(bare) is False


def test_a_function_annotated_with_change_event_takes_the_event() -> None:
    assert takes_event(with_event) is True


def test_an_optional_change_event_still_counts_as_taking_the_event() -> None:
    assert takes_event(with_optional_event) is True


def test_an_unrelated_annotation_does_not_count_as_taking_the_event() -> None:
    assert takes_event(with_unrelated_annotation) is False


def test_a_bound_method_without_parameters_is_called_bare() -> None:
    assert takes_event(Hooks().bound_bare) is False


def test_a_bound_method_annotated_with_change_event_takes_the_event() -> None:
    assert takes_event(Hooks().bound_with_event) is True


def test_a_bound_optional_change_event_takes_the_event() -> None:
    assert takes_event(Hooks().bound_with_optional_event) is True


# endregion

# region emitting


_calls: list[str] = []
_events: list[ChangeEvent] = []


def _record_bare() -> None:
    _calls.append("bare")


def _record_event(event: ChangeEvent) -> None:
    _events.append(event)


class Recorder(BaseCategory):
    """A category that only exists to hold a value to change."""

    number: ConfigValue[int] = ConfigValue(value=0)


class Root(Container):
    """A container wrapping a category, the shape BaseSettings builds."""

    # default_factory, not a bare instance, because pydantic copies a model field default
    # without rerunning model_post_init, which would leave the children pointing at the
    # template instance instead of this one.
    section: Recorder = Field(default_factory=Recorder)


def test_a_bare_hook_receives_the_change() -> None:
    value = ConfigValue(value=1)
    value.subscribe(_record_bare)

    value.value = 2

    assert _calls == ["bare"]


def test_an_annotated_hook_receives_the_event() -> None:
    value = ConfigValue(value=1)
    value.subscribe(_record_event)

    value.value = 2

    assert len(_events) == 1
    assert _events[0].value == 2


def test_a_bare_hook_does_not_crash() -> None:
    """Regression: a hook with no annotations used to raise KeyError: 'self'."""
    value = ConfigValue(value=1)
    value.subscribe(bare)

    value.value = 2


def test_the_event_bubbles_to_a_parent() -> None:
    root = Root()
    root.section.subscribe(_record_event)
    before = len(_events)

    root.section.number.value = 7

    assert len(_events) == before + 1
    assert _events[-1].value == 7


def test_the_event_path_walks_up_to_the_root() -> None:
    root = Root()
    root.section.subscribe(_record_event)

    root.section.number.value = 7

    assert _events[-1].path == ".section.number"


def test_the_source_is_the_value_that_changed() -> None:
    root = Root()
    root.section.subscribe(_record_event)

    root.section.number.value = 7

    assert _events[-1].source is root.section.number  # pyright: ignore[reportUnknownMemberType]


# endregion

# region configs_root


def test_the_root_config_honours_a_hook_that_takes_no_arguments() -> None:
    """Regression: Configs._emit used to call func(event) on every hook, unconditionally.

    The hook list is replaced first so the real save hook the app subscribes never runs and
    no config file is written by a test.
    """
    settings = Configs()
    fired: list[str] = []
    # The hook list is replaced first so the real save hook the app subscribes never runs.
    settings._change_hooks = [lambda: fired.append("bare")]  # pyright: ignore[reportPrivateUsage]

    source = ConfigValue(value=1)
    event = ChangeEvent(path="", value=None, source=source)
    settings._emit(event)  # pyright: ignore[reportPrivateUsage]

    assert fired == ["bare"]


# endregion
