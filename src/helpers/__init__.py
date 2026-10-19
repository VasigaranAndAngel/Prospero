from arg_parser import args
from platform_utils import IS_WINDOWS

if IS_WINDOWS:
    from . import windows_task_schedule_handler as task_schedule_handler
else:
    from . import linux_autostart as task_schedule_handler

if args.schtasks_handler is None:
    from ._fetch_icon import fetch_icon, fetch_windows_app_icon
    from .singleton_meta import SingletonMeta, SingletonQObjectMeta

__all__ = [
    "fetch_icon",
    "fetch_windows_app_icon",
    "SingletonMeta",
    "SingletonQObjectMeta",
    "task_schedule_handler",
]
