"""Provider-side threading wrapper around the application discovery API."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Thread
from typing import override

from configs import conf
from platform_specific import IS_LINUX, IS_WINDOWS, UnsupportedPlatformError

from ._types import AppDetail

logger = logging.getLogger(__name__)

if IS_WINDOWS:
    from .windows.apps import build_app_list, get_recent_files, supports_recent_files
elif IS_LINUX:
    from .linux.apps import build_app_list, get_recent_files, supports_recent_files
else:
    raise UnsupportedPlatformError("application discovery")


class AppDetailsFetcher(Thread):
    def __init__(self, callback: Callable[[list[AppDetail]], None]) -> None:
        super().__init__()
        self.still_fetching: bool = False
        self._callback: Callable[[list[AppDetail]], None] = callback

    @override
    def run(self) -> None:
        """Retrieves details of apps and included shortcuts and calls given callback."""
        recent_on = supports_recent_files and conf.providers.app_provider.show_recent_files.value
        self.still_fetching = recent_on
        details = build_app_list()
        self._callback(details)  # give app list. finding recent takes a while
        self.still_fetching = False

        if recent_on:
            try:
                recent = get_recent_files(details)
                if recent:
                    self._callback(recent)
            except Exception:
                logger.exception("Failed to fetch recent files")

        logger.info("App details fetching finished")


__all__ = ["AppDetail", "AppDetailsFetcher", "build_app_list", "get_recent_files", "supports_recent_files"]
