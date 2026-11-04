"""Facts about this computer: battery, memory, CPU, disk space, IP address, internet. Nothing here changes anything."""
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import socket
import time
from ctypes import wintypes
from typing import Optional, Tuple


def is_windows() -> bool:
    return platform.system() == "Windows"


def battery() -> Optional[Tuple[int, bool]]:
    """(percent, plugged in). None on a PC without a battery or when not on Windows."""
    if not is_windows():
        return None

    class PowerStatus(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                    ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                    ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]

    status = PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):  # type: ignore[attr-defined]
        return None
    if status.BatteryLifePercent > 100:  # 255 = unknown / no battery
        return None
    return status.BatteryLifePercent, status.ACLineStatus == 1


def memory() -> Optional[Tuple[int, float, float]]:
    """(percent used, total GB, free GB). Windows only."""
    if not is_windows():
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
        return None
    gb = 1024 ** 3
    return status.dwMemoryLoad, status.ullTotalPhys / gb, status.ullAvailPhys / gb


def cpu_percent(sample_seconds: float = 0.5) -> Optional[int]:
    """CPU load over a short sample. Windows only."""
    if not is_windows():
        return None

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    def read():
        idle, kernel, user = FileTime(), FileTime(), FileTime()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))  # type: ignore[attr-defined]
        return tuple((t.high << 32) | t.low for t in (idle, kernel, user))

    i1, k1, u1 = read()
    time.sleep(sample_seconds)
    i2, k2, u2 = read()
    total = (k2 - k1) + (u2 - u1)  # kernel time already includes idle time
    if total <= 0:
        return None
    return max(0, min(100, round(100 * (1 - (i2 - i1) / total))))


def disk() -> Tuple[float, float]:
    """(free GB, total GB) of the system drive."""
    root = (os.environ.get("SystemDrive", "C:") + "\\") if is_windows() else "/"
    usage = shutil.disk_usage(root)
    gb = 1024 ** 3
    return usage.free / gb, usage.total / gb


def local_ip() -> Optional[str]:
    """Address of this computer on your network. (No data is sent: UDP 'connect' only picks a route.)"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def online(timeout: float = 2.0) -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=timeout).close()
        return True
    except OSError:
        return False


def status(kind: str) -> Optional[str]:
    """A sentence for 'battery', 'memory', 'cpu', 'disk', 'ip' or 'internet'. None if not available here."""
    if kind == "battery":
        info = battery()
        if not info:
            return None
        percent, plugged = info
        return f"The battery is at {percent} percent and {'charging' if plugged else 'not charging'}."
    if kind == "memory":
        info = memory()
        if not info:
            return None
        used, total, free = info
        return f"Memory is {used} percent used. {free:.1f} of {total:.1f} gigabytes are free."
    if kind == "cpu":
        load = cpu_percent()
        return None if load is None else f"The processor is at {load} percent."
    if kind == "disk":
        free, total = disk()
        return f"You have {free:.0f} gigabytes free on a {total:.0f} gigabyte drive."
    if kind == "ip":
        address = local_ip()
        return f"Your local IP address is {address}." if address else None
    if kind == "internet":
        return "Yes, you are online." if online() else "No, I can't reach the internet right now."
    return None
