"""Timers and reminders: parse '5 minutes', format it back, and schedule a callback."""
from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional, Tuple

from .calc import _number_words

DURATION = re.compile(r"(?:\b(an?)\b|(\d+(?:\.\d+)?))\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b")
UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}
MAX_SECONDS = 24 * 3600


def parse_duration(text: str) -> Optional[float]:
    """'5 minutes', 'ten seconds', 'an hour' -> seconds. None if it is not a duration."""
    match = DURATION.search(_number_words(text.lower()))
    if not match:
        return None
    amount = 1.0 if match.group(1) else float(match.group(2))
    return amount * UNIT_SECONDS[match.group(3)[0]]


CLOCK = re.compile(r"\b(?:at |for )?(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?(?![\d:])")


def parse_clock_time(text: str, now: datetime) -> Optional[Tuple[float, datetime]]:
    """'7 am', '5:30 pm', '17:45' -> (seconds until the next time it is that o'clock, that datetime). None if not a time."""
    text = _number_words(text.lower().strip())
    match = CLOCK.fullmatch(text) or CLOCK.search(text)
    if not match:
        return None
    hour, minute, meridiem = int(match.group(1)), int(match.group(2) or 0), (match.group(3) or "").replace(".", "")
    if not meridiem and not match.group(2):
        return None  # a bare number such as "5" is not clearly a time
    if meridiem:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    if hour > 23 or minute > 59:
        return None
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds(), target


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    for unit, size in (("hour", 3600), ("minute", 60), ("second", 1)):
        if seconds >= size and (seconds % size == 0 or size == 1):
            n = seconds // size
            return f"{n} {unit}{'' if n == 1 else 's'}"
    return f"{seconds} seconds"


def thread_scheduler(seconds: float, callback: Callable[[], None]):
    """Run callback after `seconds` on a background thread. The returned timer has .cancel()."""
    timer = threading.Timer(seconds, callback)
    timer.daemon = True
    timer.start()
    return timer
