import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache, partial
from typing import ClassVar

from packaging.version import Version
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QWidget

from constants import VERSION
from query_placeholder_tokens import (
    _TOKEN_UPDATE_HOOK,  # pyright: ignore[reportPrivateUsage]
    _TOKENS,  # pyright: ignore[reportPrivateUsage]
)
from query_placeholder_tokens import register_query_placeholder_token as register_token

__all__ = ["register_token", "PlaceholderFormatter"]


def _discard_token_update_hook(hook: Callable[[str], None], *_: object) -> None:
    """Remove a formatter's update hook when its object is destroyed.

    ``QObject.destroyed`` passes the (already half-deleted) object, so the extra positional
    argument is accepted and ignored. ``discard`` is used instead of ``remove`` so a missing
    entry never raises while the interpreter is tearing down.
    """
    _TOKEN_UPDATE_HOOK.discard(hook)


@dataclass
class _Metrics:
    v: Version = VERSION
    dt: datetime = field(default_factory=datetime.now)
    b: bool = False
    d: timedelta = field(default_factory=timedelta)
    s: int = 0
    str_: str = ""
    f: float = 0


def _format_offset(dt: datetime) -> str:
    """Return UTC offset in the format +/-HH:MM for a given datetime."""
    offset = dt.utcoffset()
    if offset is None:
        return "+00:00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    return f"{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


_UNIT_TOKENS: dict[str, Callable[[_Metrics, str], str]] = {
    # date/time parts (from m.dt, spec ignored)
    "YYYY": lambda m, _spec: f"{m.dt.year:04d}",
    "YY": lambda m, _spec: f"{m.dt.year % 100:02d}",
    "MMMM": lambda m, _spec: m.dt.strftime("%B"),
    "MMM": lambda m, _spec: m.dt.strftime("%b"),
    "MM": lambda m, _spec: f"{m.dt.month:02d}",
    "M": lambda m, _spec: str(m.dt.month),
    "DD": lambda m, _spec: f"{m.dt.day:02d}",
    "D": lambda m, _spec: str(m.dt.day),
    "dddd": lambda m, _spec: m.dt.strftime("%A"),
    "ddd": lambda m, _spec: m.dt.strftime("%a"),
    "HH": lambda m, _spec: f"{m.dt.hour:02d}",
    "H": lambda m, _spec: str(m.dt.hour),
    "hh": lambda m, _spec: f"{(m.dt.hour % 12) or 12:02d}",
    "h": lambda m, _spec: str((m.dt.hour % 12) or 12),
    "mm": lambda m, _spec: f"{m.dt.minute:02d}",
    "m": lambda m, _spec: str(m.dt.minute),
    "ss": lambda m, _spec: f"{m.dt.second:02d}",
    "s": lambda m, _spec: str(m.dt.second),
    "SSS": lambda m, _spec: f"{m.dt.microsecond // 1000:03d}",
    "A": lambda m, _spec: "AM" if m.dt.hour < 12 else "PM",
    "a": lambda m, _spec: "am" if m.dt.hour < 12 else "pm",
    "Z": lambda m, _spec: _format_offset(m.dt),
    "X": lambda m, _spec: str(
        int(m.dt.timestamp() if m.dt.tzinfo else m.dt.replace(tzinfo=timezone.utc).timestamp())
    ),
    # version parts (from m.v)
    "v": lambda m, _spec: str(m.v),
    "v.epoch": lambda m, _spec: str(m.v.epoch),
    "v.major": lambda m, _spec: str(m.v.major),
    "v.minor": lambda m, _spec: str(m.v.minor),
    "v.micro": lambda m, _spec: str(m.v.micro),
    "v.dev": lambda m, _spec: "" if m.v.dev is None else str(m.v.dev),
    # bool (from m.b, optional label spec "yes|no")
    "b": lambda m, spec: _render_bool(m.b, spec),
    # size (from m.s, bytes; spec selects a fixed unit, default is human-readable)
    "size": lambda m, spec: _human_size(m.s) if not spec else _size_to(m.s, spec),
    # duration (from m.d; spec selects a part, default is human-readable)
    "d": lambda m, spec: _humanize_duration(m.d) if not spec else _duration_part(m.d, spec),
    # string related modifications
    "lower": lambda m, spec: m.str_.lower(),
    "upper": lambda m, spec: m.str_.upper(),
    "title": lambda m, spec: m.str_.title(),
    "capitalize": lambda m, spec: m.str_.capitalize(),
    # fraction related
    "ff": lambda m, spec: f"{m.f:.2f}",
    "f%": lambda m, spec: f"{m.f * 100:.2f}",
    "fcf": lambda m, spec: _common_fraction(m.f),  # e.g.: 1/2, 3/4
}


def _humanize_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _seconds = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _duration_part(td: timedelta, part: str) -> str:
    total = int(td.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = {
        "D": str(days),
        "H": str(hours),
        "HH": f"{hours:02d}",
        "M": str(minutes),
        "MM": f"{minutes:02d}",
        "S": str(seconds),
        "SS": f"{seconds:02d}",
        "TH": str(total // 3600),
        "THH": f"{total // 3600:02d}",
        "TM": str(total // 60),
        "TMM": f"{total // 60:02d}",
        "TS": str(total),
        "TSS": f"{total:02d}",
    }
    if part not in parts:
        raise ValueError(f"Unknown duration part {part!r}")
    return parts[part]


def _relative_time(dt: datetime, now: datetime) -> str:
    seconds = int((now - dt).total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _size_to(num_bytes: int, unit: str) -> str:
    scales = {"B": 0, "bytes": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4}
    if unit not in scales:
        raise ValueError(f"Unknown size unit {unit!r}")
    if scales[unit] == 0:
        return str(num_bytes)
    return f"{float(num_bytes) / 1024 ** scales[unit]:.1f}"


def _common_fraction(f: float) -> str:
    from fractions import Fraction

    return str(Fraction(f).limit_denominator(10))


def _render_bool(
    value: bool, spec: str, default_true: str = "true", default_false: str = "false"
) -> str:
    # TODO: Check validity when format is updated.
    valid = False
    lst = ""
    found_pipe = False
    for c in spec:
        if c == "|" and lst != "\\":
            if found_pipe:
                valid = False
            else:
                found_pipe = True
                valid = True
        lst = c

    if spec and valid:
        true_label, _, false_label = spec.partition("|")
        false_label = false_label or default_false
    else:
        true_label, false_label = default_true, default_false
    return true_label if value else false_label


class PlaceholderFormatter(QObject):
    """
    A token-based placeholder formatter with two kinds of tokens. Tokens are case-sensitive.

    Meta tokens (dotted names like ``app.version``, ``update.last_checked``) are registered via
    ``@register_token``. On ``{meta:spec}`` the handler runs with ``spec``; it gathers the relevant
    data into a ``_Metrics`` instance and either re-enters ``format()`` to parse the spec (nested
    meta and unit tokens, e.g. ``{update.last_checked:{YYYY}-{MM}-{DD}}``) or interprets the spec
    as a plain unit keyword itself (e.g. ``{app.name:title}``).
    """

    # TODO: Check validity of format on format update.

    updated: "Signal" = Signal(str)
    _token_update_signal: Signal = Signal(str)  # to move to main thread
    _trace_tokens: ClassVar[bool] = False
    _traced_tokens: ClassVar[set[str]] = set()
    "Traced registered tokens."

    def __init__(self, fmt: str, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._fmt: str = fmt

        self._timer: QTimer = QTimer(self)
        self._timer.setInterval(100)  # TODO: should be set from config
        # TODO: handle special cases like updating for Updater response and faster updates if needed
        _ = self._timer.timeout.connect(self._format_and_emit)

        self.set_formatter(fmt)
        _ = self._token_update_signal.connect(self._token_update)
        # Add the *exact* callable the destroyed handler removes. The old code added
        # ``self._token_update_signal.emit`` but removed ``self._token_update`` (a different
        # bound method), which raised a KeyError once the C++ object was gone and left a
        # dangling hook behind.
        hook = self._token_update_signal.emit
        _TOKEN_UPDATE_HOOK.add(hook)
        _ = self.destroyed.connect(partial(_discard_token_update_hook, hook))

    def _token_update(self, token: str) -> None:
        if PlaceholderFormatter._token_in_use(token):
            self._format_and_emit()

    def _format_and_emit(self) -> None:
        self.updated.emit(self.format(self._fmt))

    @classmethod
    def _token_in_use(cls, token: str) -> bool:
        return token in cls._traced_tokens

    def set_formatter(self, formatter: str) -> None:
        self._fmt = formatter

        # trace tokens
        PlaceholderFormatter._trace_tokens = True
        PlaceholderFormatter._traced_tokens = set()
        _ = _format(formatter)
        PlaceholderFormatter._trace_tokens = False

        # set the timer according to traced_tokens
        if self._token_in_use("SSS"):
            self._timer.setInterval(1)  # TODO: limit to refresh rate of screen
        else:
            self._timer.setInterval(100)  # TODO: set from config

    def start(self) -> None:
        self._timer.start()
        self._format_and_emit()  # For the first update

    def end(self) -> None:
        self._timer.stop()

    @staticmethod
    def format(fmt: str, metrics: "_Metrics | None" = None, *, enable_units: bool = False) -> str:
        metrics = metrics or _Metrics()
        last = ""
        final = ""
        _buffer = ""
        _token_buffer = ""
        token = False
        _spec = False
        depth = 0
        for c in fmt:
            if c == "{" and last != "\\":
                if not _spec:
                    token = True
                    depth += 1
                    final += _buffer
                    _buffer = ""
                else:
                    depth += 1
                    _buffer += c
            elif c == "}" and last != "\\" and token and depth == 1:
                token = False
                depth = 0
                if _spec:
                    _tk, _sp = _token_buffer, _buffer
                else:
                    _tk, _sp = _buffer, ""
                _spec = False
                if PlaceholderFormatter._trace_tokens:
                    PlaceholderFormatter._traced_tokens.add(_tk)
                if _tk in _TOKENS:
                    final += _TOKENS[_tk].call(metrics, _sp)
                elif enable_units and _tk in _UNIT_TOKENS:
                    final += _UNIT_TOKENS[_tk](metrics, _sp)
                elif _sp:
                    final += "{" + _tk + ":" + _sp + "}"  # leave as-is
                else:
                    final += "{" + _tk + "}"  # leave as-is, no invented ':'
                _buffer = ""
                _token_buffer = ""
            elif c == "}" and last != "\\" and _spec and depth > 1:
                depth -= 1
                _buffer += c
            elif c == ":" and last != "\\" and token and not _spec:
                _spec = True
                _token_buffer = _buffer
                _buffer = ""
            elif c == "{" and last == "\\":
                _buffer = _buffer[:-1] + c
            elif c == "}" and last == "\\":
                _buffer = _buffer[:-1] + c
            else:
                _buffer += c
            last = c
        if token:
            _buffer = "{" + (_token_buffer + ":" if _spec else "") + _buffer
        return final + _buffer  # flush any trailing literal text


_format = PlaceholderFormatter.format


# region time related tokens
@register_token("time", metrics_required=True, spec_required=True)
def _time(m: _Metrics, spec: str) -> str:
    # m.dt = datetime.now()
    return _format(spec, m, enable_units=True) if spec else m.dt.isoformat(timespec="seconds")


# endregion


# region app.*
@register_token("app.name", metrics_required=True, spec_required=True)
def _app_name(m: _Metrics, spec: str) -> str:
    from constants import APPLICATION_NAME as AN

    m.str_ = AN
    return _format(spec, m, enable_units=True) if spec else m.str_


@register_token("app.version", metrics_required=True, spec_required=True)
def _app_version(m: _Metrics, spec: str) -> str:
    from constants import VERSION as V

    m.v = V
    return _format(spec, m, enable_units=True) if spec else str(V)


@register_token(
    "app.build",
    placeholder="is not implemented. my be moved to {app.version} in future.",
)
def _app_build() -> str:
    return "{app.build} is not implemented. may be moved to {app.version} in future."


@register_token(
    "app.channel",
    placeholder="is not implemented. my be moved to {app.version} in future.",
)
def _app_channel() -> str:
    return "{app.channel} is not implemented. may be moved to {app.version} in future."


@register_token(
    "app.env",
    placeholder="is not implemented. my be moved to {app.version} in future.",
)
def _app_env() -> str:
    return "{app.env} is not implemented. may be moved to {app.version} in future."


@register_token("app.pid")
def _app_pid() -> str:
    import os

    return str(os.getpid())


@register_token("app.uptime", metrics_required=True, spec_required=True)
def _app_uptime(m: _Metrics, spec: str) -> str:
    from constants import APP_STARTED_TIME

    delta = datetime.now() - APP_STARTED_TIME
    m.d = delta
    return _format(spec, m, enable_units=True) if spec else _humanize_duration(delta)


# endregion


# region update.* # TODO
@register_token(
    "update.available",
    placeholder="is not implemented yet.",
    metrics_required=True,
    spec_required=True,
)
def _update_available(m: _Metrics, spec: str) -> str:
    m.b = False
    return _format(spec, m, enable_units=True) if spec else ("Yes" if m.b else "No")


@register_token(
    "update.latest_version",
    placeholder="is not implemented yet.",
    metrics_required=True,
    spec_required=True,
)
def _update_latest_version(m: _Metrics, spec: str) -> str:
    m.v = Version("")
    return _format(spec, m, enable_units=True) if spec else str(m.v)


@register_token("update.channel", placeholder="is not implemented yet.")
def _update_channel() -> str:
    raise NotImplementedError


@register_token(
    "update.download_progress",
    placeholder="is not implemented yet.",
    metrics_required=True,
    spec_required=True,
)
def _update_download_progress(m: _Metrics, spec: str) -> str:
    from typing import cast

    downloaded = u_progress = cast(float | None, None)
    if u_progress is None or downloaded is None:
        return "N/A"

    m.f = u_progress
    m.s = int(downloaded)

    unit = spec.strip() or "%"
    if unit in {"B", "bytes"}:
        return _format("{size:bytes}", m, enable_units=True)
    if unit == "size":
        return _format("{size}", m, enable_units=True)
    raise ValueError(f"Unknown unit {unit!r} for update.download_progress")


@register_token(
    "update.last_checked",
    placeholder="is not implemented yet.",
    metrics_required=True,
    spec_required=True,
)
def _update_last_checked(m: _Metrics, spec: str) -> str:
    m.dt = datetime.now()
    return _format(spec, m, enable_units=True) if spec else m.dt.isoformat(timespec="seconds")


# endregion


# region notifications.*
@register_token("notifications.count", placeholder="is not implemented yet.")
def _notifications_count() -> str:
    return "N/A"


@register_token("notifications.unread", placeholder="is not implemented yet.")
def _notifications_unread() -> str:
    return "N/A"


@register_token("notifications.latest", placeholder="is not implemented yet.")
def _notifications_latest() -> str:
    return "N/A"


@register_token("notifications.latest_time", placeholder="is not implemented yet.")
def _notifications_latest_time() -> str:
    return "N/A"


@register_token("notifications.priority", placeholder="is not implemented yet.")
def _notifications_priority() -> str:
    return "N/A"


# endregion


# region session.*
@lru_cache(1)
def _get_user_logon_time():
    try:
        import getpass

        import psutil

        all_users = psutil.users()
        if not all_users:
            return None

        target = getpass.getuser().casefold()
        users = [u for u in all_users if u.name.casefold() == target] or all_users
        return datetime.fromtimestamp(max(u.started for u in users))
    except Exception:
        return None


@register_token("session.duration", metrics_required=True, spec_required=True)
def _session_duration(m: _Metrics, spec: str) -> str:
    lt = _get_user_logon_time()
    if lt is None:
        return "N/A"

    delta = datetime.now() - lt
    m.d = delta
    return _format(spec, m, enable_units=True) if spec else _humanize_duration(delta)


@register_token("session.login_time", metrics_required=True, spec_required=True)
def _session_login_time(m: _Metrics, spec: str) -> str:
    lt = _get_user_logon_time()
    if lt is None:
        return "N/A"

    m.dt = lt
    return _format(spec, m, enable_units=True) if spec else lt.isoformat(timespec="seconds")


@register_token("session.username", metrics_required=True, spec_required=True)
def _session_username(m: _Metrics, spec: str) -> str:
    import getpass

    m.str_ = getpass.getuser()
    return _format(spec, m, enable_units=True) if spec else m.str_


# endregion


# region system.*
@dataclass(frozen=True)
class _SystemMetrics:
    os: str
    arch: str
    hostname: str
    cpu_usage: float
    memory_usage: float
    battery: int | None
    net_sent: int
    net_recv: int
    net_upload_speed: float
    net_download_speed: float
    boot_time: datetime


_SYSTEM_METRICS_TTL = 1.0
_SYSTEM_METRICS_CACHE: tuple[float, _SystemMetrics] | None = None
_NET_PREV: tuple[float, int, int] | None = None


def _get_system_metrics() -> _SystemMetrics:
    global _SYSTEM_METRICS_CACHE, _NET_PREV

    now = time.monotonic()
    if _SYSTEM_METRICS_CACHE is not None and now - _SYSTEM_METRICS_CACHE[0] < _SYSTEM_METRICS_TTL:
        return _SYSTEM_METRICS_CACHE[1]

    try:
        import platform

        import psutil
    except ImportError:
        return _SystemMetrics("", "", "", 0.0, 0.0, None, 0, 0, 0.0, 0.0, datetime.now())

    counters = psutil.net_io_counters()
    net_sent = int(counters.bytes_sent)
    net_recv = int(counters.bytes_recv)
    if _NET_PREV is not None:
        elapsed = now - _NET_PREV[0]
        if elapsed > 0:
            upload = max(0, (net_sent - _NET_PREV[1]) / elapsed)
            download = max(0, (net_recv - _NET_PREV[2]) / elapsed)
        else:
            upload = download = 0.0
    else:
        upload = download = 0.0
    _NET_PREV = (now, net_sent, net_recv)  # pyright: ignore[reportConstantRedefinition]

    battery = psutil.sensors_battery()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    metrics = _SystemMetrics(
        os=platform.system(),
        arch=platform.machine(),
        hostname=platform.node(),
        cpu_usage=psutil.cpu_percent(None),
        memory_usage=psutil.virtual_memory().percent,  # pyright: ignore[reportAny]
        battery=None if battery is None else round(battery.percent),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        net_sent=net_sent,
        net_recv=net_recv,
        net_upload_speed=upload,
        net_download_speed=download,
        boot_time=datetime.fromtimestamp(psutil.boot_time()),
    )
    _SYSTEM_METRICS_CACHE = (now, metrics)  # pyright: ignore[reportConstantRedefinition]
    return metrics


@register_token("system.os", metrics_required=True, spec_required=True)
def _system_os(m: _Metrics, spec: str) -> str:
    m.str_ = _get_system_metrics().os
    return _format(spec, m, enable_units=True) if spec else m.str_


@register_token("system.arch", metrics_required=True, spec_required=True)
def _system_arch(m: _Metrics, spec: str) -> str:
    m.str_ = _get_system_metrics().arch
    return _format(spec, m, enable_units=True) if spec else m.str_


@register_token("system.hostname", metrics_required=True, spec_required=True)
def _system_hostname(m: _Metrics, spec: str) -> str:
    m.str_ = _get_system_metrics().hostname
    return _format(spec, m, enable_units=True) if spec else m.str_


@register_token("system.cpu_usage", metrics_required=True, spec_required=True)
def _system_cpu_usage(m: _Metrics, spec: str) -> str:
    m.f = _get_system_metrics().cpu_usage
    return _format(spec, m, enable_units=True) if spec else f"{m.f:.1f}%"


@register_token("system.memory_usage", metrics_required=True, spec_required=True)
def _system_memory_usage(m: _Metrics, spec: str) -> str:
    m.f = _get_system_metrics().memory_usage
    return _format(spec, m, enable_units=True) if spec else f"{m.f:.1f}%"


@register_token("system.battery", metrics_required=True, spec_required=True)
def _system_battery(m: _Metrics, spec: str) -> str:
    battery = _get_system_metrics().battery
    if battery is None:
        return "N/A"
    m.f = battery / 100
    return _format(spec, m, enable_units=True) if spec else f"{battery}%"


@register_token("system.network.sent", metrics_required=True, spec_required=True)
def _system_net_sent(m: _Metrics, spec: str) -> str:
    return _format_net(m, spec, _get_system_metrics().net_sent)


@register_token("system.network.recv", metrics_required=True, spec_required=True)
def _system_net_recv(m: _Metrics, spec: str) -> str:
    return _format_net(m, spec, _get_system_metrics().net_recv)


@register_token("system.network.upload", metrics_required=True, spec_required=True)
def _system_net_upload(m: _Metrics, spec: str) -> str:
    return _format_net(m, spec, _get_system_metrics().net_upload_speed, speed=True)


@register_token("system.network.download", metrics_required=True, spec_required=True)
def _system_net_download(m: _Metrics, spec: str) -> str:
    return _format_net(m, spec, _get_system_metrics().net_download_speed, speed=True)


def _format_net(m: _Metrics, spec: str, value: int | float, *, speed: bool = False) -> str:
    if spec:
        return _format(spec, replace(m, s=int(value)), enable_units=True)
    text = _human_size(int(value))
    return f"{text}/s" if speed else text


@register_token(
    "system.network_status",
    placeholder="is not implemented yet.",
    metrics_required=True,
    spec_required=True,
)
def _system_network_status(m: _Metrics, spec: str) -> str:
    m.b = False
    return _format(spec, m, enable_units=True) if spec else "ConnectionType" if False else "Offline"


@register_token("system.uptime", metrics_required=True, spec_required=True)
def _system_uptime(m: _Metrics, spec: str) -> str:
    delta = datetime.now() - _get_system_metrics().boot_time
    m.d = delta
    return _format(spec, m, enable_units=True) if spec else _humanize_duration(delta)


# endregion
