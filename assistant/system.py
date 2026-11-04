"""Control the computer: volume and power actions. Windows only; nothing here runs user-supplied text."""
from __future__ import annotations

import ctypes
import platform
import subprocess
from typing import Callable, Optional

VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF
KEYEVENTF_KEYUP = 2
STEP_PERCENT = 2        # one volume key press changes the volume by 2 percent
NUDGE_PRESSES = 5       # "volume up" = 5 presses = 10 percent
SHUTDOWN_DELAY = 30     # seconds, so "cancel shutdown" has time to work

POWER_COMMANDS = {
    "shutdown": ["shutdown", "/s", "/t", str(SHUTDOWN_DELAY)],
    "restart": ["shutdown", "/r", "/t", str(SHUTDOWN_DELAY)],
    "cancel": ["shutdown", "/a"],
    "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
    "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
    "logoff": ["shutdown", "/l"],
}


def is_windows() -> bool:
    return platform.system() == "Windows"


def _press_key(vk: int) -> None:
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def volume(action: str, value: Optional[int] = None, press: Optional[Callable[[int], None]] = None) -> bool:
    """action: 'up', 'down', 'mute' (toggles) or 'set' with value 0-100. Returns False if unsupported."""
    if press is None:
        if not is_windows():
            return False
        press = _press_key
    if action == "up":
        presses = [VK_VOLUME_UP] * NUDGE_PRESSES
    elif action == "down":
        presses = [VK_VOLUME_DOWN] * NUDGE_PRESSES
    elif action == "mute":
        presses = [VK_VOLUME_MUTE]
    elif action == "set" and value is not None and 0 <= value <= 100:
        # go to zero first, then climb: the volume keys only move the level in steps
        presses = [VK_VOLUME_DOWN] * (100 // STEP_PERCENT) + [VK_VOLUME_UP] * round(value / STEP_PERCENT)
    else:
        return False
    for key in presses:
        press(key)
    return True


def power(action: str, run: Optional[Callable] = None) -> bool:
    """action: 'shutdown', 'restart', 'cancel', 'lock', 'sleep' or 'logoff'. Returns False if it failed or is unsupported."""
    command = POWER_COMMANDS.get(action)
    if command is None:
        return False
    if run is None:
        if not is_windows():
            return False
        run = subprocess.run
    try:
        run(command, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


BRIGHTNESS_STEP = 10
_BRIGHTNESS_GET = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
_BRIGHTNESS_SET = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{})"


def _powershell(script: str, run: Callable):
    return run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
               capture_output=True, text=True, check=True, timeout=15)


def brightness(action: str, value: Optional[int] = None, run: Optional[Callable] = None) -> bool:
    """action: 'up', 'down' or 'set' with value 0-100. Works on laptop screens; most desktop monitors don't support it."""
    if run is None:
        if not is_windows():
            return False
        run = subprocess.run
    try:
        if action == "set" and value is not None:
            level = int(value)
        elif action in ("up", "down"):
            current = int(_powershell(_BRIGHTNESS_GET, run).stdout.strip().splitlines()[0])
            level = current + (BRIGHTNESS_STEP if action == "up" else -BRIGHTNESS_STEP)
        else:
            return False
        level = max(0, min(100, level))  # an int, so nothing from the user ever reaches PowerShell as text
        _powershell(_BRIGHTNESS_SET.format(level), run)
        return True
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return False
