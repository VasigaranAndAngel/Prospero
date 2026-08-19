import subprocess
import winreg


def shutdown_respect_hybrid(force: bool = True):
    """
    Shut down Windows, honoring the current Fast Startup (HiberbootEnabled) setting.

    If Fast Startup is enabled -> hybrid shutdown (/hybrid)
    If Fast Startup is disabled -> full shutdown (no /hybrid)

    force: if True, adds /f to force-close running applications.
    """
    key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Power"

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "HiberbootEnabled")
            fast_startup_enabled = bool(value)
    except FileNotFoundError:
        # Key/value missing (older Windows, or hibernation unsupported) -> treat as disabled
        fast_startup_enabled = False

    cmd = ["shutdown", "/s", "/t", "0"]

    if fast_startup_enabled:
        cmd.append("/hybrid")
    if force:
        cmd.append("/f")

    _ = subprocess.run(cmd, check=True)
