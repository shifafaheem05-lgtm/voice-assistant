"""Open desktop apps by spoken name. Windows only; only the names listed here can be launched."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

# spoken name -> program Windows knows how to start (fixed list, user text is never executed)
APPS: Dict[str, str] = {
    "notepad": "notepad", "calculator": "calc", "calc": "calc", "paint": "mspaint",
    "command prompt": "cmd", "cmd": "cmd", "terminal": "cmd", "powershell": "powershell",
    "file explorer": "explorer", "explorer": "explorer", "files": "explorer",
    "task manager": "taskmgr", "snipping tool": "snippingtool", "settings": "ms-settings:",
    "chrome": "chrome", "google chrome": "chrome", "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox", "vs code": "code", "vscode": "code", "visual studio code": "code",
    "word": "winword", "microsoft word": "winword", "excel": "excel", "microsoft excel": "excel",
    "powerpoint": "powerpnt", "microsoft powerpoint": "powerpnt", "outlook": "outlook",
    # apps that Windows opens through their own link type (they must be installed)
    "whatsapp": "whatsapp:", "spotify": "spotify:", "telegram": "tg:", "discord": "discord:",
    "teams": "msteams:", "microsoft teams": "msteams:", "camera": "microsoft.windows.camera:",
    "clock": "ms-clock:", "alarms": "ms-clock:", "photos": "ms-photos:", "calendar": "outlookcal:",
    "store": "ms-windows-store:", "microsoft store": "ms-windows-store:", "control panel": "control",
}
# If the desktop app is not installed, these open in the browser instead
WEB_FALLBACKS: Dict[str, str] = {
    "whatsapp:": "https://web.whatsapp.com", "spotify:": "https://open.spotify.com",
    "msteams:": "https://teams.microsoft.com", "discord:": "https://discord.com/app",
    "outlook": "https://outlook.live.com", "outlookcal:": "https://outlook.live.com/calendar",
}
# spoken name -> process name for "close notepad" (a fixed list; it asks the program to close, it never force-kills)
PROCESSES: Dict[str, str] = {
    "notepad": "notepad.exe", "calculator": "CalculatorApp.exe", "calc": "CalculatorApp.exe", "paint": "mspaint.exe",
    "task manager": "Taskmgr.exe", "snipping tool": "SnippingTool.exe", "chrome": "chrome.exe", "google chrome": "chrome.exe",
    "edge": "msedge.exe", "microsoft edge": "msedge.exe", "firefox": "firefox.exe", "vs code": "Code.exe",
    "vscode": "Code.exe", "visual studio code": "Code.exe", "word": "WINWORD.EXE", "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE", "outlook": "OUTLOOK.EXE", "whatsapp": "WhatsApp.exe", "spotify": "Spotify.exe",
    "telegram": "Telegram.exe", "discord": "Discord.exe", "teams": "ms-teams.exe", "microsoft teams": "ms-teams.exe",
    "vlc": "vlc.exe", "zoom": "Zoom.exe", "photos": "Microsoft.Photos.exe",
}
FOLDERS = {"downloads": "Downloads", "documents": "Documents", "desktop": "Desktop", "pictures": "Pictures",
           "music": "Music", "videos": "Videos", "home": ""}
APPS_BY_COMPACT_NAME = {name.replace(" ", ""): cmd for name, cmd in APPS.items()}  # "note pad" -> "notepad"


def find_app(name: str, custom: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Program for a spoken app name. Your own apps (apps.json) win over the built-in list."""
    key = name.replace(" ", "")
    if custom:
        for spoken, command in custom.items():
            if spoken.lower().replace(" ", "") == key:
                return command
    return APPS_BY_COMPACT_NAME.get(key)


def find_process(name: str) -> Optional[str]:
    key = name.lower().replace(" ", "")
    for spoken, process in PROCESSES.items():
        if spoken.replace(" ", "") == key:
            return process
    return None


def close_app(name: str, run=None) -> Optional[bool]:
    """Ask a program to close. None = I don't know that app, False = couldn't (not running / not Windows), True = done."""
    process = find_process(name)
    if process is None:
        return None
    if run is None:
        if not hasattr(os, "startfile"):  # not Windows
            return False
        run = subprocess.run
    try:
        run(["taskkill", "/IM", process], check=True, capture_output=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def load_custom_apps(path="apps.json") -> Dict[str, str]:
    """Read {"my game": "C:\\Games\\game.exe"} from a JSON file. Missing or broken files give {}."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).lower(): v for k, v in data.items() if isinstance(v, str) and v.strip()}


def launch(command: str) -> bool:
    """Start the program. Returns False if it is not installed or this is not Windows."""
    if not hasattr(os, "startfile"):  # not Windows
        return False
    try:
        os.startfile(command)
        return True
    except OSError:
        path = shutil.which(command)  # e.g. 'code' is a .cmd file on the PATH
        if not path:
            return False
        try:
            subprocess.Popen([path], shell=path.lower().endswith((".cmd", ".bat")))
            return True
        except OSError:
            return False
