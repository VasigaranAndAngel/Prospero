import os
from datetime import datetime, timedelta, timezone

import pytest
from packaging.version import Version

from constants import APPLICATION_NAME
from query_placeholder_tokens import register_query_placeholder_token
from ui._query_box._placeholder_formatter import (
    PlaceholderFormatter,
    _Metrics,
    _SystemMetrics,
)


def fmt(template: str, **overrides) -> str:
    return PlaceholderFormatter.format(template, _Metrics(**overrides))


# ---------------------------------------------------------------------------
# regression tests for the bugs found in the original implementation
# ---------------------------------------------------------------------------
class TestBugFixes:
    def test_trailing_literal_text_is_not_dropped(self):
        dt = datetime(2026, 9, 22)
        assert fmt("A{time:{YYYY}}B{time:{MM}}C", dt=dt) == "A2026B09C"

    def test_second_token_still_works_after_a_spec_ed_token(self):
        dt = datetime(2026, 9, 22, 14, 5)
        assert fmt("{time:{HH}}-{time:{YYYY}}", dt=dt) == "14-2026"

    def test_three_tokens_two_of_which_have_specs(self):
        dt = datetime(2026, 9, 22, 14, 5)
        result = fmt("{time:{HH}}:{time:{mm}} on {time:{YYYY}}", dt=dt)
        assert result == "14:05 on 2026"

    def test_unknown_token_without_spec_round_trips_without_extra_colon(self):
        assert fmt("{totally.unknown}") == "{totally.unknown}"

    def test_unknown_token_with_spec_round_trips(self):
        assert fmt("{totally.unknown:foo}") == "{totally.unknown:foo}"

    def test_escaped_braces_render_literal_without_backslash(self):
        assert fmt(r"\{time\}") == "{time}"
        assert fmt(r"\{unknown.token:spec\}") == "{unknown.token:spec}"

    def test_unclosed_token_round_trips(self):
        assert fmt("{time") == "{time"
        assert fmt("{time:{HH}") == "{time:{HH}"

    def test_stray_closing_brace_is_kept(self):
        assert fmt("a}b") == "a}b"

    def test_duplicate_registration_raises(self):
        with pytest.raises(ValueError):

            @register_query_placeholder_token("time")
            def _dup(m, spec):
                return "nope"


# ---------------------------------------------------------------------------
# unit tokens only resolve inside a meta spec ("enable_units")
# ---------------------------------------------------------------------------
class TestUnitResolutionRule:
    def test_bare_date_units_stay_literal(self):
        dt = datetime(2026, 9, 22)
        assert fmt("{YYYY}-{MM}-{DD}", dt=dt) == "{YYYY}-{MM}-{DD}"

    def test_bare_version_units_stay_literal(self):
        assert fmt("{v.major}.{v.minor}", v=Version("1.2.3")) == "{v.major}.{v.minor}"

    def test_bare_bool_unit_stays_literal(self):
        assert fmt("{b:yes|no}", b=True) == "{b:yes|no}"

    def test_bare_size_unit_stays_literal(self):
        assert fmt("{size:MB}", s=1572864) == "{size:MB}"

    def test_bare_duration_unit_stays_literal(self):
        assert fmt("{d:HH}", d=timedelta(hours=3)) == "{d:HH}"

    def test_bare_string_unit_stays_literal(self):
        assert fmt("{upper}", str_="prospero") == "{upper}"

    def test_bare_fraction_unit_stays_literal(self):
        assert fmt("{fcf}", f=0.5) == "{fcf}"

    def test_meta_token_without_spec_still_resolves(self):
        assert fmt("{app.name}") == APPLICATION_NAME


# ---------------------------------------------------------------------------
# generic unit tokens, rendered through a meta spec
# ---------------------------------------------------------------------------
class TestGenericUnits:
    def test_version_parts(self):
        v = Version("1.2.3.dev4")
        assert fmt("{time:{v}}", v=v) == "1.2.3.dev4"
        assert fmt("{time:{v.major}.{v.minor}}", v=v) == "1.2"
        assert fmt("{time:{v.major}.{v.minor}.{v.dev}}", v=v) == "1.2.4"

    def test_version_dev_empty_when_absent(self):
        assert fmt("{time:{v.major}.{v.minor}{v.dev}}", v=Version("4.5.6")) == "4.5"

    def test_version_epoch_micro(self):
        assert fmt("{time:{v.major}.{v.minor}.{v.micro}}", v=Version("1.2.3")) == "1.2.3"
        assert fmt("{time:{v}}", v=Version("1.0b1")) == "1.0b1"

    def test_bool_unit(self):
        assert fmt("{time:{b}}", b=True) == "true"
        assert fmt("{time:{b}}", b=False) == "false"
        assert fmt("{time:{b:yes|no}}", b=True) == "yes"
        assert fmt("{time:{b:yes|no}}", b=False) == "no"

    def test_size_units(self):
        assert fmt("{time:{size}}", s=1536) == "1.5KB"
        assert fmt("{time:{size:KB}}", s=1536) == "1.5"
        assert fmt("{time:{size:MB}}", s=1572864) == "1.5"
        assert fmt("{time:{size:GB}}", s=1073741824) == "1.0"
        assert fmt("{time:{size:B}}", s=1572864) == "1572864"
        assert fmt("{time:{size:bytes}}", s=1572864) == "1572864"

    def test_size_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            fmt("{time:{size:XZ}}", s=1024)

    def test_duration_humanized(self):
        d = timedelta(days=2, hours=3, minutes=4, seconds=5)
        assert fmt("{time:{d}}", d=d) == "2d 3h"

    def test_duration_parts(self):
        d = timedelta(days=2, hours=3, minutes=4, seconds=5)
        assert fmt("{time:{d:D}}", d=d) == "2"
        assert fmt("{time:{d:H}}", d=d) == "3"
        assert fmt("{time:{d:HH}}", d=d) == "03"
        assert fmt("{time:{d:M}}", d=d) == "4"
        assert fmt("{time:{d:MM}}", d=d) == "04"
        assert fmt("{time:{d:S}}", d=d) == "5"
        assert fmt("{time:{d:SS}}", d=d) == "05"

    def test_duration_total_parts(self):
        d = timedelta(days=2, hours=3, minutes=4, seconds=5)
        assert fmt("{time:{d:TH}}", d=d) == "51"
        assert fmt("{time:{d:THH}}", d=d) == "51"
        assert fmt("{time:{d:TM}}", d=d) == "3064"
        assert fmt("{time:{d:TMM}}", d=d) == "3064"
        assert fmt("{time:{d:TS}}", d=d) == "183845"
        assert fmt("{time:{d:TSS}}", d=d) == "183845"

    def test_duration_unknown_part_raises(self):
        with pytest.raises(ValueError):
            fmt("{time:{d:Q}}", d=timedelta(minutes=1))


# ---------------------------------------------------------------------------
# string modification units (from m.str_)
# ---------------------------------------------------------------------------
class TestStringUnits:
    def test_case_modifiers(self):
        assert fmt("{time:{lower}}", str_="Prospero") == "prospero"
        assert fmt("{time:{upper}}", str_="Prospero") == "PROSPERO"
        assert fmt("{time:{title}}", str_="the quick brown fox") == "The Quick Brown Fox"
        assert fmt("{time:{capitalize}}", str_="hello world") == "Hello world"

    def test_unknown_string_unit_round_trips(self):
        assert fmt("{time:{kebab}}", str_="Prospero") == "{kebab}"


# ---------------------------------------------------------------------------
# fraction units (from m.f)
# ---------------------------------------------------------------------------
class TestFractionUnits:
    def test_fixed_precision(self):
        assert fmt("{time:{ff}}", f=0.4213) == "0.42"
        assert fmt("{time:{f%}}", f=0.4213) == "42.13"

    def test_common_fraction(self):
        assert fmt("{time:{fcf}}", f=0.5) == "1/2"
        assert fmt("{time:{fcf}}", f=0.75) == "3/4"


# ---------------------------------------------------------------------------
# built-in date parts / time
# ---------------------------------------------------------------------------
class TestTime:
    def test_date_parts(self):
        dt = datetime(2026, 9, 22, 14, 5, 9)
        assert fmt("{time:{YYYY}}-{time:{MM}}-{time:{DD}}", dt=dt) == "2026-09-22"

    def test_nested_spec(self):
        dt = datetime(2026, 9, 22)
        assert fmt("{time:{MM}-{DD}-{YYYY}}", dt=dt) == "09-22-2026"

    def test_no_spec_defaults_to_isoformat(self):
        dt = datetime(2026, 9, 22, 14, 5, 9)
        assert fmt("{time}", dt=dt) == dt.isoformat(timespec="seconds")

    def test_twelve_hour_and_meridiem(self):
        dt = datetime(2026, 9, 22, 14, 5)
        assert fmt("{time:{h}{a}}", dt=dt) == "2pm"
        assert fmt("{time:{hh} {A}}", dt=dt) == "02 PM"
        assert fmt("{time:{h}{a}}", dt=datetime(2026, 9, 22, 9, 5)) == "9am"

    def test_zero_padded_seconds(self):
        dt = datetime(2026, 9, 22, 14, 5, 4)
        assert fmt("{time:{ss}}", dt=dt) == "04"
        assert fmt("{time:{s}}", dt=dt) == "4"

    def test_utc_offset_and_epoch(self):
        dt = datetime(2026, 9, 22, 14, 5)
        assert fmt("{time:{Z}}", dt=dt) == "+00:00"
        expected = int(dt.replace(tzinfo=timezone.utc).timestamp())
        assert fmt("{time:{X}}", dt=dt) == str(expected)


# ---------------------------------------------------------------------------
# app.* (driven by constants; monkeypatch for determinism)
# ---------------------------------------------------------------------------
class TestApp:
    def test_name_default_and_units(self, monkeypatch):
        monkeypatch.setattr("constants.APPLICATION_NAME", "my app")
        assert fmt("{app.name}") == "my app"
        assert fmt("{app.name:{upper}}") == "MY APP"
        assert fmt("{app.name:{lower}}") == "my app"
        assert fmt("{app.name:{title}}") == "My App"

    def test_name_nested_spec(self, monkeypatch):
        monkeypatch.setattr("constants.APPLICATION_NAME", "my app")
        assert fmt("{app.name:{upper}}") == "MY APP"

    def test_version_default_and_spec(self, monkeypatch):
        monkeypatch.setattr("constants.VERSION", Version("2.4.1"))
        assert fmt("{app.version}") == "2.4.1"
        assert fmt("{app.version:v{v.major}.{v.minor}}") == "v2.4"

    def test_version_dev_replaces_nothing(self, monkeypatch):
        monkeypatch.setattr("constants.VERSION", Version("2.4.1.dev3"))
        assert fmt("{app.version:{v.major}.{v.minor}{v.dev}}") == "2.43"

    def test_pid(self):
        assert fmt("{app.pid}") == str(os.getpid())

    def test_build_channel_env_placeholders(self):
        assert (
            fmt("{app.build}")
            == "'app.build' is not implemented. my be moved to {app.version} in future."
        )
        assert (
            fmt("{app.channel}")
            == "'app.channel' is not implemented. my be moved to {app.version} in future."
        )
        assert (
            fmt("{app.env}")
            == "'app.env' is not implemented. my be moved to {app.version} in future."
        )

    def test_uptime_default_humanized(self, monkeypatch):
        monkeypatch.setattr(
            "constants.APP_STARTED_TIME",
            datetime.now() - timedelta(hours=2, minutes=15, seconds=30),
        )
        assert fmt("{app.uptime}") == "2h 15m"

    def test_uptime_with_duration_parts(self, monkeypatch):
        monkeypatch.setattr(
            "constants.APP_STARTED_TIME", datetime.now() - timedelta(hours=1, minutes=5, seconds=30)
        )
        assert fmt("{app.uptime:{d:H}h {d:MM}m}") == "1h 05m"


# ---------------------------------------------------------------------------
# update.* (currently stubbed with placeholder text)
# ---------------------------------------------------------------------------
class TestUpdate:
    def test_all_tokens_are_placeholder_stubs(self):
        for token in (
            "available",
            "latest_version",
            "channel",
            "download_progress",
            "last_checked",
        ):
            assert fmt("{%s}" % f"update.{token}") == f"'update.{token}' is not implemented yet."


# ---------------------------------------------------------------------------
# notifications.* (currently stubbed)
# ---------------------------------------------------------------------------
class TestNotifications:
    def test_placeholders(self):
        for token in ("count", "unread", "latest", "latest_time", "priority"):
            assert (
                fmt("{%s}" % f"notifications.{token}")
                == f"'notifications.{token}' is not implemented yet."
            )


# ---------------------------------------------------------------------------
# session.* (live via psutil + getpass; monkeypatch logon time for determinism)
# ---------------------------------------------------------------------------
class TestSession:
    def test_logon_time_none(self, monkeypatch):
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_user_logon_time", lambda: None
        )
        assert fmt("{session.login_time}") == "N/A"
        assert fmt("{session.duration}") == "N/A"

    def test_login_time_default_and_spec(self, monkeypatch):
        lt = datetime(2026, 9, 22, 8, 0)
        monkeypatch.setattr("ui._query_box._placeholder_formatter._get_user_logon_time", lambda: lt)
        assert fmt("{session.login_time}") == lt.isoformat(timespec="seconds")
        assert fmt("{session.login_time:{YYYY}-{MM}-{DD}}") == "2026-09-22"

    def test_duration_default(self, monkeypatch):
        lt = datetime.now() - timedelta(minutes=42, seconds=30)
        monkeypatch.setattr("ui._query_box._placeholder_formatter._get_user_logon_time", lambda: lt)
        assert fmt("{session.duration}") == "42m"

    def test_duration_with_spec(self, monkeypatch):
        lt = datetime.now() - timedelta(hours=1, minutes=2, seconds=30)
        monkeypatch.setattr("ui._query_box._placeholder_formatter._get_user_logon_time", lambda: lt)
        assert fmt("{session.duration:{d:H}:{d:MM}}") == "1:02"

    def test_username(self):
        import getpass

        assert fmt("{session.username}") == getpass.getuser()
        assert fmt("{session.username:{upper}}") == getpass.getuser().upper()


# ---------------------------------------------------------------------------
# system.* (live via psutil; monkeypatch the snapshot for determinism)
# ---------------------------------------------------------------------------
def _snapshot(**overrides) -> _SystemMetrics:
    defaults = dict(
        os="Windows 11",
        arch="AMD64",
        hostname="my-pc",
        cpu_usage=25.0,
        memory_usage=55.0,
        battery=86,
        net_sent=1536,
        net_recv=1073741824,
        net_upload_speed=1536.0,
        net_download_speed=1536.0,
        boot_time=datetime.now() - timedelta(days=1, hours=3, seconds=30),
    )
    defaults.update(overrides)
    return _SystemMetrics(**defaults)  # pyright: ignore[reportArgumentType]


class TestSystem:
    def test_plain_fields(self, monkeypatch):
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_system_metrics", lambda: _snapshot()
        )
        assert fmt("{system.os}") == "Windows 11"
        assert fmt("{system.arch}") == "AMD64"
        assert fmt("{system.hostname}") == "my-pc"

    def test_string_modifiers(self, monkeypatch):
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_system_metrics", lambda: _snapshot()
        )
        assert fmt("{system.os:{upper}}") == "WINDOWS 11"

    def test_usage_percentages_and_fraction_units(self, monkeypatch):
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_system_metrics", lambda: _snapshot()
        )
        assert fmt("{system.cpu_usage}") == "25.0%"
        assert fmt("{system.cpu_usage:{ff}}") == "25.00"
        assert fmt("{system.cpu_usage:{f%}}") == "2500.00"
        assert fmt("{system.cpu_usage:{fcf}}") == "25"
        assert fmt("{system.memory_usage}") == "55.0%"
        assert fmt("{system.memory_usage:{f%}}") == "5500.00"

    def test_battery(self, monkeypatch):
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_system_metrics",
            lambda: _snapshot(battery=86),
        )
        assert fmt("{system.battery}") == "86%"
        assert fmt("{system.battery:{f%}}") == "86.00"
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_system_metrics",
            lambda: _snapshot(battery=None),
        )
        assert fmt("{system.battery}") == "N/A"

    def test_network_totals(self, monkeypatch):
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_system_metrics", lambda: _snapshot()
        )
        assert fmt("{system.network.sent}") == "1.5KB"
        assert fmt("{system.network.sent:{size:B}}") == "1536"
        assert fmt("{system.network.recv:{size:GB}}") == "1.0"

    def test_network_speeds(self, monkeypatch):
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_system_metrics", lambda: _snapshot()
        )
        assert fmt("{system.network.upload}") == "1.5KB/s"
        assert fmt("{system.network.download:{size:KB}}") == "1.5"

    def test_network_status_placeholder(self, monkeypatch):
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_system_metrics", lambda: _snapshot()
        )
        assert fmt("{system.network_status}") == "'system.network_status' is not implemented yet."

    def test_uptime_default_and_spec(self, monkeypatch):
        monkeypatch.setattr(
            "ui._query_box._placeholder_formatter._get_system_metrics", lambda: _snapshot()
        )
        assert fmt("{system.uptime}") == "1d 3h"
        assert fmt("{system.uptime:{d:D}d {d:HH}h}") == "1d 03h"


# ---------------------------------------------------------------------------
# a realistic combined template
# ---------------------------------------------------------------------------
def test_combined_status_bar_template(monkeypatch):
    monkeypatch.setattr("constants.VERSION", Version("1.2.3"))
    dt = datetime(2026, 9, 22, 14, 5)
    result = fmt(
        "{app.name:{title}} {app.version:v{v.major}.{v.minor}} "
        + "- {notifications.count} - {time:{HH}:{mm}} - {update.available}",
        dt=dt,
    )
    assert (
        result
        == "Prospero v1.2 - 'notifications.count' is not implemented yet. - 14:05 - 'update.available' is not implemented yet."
    )


def test_perf():
    import time

    st = time.perf_counter()
    template = (
        "{app.name} {app.version:v{v.major}.{v.minor}} " + "- {time:{HH}:{mm}} - {update.available}"
    )
    for _ in range(10_000):
        fmt(template)
    print("\n", time.perf_counter() - st)


# ---------------------------------------------------------------------------- #
#                                 token tracing                                #
# ---------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "format, used_token",
    (
        (r"{app.name}", {"app.name"}),
        (r"{app.version:v{v.major}.{v.minor}}", {"app.version", "v.major", "v.minor"}),
        (
            r"{app.name:{title}} {app.version:v{v.major}.{v.minor}} - {notifications.count} - {time:{HH}:{mm}} - {update.available}",
            {
                "app.name",
                "title",
                "app.version",
                "v.major",
                "v.minor",
                "notifications.count",
                "time",
                "HH",
                "mm",
                "update.available",
            },
        ),
    ),
)
def test_tracing_token(format: str, used_token: set[str]):
    p = PlaceholderFormatter(format)
    assert p._traced_tokens == used_token


# ---------------------------------------------------------------------------- #
#                  trigger update token from unrelated sources                 #
# ---------------------------------------------------------------------------- #
def test_token_update():
    # TODO
    pass
