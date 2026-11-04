"""Websites by spoken name, and site-specific searches ('search amazon for headphones')."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote_plus

SITES: Dict[str, str] = {
    # search, mail, social
    "google": "https://www.google.com", "gmail": "https://mail.google.com", "bing": "https://www.bing.com",
    "duckduckgo": "https://duckduckgo.com", "yahoo": "https://www.yahoo.com",
    "youtube": "https://www.youtube.com", "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com", "twitter": "https://twitter.com", "x": "https://x.com",
    "reddit": "https://www.reddit.com", "linkedin": "https://www.linkedin.com", "pinterest": "https://www.pinterest.com",
    "tiktok": "https://www.tiktok.com", "snapchat": "https://www.snapchat.com", "twitch": "https://www.twitch.tv",
    "whatsapp web": "https://web.whatsapp.com", "telegram web": "https://web.telegram.org",
    # AI assistants
    "claude": "https://claude.ai", "chatgpt": "https://chatgpt.com", "chat gpt": "https://chatgpt.com",
    "gemini": "https://gemini.google.com", "perplexity": "https://www.perplexity.ai",
    "copilot": "https://copilot.microsoft.com", "hugging face": "https://huggingface.co",
    # Google tools
    "google drive": "https://drive.google.com", "drive": "https://drive.google.com",
    "google docs": "https://docs.google.com", "google sheets": "https://sheets.google.com",
    "google slides": "https://slides.google.com", "google maps": "https://www.google.com/maps",
    "maps": "https://www.google.com/maps", "google translate": "https://translate.google.com",
    "translate": "https://translate.google.com", "google calendar": "https://calendar.google.com",
    "google meet": "https://meet.google.com", "meet": "https://meet.google.com",
    "google photos": "https://photos.google.com", "google news": "https://news.google.com",
    "news": "https://news.google.com", "google scholar": "https://scholar.google.com",
    "google classroom": "https://classroom.google.com", "classroom": "https://classroom.google.com",
    "google images": "https://images.google.com", "google earth": "https://earth.google.com",
    # work and study
    "github": "https://github.com", "stackoverflow": "https://stackoverflow.com", "stack overflow": "https://stackoverflow.com",
    "leetcode": "https://leetcode.com", "hackerrank": "https://www.hackerrank.com", "kaggle": "https://www.kaggle.com",
    "geeksforgeeks": "https://www.geeksforgeeks.org", "w3schools": "https://www.w3schools.com",
    "medium": "https://medium.com", "dev to": "https://dev.to", "quora": "https://www.quora.com",
    "wikipedia": "https://www.wikipedia.org", "coursera": "https://www.coursera.org", "udemy": "https://www.udemy.com",
    "khan academy": "https://www.khanacademy.org", "notion": "https://www.notion.so", "figma": "https://www.figma.com",
    "canva": "https://www.canva.com", "trello": "https://trello.com", "slack": "https://slack.com",
    "zoom": "https://zoom.us", "dropbox": "https://www.dropbox.com", "onedrive": "https://onedrive.live.com",
    "outlook web": "https://outlook.live.com", "paypal": "https://www.paypal.com", "linkedin jobs": "https://www.linkedin.com/jobs",
    # shopping, entertainment
    "amazon": "https://www.amazon.com", "ebay": "https://www.ebay.com", "aliexpress": "https://www.aliexpress.com",
    "daraz": "https://www.daraz.pk", "olx": "https://www.olx.com.pk", "pakwheels": "https://www.pakwheels.com",
    "foodpanda": "https://www.foodpanda.pk", "netflix": "https://www.netflix.com", "imdb": "https://www.imdb.com",
    "soundcloud": "https://soundcloud.com", "spotify web": "https://open.spotify.com",
    # news and cricket
    "dawn": "https://www.dawn.com", "geo news": "https://www.geo.tv", "ary news": "https://arynews.tv",
    "cricbuzz": "https://www.cricbuzz.com", "espncricinfo": "https://www.espncricinfo.com", "cricinfo": "https://www.espncricinfo.com",
    "bbc": "https://www.bbc.com/news", "bbc news": "https://www.bbc.com/news", "cnn": "https://www.cnn.com",
}

# {q} is replaced with the URL-encoded search words
SEARCH_URLS: Dict[str, str] = {
    "google": "https://www.google.com/search?q={q}", "bing": "https://www.bing.com/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}", "youtube": "https://www.youtube.com/results?search_query={q}",
    "amazon": "https://www.amazon.com/s?k={q}", "ebay": "https://www.ebay.com/sch/i.html?_nkw={q}",
    "aliexpress": "https://www.aliexpress.com/wholesale?SearchText={q}", "daraz": "https://www.daraz.pk/catalog/?q={q}",
    "olx": "https://www.olx.com.pk/items/q-{q}", "pakwheels": "https://www.pakwheels.com/used-cars/search/-/?q={q}",
    "github": "https://github.com/search?q={q}", "stackoverflow": "https://stackoverflow.com/search?q={q}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={q}", "reddit": "https://www.reddit.com/search/?q={q}",
    "twitter": "https://twitter.com/search?q={q}", "x": "https://x.com/search?q={q}",
    "linkedin": "https://www.linkedin.com/search/results/all/?keywords={q}", "pinterest": "https://www.pinterest.com/search/pins/?q={q}",
    "quora": "https://www.quora.com/search?q={q}", "medium": "https://medium.com/search?q={q}",
    "imdb": "https://www.imdb.com/find?q={q}", "netflix": "https://www.netflix.com/search?q={q}",
    "maps": "https://www.google.com/maps/search/{q}", "googlemaps": "https://www.google.com/maps/search/{q}",
    "googleimages": "https://www.google.com/search?tbm=isch&q={q}", "images": "https://www.google.com/search?tbm=isch&q={q}",
    "googlenews": "https://news.google.com/search?q={q}", "news": "https://news.google.com/search?q={q}",
    "googlescholar": "https://scholar.google.com/scholar?q={q}", "scholar": "https://scholar.google.com/scholar?q={q}",
    "googledrive": "https://drive.google.com/drive/search?q={q}", "gmail": "https://mail.google.com/mail/u/0/#search/{q}",
    "spotify": "https://open.spotify.com/search/{q}", "soundcloud": "https://soundcloud.com/search?q={q}",
    "udemy": "https://www.udemy.com/courses/search/?q={q}", "coursera": "https://www.coursera.org/search?query={q}",
    "kaggle": "https://www.kaggle.com/search?q={q}", "leetcode": "https://leetcode.com/problemset/?search={q}",
    "geeksforgeeks": "https://www.geeksforgeeks.org/search/?q={q}", "w3schools": "https://www.w3schools.com/search/?q={q}",
    "huggingface": "https://huggingface.co/models?search={q}", "dictionary": "https://www.dictionary.com/browse/{q}",
    "translate": "https://translate.google.com/?sl=auto&tl=en&text={q}&op=translate",
}
# Spoken nicknames -> the name used above
ALIASES: Dict[str, str] = {
    "insta": "instagram", "fb": "facebook", "yt": "youtube", "tube": "youtube", "so": "stackoverflow",
    "wiki": "wikipedia", "gh": "github", "chat gpt": "chatgpt", "open ai": "chatgpt", "anthropic claude": "claude",
    "google map": "google maps", "map": "maps", "image": "images", "google image": "google images",
    "gdrive": "google drive", "gmeet": "google meet", "gdocs": "google docs", "gsheets": "google sheets",
}


def compact(name: str) -> str:
    """'You Tube' -> 'youtube'. Speech recognition often adds or drops spaces."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _lookup(table: Dict[str, str], name: str) -> Optional[str]:
    name = name.strip().lower()
    keys = [compact(name)] + ([compact(ALIASES[name])] if name in ALIASES else [])  # own spelling first, nickname second
    for key in keys:
        for known, value in table.items():
            if compact(known) == key:
                return value
    return None


def find_site(name: str, custom: Optional[Dict[str, str]] = None) -> Optional[str]:
    """URL for a spoken site name. Your own sites (sites.json) win over the built-in list."""
    name = name.strip()
    if not name:
        return None
    if custom:
        found = _lookup(custom, name)
        if found:
            return found
    return _lookup(SITES, name)


def search_url(site: str, query: str, custom: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Search page of a site for `query`, or None when we don't know how that site searches."""
    template = None
    if custom:
        # custom sites may use {q}: {"my wiki": "https://wiki.example.com/search?q={q}"}
        found = _lookup(custom, site)
        template = found if found and "{q}" in found else None
    if template is None:
        template = _lookup(SEARCH_URLS, site)
    if template is None:
        return None
    return template.replace("{q}", quote_plus(query))


def load_custom_sites(path="sites.json") -> Dict[str, str]:
    """Read {"my blog": "https://example.com"} from a JSON file. Missing or broken files give {}."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).lower(): v.strip() for k, v in data.items()
            if isinstance(v, str) and re.match(r"^https?://", v.strip(), re.I)}
