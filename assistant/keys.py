"""Spoken keyboard shortcuts ('refresh' = F5, 'new tab' = Ctrl+T ...). Windows only.

The keys go to whichever window is in front, so this works best in voice mode with your browser or app in focus.
"""
from __future__ import annotations

import ctypes
import platform
from typing import Callable, List, Optional

KEYEVENTF_KEYUP = 2
VK = {
    "CTRL": 0x11, "SHIFT": 0x10, "ALT": 0x12, "WIN": 0x5B, "TAB": 0x09, "ENTER": 0x0D, "ESC": 0x1B,
    "LEFT": 0x25, "RIGHT": 0x27, "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "PRINTSCREEN": 0x2C, "F5": 0x74, "F11": 0x7A, "PLUS": 0xBB, "MINUS": 0xBD, "0": 0x30,
    "MEDIA_NEXT": 0xB0, "MEDIA_PREV": 0xB1, "MEDIA_PLAY_PAUSE": 0xB3,
    **{letter: ord(letter) for letter in "ACDFSTVWXYZ"},
}
SHORTCUTS = {
    "refresh": ["F5"], "hard_refresh": ["CTRL", "F5"], "back": ["ALT", "LEFT"], "forward": ["ALT", "RIGHT"],
    "new_tab": ["CTRL", "T"], "close_tab": ["CTRL", "W"], "next_tab": ["CTRL", "TAB"],
    "previous_tab": ["CTRL", "SHIFT", "TAB"], "reopen_tab": ["CTRL", "SHIFT", "T"],
    "scroll_down": ["PAGEDOWN"], "scroll_up": ["PAGEUP"], "top": ["HOME"], "bottom": ["END"],
    "zoom_in": ["CTRL", "PLUS"], "zoom_out": ["CTRL", "MINUS"], "zoom_reset": ["CTRL", "0"],
    "fullscreen": ["F11"], "copy": ["CTRL", "C"], "paste": ["CTRL", "V"], "cut": ["CTRL", "X"],
    "select_all": ["CTRL", "A"], "undo": ["CTRL", "Z"], "redo": ["CTRL", "Y"], "save": ["CTRL", "S"],
    "find": ["CTRL", "F"], "switch_window": ["ALT", "TAB"], "show_desktop": ["WIN", "D"],
    "screenshot": ["WIN", "PRINTSCREEN"],  # Windows saves it in Pictures > Screenshots
    "enter": ["ENTER"], "escape": ["ESC"],
    "media_play_pause": ["MEDIA_PLAY_PAUSE"], "media_next": ["MEDIA_NEXT"], "media_prev": ["MEDIA_PREV"],
}

# (what you say as a regular expression, shortcut name, spoken reply)
COMMANDS = [
    (r"^(?:refresh|reload)(?: the| this)?(?: page| tab| window| screen| browser)?$|^(?:press )?f5$", "refresh", "Refreshing."),
    (r"^(?:hard|force) (?:refresh|reload)(?: the)?(?: page| tab)?$", "hard_refresh", "Hard refresh."),
    (r"^(?:go )?back(?: a page| one page)?$|^previous page$", "back", "Going back."),
    (r"^(?:go )?forward(?: a page| one page)?$|^next page$", "forward", "Going forward."),
    (r"^(?:open )?(?:a )?new tab$", "new_tab", "New tab."),
    (r"^close (?:the |this )?tab$", "close_tab", "Closing the tab."),
    (r"^(?:next|switch) tab$", "next_tab", "Next tab."),
    (r"^(?:previous|last) tab$", "previous_tab", "Previous tab."),
    (r"^(?:reopen|restore)(?: the)?(?: last| closed)? tab$|^undo close tab$", "reopen_tab", "Reopening the tab."),
    (r"^scroll down$", "scroll_down", "Scrolling down."),
    (r"^scroll up$", "scroll_up", "Scrolling up."),
    (r"^(?:scroll to|go to) (?:the )?top(?: of (?:the )?page)?$", "top", "Going to the top."),
    (r"^(?:scroll to|go to) (?:the )?(?:bottom|end)(?: of (?:the )?page)?$", "bottom", "Going to the bottom."),
    (r"^zoom in$", "zoom_in", "Zooming in."),
    (r"^zoom out$", "zoom_out", "Zooming out."),
    (r"^(?:reset|normal) zoom$", "zoom_reset", "Zoom reset."),
    (r"^(?:exit |toggle )?full ?screen$", "fullscreen", "Toggled full screen."),
    (r"^copy(?: this| that| it)?$", "copy", "Copied."),
    (r"^paste(?: it| here| that)?$", "paste", "Pasted."),
    (r"^cut(?: this| that| it)?$", "cut", "Cut."),
    (r"^select all$", "select_all", "Selected all."),
    (r"^undo(?: that)?$", "undo", "Undone."),
    (r"^redo(?: that)?$", "redo", "Redone."),
    (r"^save(?: this| the)?(?: file| page| document)?$", "save", "Saving."),
    (r"^find (?:on|in) (?:this |the )?page$", "find", "Find is open."),
    (r"^(?:switch|change) (?:the )?(?:window|app|application)s?$|^alt tab$", "switch_window", "Switching window."),
    (r"^show (?:the )?desktop$|^minimi[sz]e (?:all|everything)(?: windows)?$", "show_desktop", "Showing the desktop."),
    (r"^(?:take (?:a )?)?screenshot$|^capture (?:the )?screen$", "screenshot",
     "Screenshot taken. You'll find it in Pictures, Screenshots."),
    (r"^(?:press|hit) enter$", "enter", "Enter."),
    (r"^(?:press|hit) escape$|^escape$", "escape", "Escape."),
    (r"^(?:pause|resume|play pause)(?: the)?(?: music| video| song)?$", "media_play_pause", "Okay."),
    (r"^(?:next|skip)(?: song| track)?$", "media_next", "Next track."),
    (r"^previous (?:song|track)$", "media_prev", "Previous track."),
]


def _key_event(vk: int, up: bool) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP if up else 0, 0)  # type: ignore[attr-defined]


def send_shortcut(name: str, key_event: Optional[Callable[[int, bool], None]] = None) -> bool:
    """Press the keys of a known shortcut (modifiers first, released in reverse). False if unknown or unsupported."""
    keys: Optional[List[str]] = SHORTCUTS.get(name)
    if keys is None:
        return False
    if key_event is None:
        if platform.system() != "Windows":
            return False
        key_event = _key_event
    for key in keys:
        key_event(VK[key], False)
    for key in reversed(keys):
        key_event(VK[key], True)
    return True


KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1
MAX_TYPED = 500


def _send_units(units: List[int]) -> bool:
    """Type UTF-16 code units into the focused window with SendInput (works for any language, no clipboard needed)."""
    from ctypes import wintypes

    class KeyboardInput(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class MouseInput(ctypes.Structure):  # only here so the union has the real size Windows expects
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class InputUnion(ctypes.Union):
        _fields_ = [("ki", KeyboardInput), ("mi", MouseInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", InputUnion)]

    events = []
    for unit in units:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            events.append(Input(INPUT_KEYBOARD, InputUnion(ki=KeyboardInput(0, unit, flags, 0, 0))))
    array = (Input * len(events))(*events)
    sent = ctypes.windll.user32.SendInput(len(events), array, ctypes.sizeof(Input))  # type: ignore[attr-defined]
    return sent == len(events)


def type_text(text: str, send: Optional[Callable[[List[int]], bool]] = None) -> bool:
    """Type `text` into whichever window is in front. False if empty, too long, or not Windows."""
    if not text or len(text) > MAX_TYPED:
        return False
    if send is None:
        if platform.system() != "Windows":
            return False
        send = _send_units
    data = text.encode("utf-16-le")
    units = [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
    return send(units)
