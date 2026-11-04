"""Short answers for 'who is ...' / 'tell me about ...' from the Wikipedia summary API."""
from __future__ import annotations

import json
import re
from typing import Callable, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
MAX_CHARS = 350


def _shorten(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    short = " ".join(sentences[:2])
    return short if len(short) <= MAX_CHARS else short[:MAX_CHARS].rsplit(" ", 1)[0] + "..."


def summary(topic: str, fetch: Callable = urlopen, timeout: float = 5.0) -> Optional[str]:
    """First sentences of the article about `topic`, or None (not found, offline, ambiguous)."""
    topic = topic.strip()
    for title in dict.fromkeys([topic.title(), topic[:1].upper() + topic[1:]]):
        url = API.format(quote(title.replace(" ", "_"), safe=""))
        try:
            request = Request(url, headers={"User-Agent": "voice-assistant/1.0 (learning project)"})
            with fetch(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:  # 404, offline, bad JSON: try the next spelling
            continue
        if data.get("type") == "standard" and data.get("extract"):
            return _shorten(data["extract"])
    return None
