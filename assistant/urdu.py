"""Roman-Urdu / Hinglish commands ('whatsapp kholo', 'ali ko hello bhejo') rewritten into the English commands.

Typed Roman Urdu always works. In voice mode try `--language en-IN`, which usually writes Urdu/Hindi words in Latin letters.
"""
from __future__ import annotations

import re
from typing import List, Tuple

_OPEN = r"(?:kholo|khol do|kholdo|kholein|kholna|chalao|chala do|chalado|open karo|open kar do|open kardo)"
_SEND = r"(?:bhejo|bhej do|bhejdo|send karo|send kar do|send kardo|likho|likh do)"
_HOURS = re.compile(r"\b(?:ghanta|ghante|ghanty)\b")
_MINUTES = re.compile(r"\b(?:minat|minute|minut)\b")

# (pattern, replacement) - the first one that matches wins
RULES: List[Tuple[re.Pattern, str]] = [(re.compile(p), r) for p, r in [
    # jokes first: 'ek mazaaq sunao' would otherwise look like 'play ... sunao'
    (r"^(?:koi )?(?:mazaaq|mazak|latifa|joke) (?:sunao|suna do|batao|suno)$|^ek (?:mazaaq|mazak|latifa|joke) (?:sunao|suna do)$",
     "tell me a joke"),
    # messages: "ali ko hello bhejo", "ali ko whatsapp pe message bhejo ke main late hoon"
    (rf"^(.+?) ko (?:whatsapp )?(?:pe |par |per )?(?:message|msg|sms) (?:bhejo|bhej do|bhejdo|karo|kardo|kar do)(?: ke| ki ye| ye)? ?(.+)$",
     r"send whatsapp message to \1 saying \2"),
    (r"^(.+?) ko (?:whatsapp )?(?:pe |par |per )?(?:message|msg|sms) (?:bhejo|bhej do|bhejdo|karo|kardo|kar do)$",
     r"send whatsapp message to \1"),
    (rf"^(.+?) ko (?:whatsapp )?(?:pe |par |per )?(.+?) {_SEND}$", r"send whatsapp message to \1 saying \2"),
    (r"^(.+?) ko email (?:karo|kardo|kar do|bhejo|bhej do)$", r"send email to \1"),
    # open / search / play
    (r"^(.+?) (?:pe|par|per) (.+?) (?:search karo|search kar do|search kardo|dhoondo|dhundo|talash karo|talash kar do)$",
     r"search \2 on \1"),
    (r"^(.+?) (?:search karo|search kar do|search kardo|dhoondo|dhundo|talash karo|google karo)$", r"search for \1"),
    (r"^(.+?) (?:bajao|baja do|play karo|play kar do|sunao|suna do)$", r"play \1"),
    (rf"^(.+?) {_OPEN}$", r"open \1"),
    # information
    (r"^(?:abhi )?(?:time|waqt|samay) (?:kya hai|kitna hua hai|batao|bata do|kya hua hai)$|^kitne baje hain?$|^kya (?:time|waqt) hua hai$",
     "what time is it"),
    (r"^(?:aaj|aj) (?:ki|kya) (?:date|tareekh|tarikh)(?: kya hai| hai)?$|^aaj kaun sa din hai$|^(?:date|tareekh|tarikh) (?:kya hai|batao)$",
     "what is the date today"),
    (r"^(?:aaj )?(?:ka )?mausam(?: kaisa hai| batao| kya hai)?$", "weather"),
    (r"^(.+?) (?:ka|ke) mausam(?: kaisa hai| batao| kya hai)?$", r"weather in \1"),
    (r"^(?:kya kar sakte ho|tum kya kar sakte ho|madad karo|madad chahiye|help karo)$", "help"),
    (r"^(?:khuda hafiz|allah hafiz|alvida|band ho jao)$", "exit"),
    (r"^(?:khabrein|khabar|news) (?:sunao|dikhao|batao)$", "news"),
    # volume, power
    (r"^(?:awaaz|awaz|volume|sound) (?:barhao|badhao|zyada karo|tez karo|up karo)$", "volume up"),
    (r"^(?:awaaz|awaz|volume|sound) (?:kam karo|ghatao|halki karo|down karo|kam kar do)$", "volume down"),
    (r"^(?:awaaz|awaz|volume|sound) (?:band karo|band kar do|mute karo|mute kar do)$", "mute"),
    (r"^(?:computer|pc|laptop) (?:band karo|band kar do|shutdown karo)$", "shut down"),
    (r"^(?:computer|pc|laptop) restart karo$", "restart"),
    (r"^(?:computer|pc|laptop|screen) lock (?:karo|kar do|kardo)$|^lock (?:karo|kar do|kardo)$", "lock the computer"),
    (r"^screenshot (?:lo|le lo|lelo)$", "take a screenshot"),
    # generic "X band karo" last, so 'awaaz band karo' and 'computer band karo' are matched above
    (r"^(.+?) (?:band karo|band kar do|band kardo|close karo|close kar do)$", r"close \1"),
    (r"^(?:roshni|brightness) (?:barhao|badhao|zyada karo)$", "brightness up"),
    (r"^(?:roshni|brightness) (?:kam karo|ghatao|kam kar do)$", "brightness down"),
    # notes, timers
    (r"^(?:yaad rakho|note karo|note kar lo|likh lo|likh do) (.+)$", r"take a note \1"),
    (r"^(?:mere )?notes (?:dikhao|sunao|batao|padho)$", "read my notes"),
    (r"^(.+?) ka (?:timer|alarm) (?:lagao|laga do|set karo|set kar do|lagana)$", r"set a timer for \1"),
    (r"^(.+?) (?:baad|mein|me) (?:mujhe )?yaad dilao (?:ke |ki )?(.+)$", r"remind me in \1 to \2"),
]]
_CONJUNCTION = re.compile(r"\s+(?:aur phir|phir|aur)\s+")
_WHATSAPP_OPEN_PREFIX = re.compile(rf"^whatsapp {_OPEN}(?: aur| phir| or)? (?=\S)")


def _units(text: str) -> str:
    return _MINUTES.sub("minutes", _HOURS.sub("hours", text))


def _rewrite(command: str) -> str:
    for pattern, template in RULES:
        match = pattern.match(command)
        if match:
            result = match.expand(template)
            return _units(result) if "timer" in result or "remind" in result else result
    return command


def to_english(command: str) -> str:
    """Return the English command, or `command` unchanged if it isn't a known Roman-Urdu pattern."""
    command = _WHATSAPP_OPEN_PREFIX.sub("", command)  # sending a message opens WhatsApp anyway
    parts = _CONJUNCTION.split(command)
    if len(parts) > 1:  # "youtube kholo aur google kholo": only if every part is understood
        rewritten = [_rewrite(p) for p in parts]
        if all(new != old for new, old in zip(rewritten, parts)) and not any(r.startswith("send ") for r in rewritten):
            return " and ".join(rewritten)
    return _rewrite(command)  # a single command (its text may contain "aur")
