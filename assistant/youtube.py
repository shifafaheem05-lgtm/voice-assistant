"""Find the first YouTube video for a search, so 'play ...' can open it directly."""
from __future__ import annotations

import re
from typing import Callable, Optional
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

VIDEO_ID = re.compile(r'"videoRenderer":\{"videoId":"([\w-]{11})"')


def first_video_url(query: str, fetch: Callable = urlopen, timeout: float = 5.0) -> Optional[str]:
    """Return the watch URL of the top result, or None if it cannot be found (offline, page changed)."""
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
        with fetch(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception:  # offline, blocked, timeout: the caller falls back to the search page
        return None
    match = VIDEO_ID.search(html)
    return f"https://www.youtube.com/watch?v={match.group(1)}" if match else None
