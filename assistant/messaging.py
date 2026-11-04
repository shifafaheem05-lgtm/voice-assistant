"""Helpers for 'send a WhatsApp message to ...' and 'send an email to ...': phone numbers, links, sentence splitting."""
from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple
from urllib.parse import quote, quote_plus

DIGIT_WORDS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
               "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
_REPEAT = {"double": 2, "triple": 3}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
FILLER = {"phone", "number", "no", "mobile", "cell", "whatsapp", "is", "with", "at", "contact", "has", "its"}


def spoken_to_digits(text: str) -> str:
    """'zero three double zero' -> '0300'. Other words are left alone."""
    out, repeat = [], 1
    for token in text.lower().split():
        if token in _REPEAT:
            repeat = _REPEAT[token]
        elif token in DIGIT_WORDS:
            out.append(DIGIT_WORDS[token] * repeat)
            repeat = 1
        elif token == "plus":
            out.append("+")
        else:
            repeat = 1
            out.append(token)
    return " ".join(out)


def normalize_phone(raw: str, country_code: str = "92") -> Optional[str]:
    """'0300 1234567' -> '923001234567' (digits only, with country code). None if it is not a phone number."""
    text = spoken_to_digits(raw).strip()
    if not re.fullmatch(r"\+?[\d\s().-]+", text):
        return None
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    if text.startswith("+"):
        number = digits
    elif digits.startswith("00"):
        number = digits[2:]
    elif digits.startswith("0"):
        number = country_code + digits[1:]
    elif len(digits) <= 10 and country_code:
        number = country_code + digits
    else:
        number = digits
    return number if 8 <= len(number) <= 15 else None


def _digitish(token: str) -> bool:
    return bool(re.fullmatch(r"\+?[\d-]+", token)) or token in DIGIT_WORDS or token in _REPEAT or token == "plus"


# ------------------------------------------------------------------ links
def whatsapp_app_url(phone: str, text: str) -> str:
    """Opens the WhatsApp desktop app on that chat with the message already typed."""
    return f"whatsapp://send?phone={phone}&text={quote(text, safe='')}"


def whatsapp_web_url(phone: str, text: str) -> str:
    return f"https://web.whatsapp.com/send?phone={phone}&text={quote(text, safe='')}"


def gmail_compose_url(to: str = "", subject: str = "", body: str = "") -> str:
    return ("https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={quote_plus(to)}&su={quote_plus(subject)}&body={quote_plus(body)}")


# ------------------------------------------------------------------ sentence splitting
_SEPARATOR = re.compile(
    r"\s*(?:\bsaying(?: that)?\b|\bsay\b|\bthat says\b|\bwith (?:the )?message\b|\bmessage is\b|\bmessage\b"
    r"|\btelling (?:him|her|them)(?: that)?\b|\bto tell (?:him|her|them)(?: that)?\b)\s+|\s*:\s*", re.I)


def split_recipient_and_text(rest: str, known_names: Iterable[str] = ()) -> Tuple[str, str]:
    """'ali saying hello there' -> ('ali', 'hello there'). Works with names from your contacts or phone numbers.

    Without a word like 'saying' the best guess is: a known contact name, then a phone number, then the first word.
    """
    rest = rest.strip()
    match = _SEPARATOR.search(rest)
    if match and rest[:match.start()].strip():
        return rest[:match.start()].strip(), rest[match.end():].strip()
    # a spoken or typed phone number at the start
    tokens = rest.split()
    i = 0
    while i < len(tokens) and _digitish(tokens[i]):
        i += 1
    if i and len(re.sub(r"\D", "", spoken_to_digits(" ".join(tokens[:i])))) >= 7:
        return " ".join(tokens[:i]), " ".join(tokens[i:])
    lowered = rest.lower()
    for name in sorted(known_names, key=len, reverse=True):
        if lowered == name or lowered.startswith(name + " "):
            return rest[:len(name)], rest[len(name):].strip()
    if not tokens:
        return "", ""
    return tokens[0], " ".join(tokens[1:])


def parse_contact_details(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    """'ali 0300 1234567' / 'sara email sara at gmail dot com' -> (name, phone words, email)."""
    text = text.strip()
    email = None
    match = re.search(r"\b(?:e-?mail|mail)(?: address)?(?: is)?\s+(.+)$", text)
    if match:
        spoken = " " + match.group(1) + " "
        spoken = spoken.replace(" at the rate ", "@").replace(" at ", "@").replace(" dot ", ".")
        candidate = re.sub(r"\s+", "", spoken)
        if EMAIL.fullmatch(candidate):
            email = candidate
        text = text[:match.start()].strip()
    inline = EMAIL.search(text)
    if inline:
        email = inline.group(0)
        text = (text[:inline.start()] + " " + text[inline.end():]).strip()
    tokens = text.split()
    j = len(tokens)
    while j > 0 and _digitish(tokens[j - 1]):
        j -= 1
    phone = " ".join(tokens[j:]) or None
    name_tokens = tokens[:j]
    while name_tokens and name_tokens[-1] in FILLER:
        name_tokens.pop()
    return " ".join(name_tokens).strip(), phone, email
