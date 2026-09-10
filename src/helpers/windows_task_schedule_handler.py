"""
## Prospero Startup-at-Logon Task Scheduler Handler

Uses `powershell.exe` to add and Windows `schtasks` via subprocess.run to remove, and query a
scheduled task that launches Prospero at user logon.
"""

# NOTE: Avoid importing too much since this will be imported on --schtasks-handler mode.
import atexit
import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, TypeVar

from constants import APPLICATION_PATH, RUNNING_AS_ADMIN

logger = logging.getLogger(__name__)  # This logger will be used in both main and elevated process.

_TASK_NAME = "Prospero Startup"


# region Runs from process with --schtasks-handler mode.
def _run(args: Sequence[str]):
    """Run a schtasks command and return (success, output)."""
    import subprocess

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    success = result.returncode == 0
    output = result.stdout if success else result.stderr
    return success, output.strip()


def _add_task():
    """Create a scheduled task to run at logon for the current user. Returns True if success."""
    # fmt: off
    # args = [
    #     "schtasks.exe", "/Create",
    #     "/SC", "ONLOGON",
    #     "/TN", _TASK_NAME,
    #     "/TR", f'"{APPLICATION_PATH}"',
    #     "/F"                # overwrite if it already exists
    # ]
    # fmt: on
    script = [
        f'$action = New-ScheduledTaskAction -Execute "{APPLICATION_PATH}"',
        "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME",
        "$setting = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries",
        f'Register-ScheduledTask -TaskName "{_TASK_NAME}" -Action $action -Settings $setting -Trigger $trigger',
    ]
    # fmt: off
    command = [
        "powershell.exe", "-NonInteractive", "-NoProfile",
        "-WindowStyle", "Hidden",
        "-Command", "; ".join(script),
    ]
    # fmt: on
    logger.debug(f"Executing powershell command: {command}")
    success, output = _run(command)
    if success:
        logger.debug(f"Task '{_TASK_NAME}' created to run at logon.")
    else:
        logger.error(f"Failed to create task '{_TASK_NAME}': {output}")
    return success


def _remove_task() -> bool:
    """Delete the scheduled task. Returns True if success."""
    args = ["schtasks", "/Delete", "/TN", _TASK_NAME, "/F"]
    success, output = _run(args)
    if success:
        logger.debug(f"Task '{_TASK_NAME}' removed.")
    else:
        logger.error(f"Failed to remove task '{_TASK_NAME}': {output}")
    return success


def _query_task() -> tuple[bool, str]:
    """Query the scheduled task and returns its details. Returns True if success."""
    args = ["schtasks", "/Query", "/TN", _TASK_NAME, "/FO", "LIST", "/V"]
    success, output = _run(args)
    if success:
        logger.debug(f"Task '{_TASK_NAME}' details:\n{output}")
    else:
        logger.error(f"Task '{_TASK_NAME}' not found or query failed: {output}")
    return success, output


def start_listener(auth_key: str, port: str):
    from multiprocessing.connection import Listener

    AUTHKEY = auth_key
    PORT = int(port)

    listener = Listener(("localhost", PORT), authkey=AUTHKEY.encode())
    conn = listener.accept()
    try:
        while True:
            request = conn.recv()  # pyright: ignore[reportAny]
            logger.debug(f"Request received: {request}")
            if request == "exit":
                conn.send({"ok": True})
                break
            match request:
                case "_add_task":
                    response = _add_task()
                case "_remove_task":
                    response = _remove_task()
                case "_query_task":
                    response = _query_task()
                case _:  # pyright: ignore[reportAny]
                    response = None
            logger.debug(f"Response sending back: {response}")
            conn.send(response)
    finally:
        conn.close()
        listener.close()

    import sys

    sys.exit()


# endregion


def _get_free_port():  # pyright: ignore[reportAny]
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]  # pyright: ignore[reportAny]


if TYPE_CHECKING:
    from multiprocessing.connection import Connection, PipeConnection

_client_connection: "Connection | PipeConnection | None" = None
_key_and_port: tuple[bytes, str] | None = None


def launch_elevated_handler():
    import ctypes
    import secrets
    import sys

    if RUNNING_AS_ADMIN:
        logger.warning("Already running elevated. aborting elevation.")
        return

    authkey = secrets.token_hex(16)
    port = _get_free_port()  # pyright: ignore[reportAny]
    params = ""

    if getattr(sys, "frozen", False):
        exe_path = str(APPLICATION_PATH)
    else:
        exe_path = sys.executable
        params += " src/main.py "

    params += f"--schtasks-handler {authkey} {port}"

    logger.debug(f"Launching elevated application...")
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, params, None, 0)  # pyright: ignore[reportAny]
    if result <= 32:
        raise OSError(f"Elevation failed or was denied, code {result}")

    return authkey.encode(), port


def _connect_with_retry(
    authkey: bytes, port: int, retries: int = 40, delay: float = 0.25
) -> "Connection | PipeConnection":
    import time
    from multiprocessing.connection import Client

    for _ in range(retries):
        try:
            return Client(("localhost", port), authkey=authkey)
        except (ConnectionRefusedError, OSError):
            time.sleep(delay)
    raise TimeoutError("Could not connect to elevated helper")


def _get_connection() -> "Connection | PipeConnection":
    global _client_connection, _key_and_port
    if _client_connection is None:
        if _key_and_port is None:
            _key_and_port = launch_elevated_handler()
            if _key_and_port is None:
                # This will never happen because _execute() function never
                raise RuntimeError("Already might running as admin")
        key, port = _key_and_port
        con = _connect_with_retry(key, int(port))
        _client_connection = con
    return _client_connection


TOutputVar = TypeVar("TOutputVar")


def _execute(func: Callable[[], TOutputVar], callback: Callable[[TOutputVar], None]) -> None:
    """Sends the request through the connection and waits for response.

    The given func will be called and returned value will be sent to given callback if the
    application already running as admin. otherwise get connection with _get_connection (which
    starts elevated process if not started yet), sends a request to run the function and waits for
    the result to send it to the callback.
    Supported functions are: `_add_task`, `_query_task`, `_remove_task`

    Args:
        func (Callable[[], TOutputVar]): One of supported functions.
        callback (Callable[[TOutputVar], None]): A callable to be called with received result.
    """
    logger.debug(f"Executing {func.__name__}")
    if RUNNING_AS_ADMIN:
        callback(func())
    else:
        con = _get_connection()
        con.send(func.__name__)
        res = con.recv()  # pyright: ignore[reportAny]
        callback(res)  # pyright: ignore[reportAny]


def stop_elevated_handler() -> bool:
    if _key_and_port is None:
        return True
    if _client_connection is None:
        return True
    con = _get_connection()
    con.send("exit")
    return con.recv()["ok"]  # pyright: ignore[reportAny]


def add_task(callback: Callable[[bool], None]) -> None:
    _execute(_add_task, callback)


def remove_task(callback: Callable[[bool], None]) -> None:
    _execute(_remove_task, callback)


def query_task(callback: Callable[[tuple[bool, str]], None]) -> None:
    _execute(_query_task, callback)


# Register task_schedule_handler to request the elevated process to stop.
_ = atexit.register(stop_elevated_handler)


__all__ = [
    "launch_elevated_handler",
    "stop_elevated_handler",
    "add_task",
    "remove_task",
    "query_task",
]
