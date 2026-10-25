"""POSIX single-key read for the interactive CLI."""

from __future__ import annotations

import sys


def read_key() -> str:
    """Read a single keypress without echoing it."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


__all__ = ["read_key"]
