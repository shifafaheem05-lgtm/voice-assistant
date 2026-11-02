"""Command engine: turns a sentence into a reply. No microphone or internet needed."""
from __future__ import annotations

import random
import re
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional, Tuple
from urllib.parse import quote_plus

from .calc import CalcError, calculate, format_number
from .notes import NoteStore

SITES = {
    "google": "https://www.google.com", "youtube": "https://www.youtube.com",
    "github": "https://github.com", "gmail": "https://mail.google.com",
    "linkedin": "https://www.linkedin.com", "wikipedia": "https://www.wikipedia.org",
    "stackoverflow": "https://stackoverflow.com", "stack overflow": "https://stackoverflow.com",
}
JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I would tell you a UDP joke, but you might not get it.",
    "There are 10 kinds of people: those who understand binary and those who don't.",
    "Why did the developer go broke? Because he used up all his cache.",
    "A SQL query walks into a bar, walks up to two tables and asks: can I join you?",
]
DOMAIN = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")
HELP = ("I can tell the time and date, open websites (for example 'open youtube'), search the web "
        "('search for python tutorials'), play something on YouTube, do maths ('what is 12 times 7'), "
        "take notes ('take a note buy milk', 'read my notes'), flip a coin, roll a dice and tell a joke. "
        "Say 'exit' to stop.")


@dataclass
class Reply:
    text: str
    exit: bool = False


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[?!.,;]+$", "", text)
    return re.sub(r"\s+", " ", text)


def strip_wake_word(text: str, wake_word: Optional[str]) -> Optional[str]:
    """Return the command after the wake word, or None if the wake word was not said."""
    if not wake_word:
        return text
    pattern = rf"^\s*(?:hey\s+|ok\s+|okay\s+)?{re.escape(wake_word.lower())}\b[\s,:]*"
    if re.match(pattern, text.lower()):
        return re.sub(pattern, "", text, count=1, flags=re.I).strip()
    return None


class Assistant:
    def __init__(self, notes: Optional[NoteStore] = None,
                 opener: Callable[[str], object] = webbrowser.open,
                 now: Callable[[], datetime] = datetime.now,
                 rng: Optional[random.Random] = None) -> None:
        self.notes = notes or NoteStore()
        self.opener = opener
        self.now = now
        self.rng = rng or random.Random()
        # Order matters: commands that start with a keyword first, loose keyword matches
        # (joke, time, date) after them, the calculator last.
        self.routes: List[Tuple[re.Pattern, Callable[[re.Match], Reply]]] = [
            (re.compile(r"^(?:exit|quit|stop|goodbye|good bye|bye|shut down)\b"), self._exit),
            (re.compile(r"^(?:help|what can you do)\b"), lambda m: Reply(HELP)),
            (re.compile(r"^(?:take|add|make|write|save)(?: a| me a)? note(?: that| to)?[: ]*(.+)$"), self._add_note),
            (re.compile(r"^note[: ]+(.+)$"), self._add_note),
            (re.compile(r"^(?:read|show|list|what are)(?: me)?(?: my| all)? notes$"), self._read_notes),
            (re.compile(r"^(?:clear|delete|erase)(?: all)?(?: my)? notes$"), self._clear_notes),
            (re.compile(r"^(?:hello|hi|hey|salam|assalam[a-z ]*)\b"), lambda m: Reply("Hello! How can I help you?")),
            (re.compile(r"^(?:what(?:'s| is) your name|who are you)$"), lambda m: Reply("I'm your voice assistant, written in Python.")),
            (re.compile(r"^(?:play|search youtube for|youtube) (.+?)(?: on youtube)?$"), self._youtube),
            (re.compile(r"^(?:search for|search|google|look up) (.+)$"), self._search),
            (re.compile(r"^open (.+)$"), self._open),
            (re.compile(r"^(?:flip|toss) a coin$"), lambda m: Reply(f"It's {self.rng.choice(['heads', 'tails'])}.")),
            (re.compile(r"^roll a (?:dice|die)$"), lambda m: Reply(f"You rolled a {self.rng.randint(1, 6)}.")),
            (re.compile(r"\bjoke\b"), lambda m: Reply(self.rng.choice(JOKES))),
            (re.compile(r"\btime\b"), self._time),
            (re.compile(r"\b(?:date|today|day is it)\b"), self._date),
        ]

    # ------------------------------------------------------------ public
    def handle(self, text: str) -> Reply:
        command = normalize(text)
        if not command:
            return Reply("I didn't catch that.")
        for pattern, handler in self.routes:
            match = pattern.search(command)
            if match:
                return handler(match)
        reply = self._maths(command)
        return reply or Reply("Sorry, I don't know how to do that yet. Say 'help' to hear what I can do.")

    # ------------------------------------------------------------ handlers
    def _exit(self, m) -> Reply:
        return Reply("Goodbye!", exit=True)

    def _time(self, m) -> Reply:
        return Reply(f"It's {self.now().strftime('%I:%M %p').lstrip('0')}.")

    def _date(self, m) -> Reply:
        return Reply(f"Today is {self.now():%A, %d %B %Y}.")

    def _add_note(self, m) -> Reply:
        text = m.group(1).strip()
        if not text:
            return Reply("What should I write in the note?")
        self.notes.add(text, self.now())
        return Reply(f"Okay, I saved your note: {text}.")

    def _read_notes(self, m) -> Reply:
        notes = self.notes.all()
        if not notes:
            return Reply("You have no notes.")
        listing = "; ".join(f"{i}. {n['text']}" for i, n in enumerate(notes, start=1))
        return Reply(f"You have {len(notes)} note{'s' if len(notes) != 1 else ''}: {listing}")

    def _clear_notes(self, m) -> Reply:
        count = self.notes.clear()
        return Reply(f"Deleted {count} note{'s' if count != 1 else ''}.")

    def _search(self, m) -> Reply:
        query = m.group(1).strip()
        self.opener(f"https://www.google.com/search?q={quote_plus(query)}")
        return Reply(f"Searching the web for {query}.")

    def _youtube(self, m) -> Reply:
        query = m.group(1).strip()
        self.opener(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
        return Reply(f"Searching YouTube for {query}.")

    def _open(self, m) -> Reply:
        target = m.group(1).strip()
        if target in SITES:
            self.opener(SITES[target])
            return Reply(f"Opening {target}.")
        if DOMAIN.match(target.replace(" dot ", ".").replace(" ", "")):
            domain = target.replace(" dot ", ".").replace(" ", "")
            self.opener(f"https://{domain}")
            return Reply(f"Opening {domain}.")
        return Reply(f"I don't know the website {target}. Try a name like youtube or a domain like example.com.")

    def _maths(self, command: str) -> Optional[Reply]:
        expression = re.sub(r"^(?:calculate|compute|solve|what is|what's|how much is)\s+", "", command)
        try:
            return Reply(f"The answer is {format_number(calculate(expression))}.")
        except CalcError as exc:
            if str(exc) == "not a calculation":
                return None
            return Reply(f"Sorry, {exc}.")
