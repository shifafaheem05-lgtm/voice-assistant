"""Command engine: turns a sentence into a reply. No microphone or internet needed."""
from __future__ import annotations

import queue
import random
import re
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from urllib.parse import quote, quote_plus

from .apps import FOLDERS, WEB_FALLBACKS, close_app, find_app, launch
from .calc import CalcError, _number_words, calculate, format_number
from .contacts import ContactStore
from .convert import convert_units, currency_code, fetch_rate, parse_conversion
from .keys import COMMANDS as KEY_COMMANDS, send_shortcut, type_text
from .messaging import (gmail_compose_url, normalize_phone, parse_contact_details, split_recipient_and_text,
                        whatsapp_app_url, whatsapp_web_url)
from .notes import NoteStore
from .sites import SITES, find_site, search_url
from .sysinfo import status as system_status
from .system import SHUTDOWN_DELAY, brightness, power, volume
from .timers import MAX_SECONDS, format_duration, parse_clock_time, parse_duration, thread_scheduler
from .urdu import to_english
from .wiki import summary as wiki_summary
from .youtube import first_video_url

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I would tell you a UDP joke, but you might not get it.",
    "There are 10 kinds of people: those who understand binary and those who don't.",
    "Why did the developer go broke? Because he used up all his cache.",
    "A SQL query walks into a bar, walks up to two tables and asks: can I join you?",
    "Why do Java developers wear glasses? Because they don't C sharp.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "I'd tell you a joke about recursion, but first I'd have to tell you a joke about recursion.",
    "Why was the computer cold? It left its Windows open.",
    "There's no place like 127.0.0.1.",
]
QUOTES = [
    "The secret of getting ahead is getting started. - Mark Twain",
    "It always seems impossible until it's done. - Nelson Mandela",
    "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
    "The only way to do great work is to love what you do. - Steve Jobs",
    "Believe you can and you're halfway there. - Theodore Roosevelt",
    "Small steps every day add up to big results.",
]
LANGUAGES = {
    "english": "en", "urdu": "ur", "hindi": "hi", "arabic": "ar", "french": "fr", "german": "de", "spanish": "es",
    "italian": "it", "portuguese": "pt", "russian": "ru", "turkish": "tr", "chinese": "zh-CN", "japanese": "ja",
    "korean": "ko", "punjabi": "pa", "persian": "fa", "farsi": "fa", "bengali": "bn", "pashto": "ps",
    "sindhi": "sd", "dutch": "nl", "greek": "el", "indonesian": "id", "malay": "ms",
}
STATUS_WORDS = {
    "battery": r"battery(?: percentage| level| status| life| charge)?",
    "memory": r"(?:memory|ram)(?: usage| status)?",
    "cpu": r"(?:cpu|processor)(?: usage| load| status)?",
    "disk": r"(?:disk|storage|hard ?disk|drive)(?: space| usage| status)?",
    "ip": r"(?:local )?ip(?: address)?",
}
KNOWLEDGE = re.compile(r"^(?:tell me about|who is|who was|who are|what is|what are|what was|define|explain)\s+(?:an? |the )?(.+)$")
YES = {"yes", "yeah", "yep", "sure", "confirm", "do it", "go ahead", "yes do it", "send it", "send", "yes send it", "haan", "ji", "ji haan"}
NO = {"no", "nope", "cancel", "never mind", "nevermind", "don't", "stop", "nahi", "nahin", "ruko"}
DOMAIN = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")
HELP = ("I can tell the time and date, open websites and apps ('open youtube', 'open notepad', 'close notepad'), "
        "search the web or a site ('search for python tutorials', 'search amazon for headphones'), play things on YouTube or Spotify, "
        "send WhatsApp messages ('send a message to ali saying I'll be late') and emails, keep a contact book ('add contact ali 0300 1234567'), "
        "translate ('translate good morning to urdu'), convert units and currency ('convert 10 km to miles', '100 dollars to rupees'), "
        "give directions, do maths, take notes, set timers, alarms and reminders ('remind me at 5 pm to call mom'), "
        "change the volume and brightness, press keys like refresh, back and new tab, type text for you, "
        "tell you your battery, memory, disk space or IP address, lock, sleep, restart or shut down the computer, "
        "tell you the weather, look things up ('who is Ada Lovelace'), flip a coin, roll a dice, tell a joke or a quote. "
        "You can also type in Roman Urdu, like 'youtube kholo'. Say 'exit' to stop.")

# Several commands in one sentence: "open youtube and open notepad". Messages, notes and the like are never split,
# because 'and' can be part of what you want to say.
CONJUNCTION = re.compile(
    r"\s+(?:and then|and also|then|and)\s+(?=(?:open|search|play|go to|launch|visit|start|set|turn|increase|decrease|lower|"
    r"raise|mute|lock|take a screenshot|close|translate|what|tell|remind|volume|brightness|scroll|refresh|zoom|show|read|"
    r"type|send|message|whatsapp|flip|roll|convert|email|navigate)\b)")
UNSPLITTABLE = re.compile(
    r"^(?:open whats ?app(?: and| then)? )?(?:send|message|msg|text|whats ?app|email|e-mail|type|dictate|say|translate|remind|"
    r"(?:take|add|make|write|save)(?: a| me a| new)? (?:note|contact)|note\b|set (?:a |an )?(?:timer|alarm))"
    r"|^open .+? and (?:search|look up|find)\b")


@dataclass
class Reply:
    text: str
    exit: bool = False


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[?!.,;]+$", "", text)
    return re.sub(r"\s+", " ", text)


POLITE = re.compile(r"^(?:(?:please|can you|could you|would you|will you)\s+)+")


def strip_politeness(command: str) -> str:
    """'can you please open youtube' -> 'open youtube'."""
    command = POLITE.sub("", command)
    return re.sub(r"\s+please$", "", command)


def strip_wake_word(text: str, wake_word: Optional[str]) -> Optional[str]:
    """Return the command after the wake word, or None if the wake word was not said."""
    if not wake_word:
        return text
    pattern = rf"^\s*(?:hey\s+|ok\s+|okay\s+)?{re.escape(wake_word.lower())}\b[\s,:]*"
    if re.match(pattern, text.lower()):
        return re.sub(pattern, "", text, count=1, flags=re.I).strip()
    return None


def split_compound(command: str) -> List[str]:
    """'open youtube and open notepad' -> ['open youtube', 'open notepad']; messages and notes stay in one piece."""
    if UNSPLITTABLE.search(command):
        return [command]
    return [part for part in CONJUNCTION.split(command) if part.strip()] or [command]


class Assistant:
    APP_SEND_DELAY = 6.0    # seconds to wait for the WhatsApp app to show the chat before pressing Enter
    WEB_SEND_DELAY = 14.0   # WhatsApp Web needs longer to load

    def __init__(self, notes: Optional[NoteStore] = None,
                 opener: Callable[[str], object] = webbrowser.open,
                 now: Callable[[], datetime] = datetime.now,
                 rng: Optional[random.Random] = None,
                 video_finder: Callable[[str], Optional[str]] = first_video_url,
                 app_launcher: Callable[[str], bool] = launch,
                 scheduler: Callable = thread_scheduler,
                 summary_finder: Callable[[str], Optional[str]] = wiki_summary,
                 volume_controller: Callable[..., bool] = volume,
                 power_controller: Callable[[str], bool] = power,
                 key_sender: Callable[[str], bool] = send_shortcut,
                 custom_apps: Optional[dict] = None,
                 contacts: Optional[ContactStore] = None,
                 custom_sites: Optional[dict] = None,
                 text_typer: Callable[[str], bool] = type_text,
                 brightness_controller: Callable[..., bool] = brightness,
                 app_closer: Callable[[str], Optional[bool]] = close_app,
                 status_reader: Callable[[str], Optional[str]] = system_status,
                 rate_fetcher: Callable[[str, str], Optional[float]] = fetch_rate,
                 home: Optional[Path] = None,
                 confirm_messages: bool = True,
                 auto_send: bool = True,
                 send_delay: Optional[float] = None) -> None:
        self.notes = notes or NoteStore()
        self.opener = opener
        self.now = now
        self.rng = rng or random.Random()
        self.video_finder = video_finder
        self.app_launcher = app_launcher
        self.scheduler = scheduler
        self.summary_finder = summary_finder
        self.volume_controller = volume_controller
        self.power_controller = power_controller
        self.key_sender = key_sender
        self.custom_apps = custom_apps or {}
        self.contacts = contacts or ContactStore()
        self.custom_sites = custom_sites or {}
        self.text_typer = text_typer
        self.brightness_controller = brightness_controller
        self.app_closer = app_closer
        self.status_reader = status_reader
        self.rate_fetcher = rate_fetcher
        self.home = home or Path.home()
        self.confirm_messages = confirm_messages
        self.auto_send = auto_send
        self.send_delay = send_delay
        self._raw = ""  # what you typed, with capital letters, so messages keep them
        self._pending: Optional[str] = None  # shutdown/restart waiting for a "yes"
        self._followup: Optional[Callable[[str], Optional[Reply]]] = None  # next sentence answers a question of ours
        self.alert_sink: Optional[Callable[[str], None]] = None  # speak timer alerts immediately if set
        self._alerts: "queue.Queue[str]" = queue.Queue()
        self._timers: list = []
        # Order matters: commands that start with a keyword first, loose keyword matches
        # (joke, time, date) after them, the calculator last. A handler may return None to let later routes try.
        self.routes: List[Tuple[re.Pattern, Callable[[re.Match], Optional[Reply]]]] = [
            (re.compile(r"^(?:cancel|stop|clear|delete)(?: all| my)? (?:timers?|reminders?|alarms?)$"), self._cancel_timers),
            (re.compile(r"^(?:cancel|abort|stop)(?: the| my)? (?:shut ?down|restart|reboot)$"),
             lambda m: self._power_now("cancel")),
            (re.compile(r"^(shut ?down|power off|restart|reboot)(?: the| my)?(?: computer| pc| laptop| system| windows)?$"),
             lambda m: self._ask_power("restart" if m.group(1) in ("restart", "reboot") else "shutdown")),
            (re.compile(r"^turn off (?:the |my )?(?:computer|pc|laptop|system)$"), lambda m: self._ask_power("shutdown")),
            (re.compile(r"^(?:log ?off|log out|sign out)(?: of)?(?: the| my)?(?: computer| pc| laptop| windows| account| system)?$"),
             lambda m: self._ask_power("logoff")),
            (re.compile(r"^lock(?: the| my)?(?: computer| pc| laptop| screen| system| windows)?$"),
             lambda m: self._power_now("lock")),
            (re.compile(r"^(?:(?:put|set) (?:the |my )?(?:computer|pc|laptop|system) (?:to |on )?sleep|sleep (?:the |my )?(?:computer|pc|laptop|system)|sleep mode)$"),
             lambda m: self._power_now("sleep")),
            (re.compile(r"^(?:turn )?(?:the )?volume up$|^(?:increase|raise|turn up)(?: the)? volume$|^louder$"),
             lambda m: self._volume("up")),
            (re.compile(r"^(?:turn )?(?:the )?volume down$|^(?:decrease|lower|reduce|turn down)(?: the)? volume$|^quieter$"),
             lambda m: self._volume("down")),
            (re.compile(r"^(?:un)?mute(?: the)?(?: volume| sound| computer)?$"), lambda m: self._volume("mute")),
            (re.compile(r"^(?:set )?(?:the )?volume (?:to |at )?(.+?)(?: percent|%)?$"), self._set_volume),
            (re.compile(r"^(?:(?:turn )?(?:the )?(?:screen )?brightness up|(?:increase|raise|turn up)(?: the)?(?: screen)?(?: brightness)?|brighter|brighten(?: the screen)?)$"),
             lambda m: self._brightness("up")),
            (re.compile(r"^(?:(?:turn )?(?:the )?(?:screen )?brightness down|(?:decrease|lower|reduce|turn down)(?: the)?(?: screen)?(?: brightness)?|dimmer|dim(?: the screen)?)$"),
             lambda m: self._brightness("down")),
            (re.compile(r"^(?:set )?(?:the )?(?:screen )?brightness (?:to |at )?(.+?)(?: percent|%)?$"), self._set_brightness),
            *[(re.compile(pattern), lambda m, n=name, r=reply: self._shortcut(n, r))
              for pattern, name, reply in KEY_COMMANDS],
            (re.compile(r"^(?:close|kill|terminate)(?: the)? (.+?)(?: app| application| window| program)?$"), self._close_app),
            (re.compile(r"^(?:exit|quit|stop|goodbye|good bye|bye)\b"), self._exit),
            (re.compile(r"^(?:help|what can you do)\b"), lambda m: Reply(HELP)),
            (re.compile(r"^(?:take|add|make|write|save)(?: a| me a)? note(?: that| to)?[: ]*(.+)$"), self._add_note),
            (re.compile(r"^note[: ]+(.+)$"), self._add_note),
            (re.compile(r"^(?:read|show|list|what are)(?: me)?(?: my| all)? notes$"), self._read_notes),
            (re.compile(r"^(?:clear|delete|erase)(?: all)?(?: my)? notes$"), self._clear_notes),
            (re.compile(r"^(?:delete|remove|erase) note (.+)$"), self._delete_note),
            # contacts and messages
            (re.compile(r"^(?:add|save|create)(?: a| new)?(?: new)? contact (.+)$"), self._add_contact),
            (re.compile(r"^(?:list|show|read)(?: me)?(?: my| all)? contacts$"), self._list_contacts),
            (re.compile(r"^(?:delete|remove|erase) (?:the )?contact (.+)$"), self._delete_contact),
            (re.compile(r"^(?:what(?:'s| is)|show|tell me)(?: me)?(?: the)?(?: phone| mobile)? (number|e-?mail|mail)(?: address)? (?:of|for) (.+)$"),
             self._contact_info),
            (re.compile(r"^send (?:an? )?(?:whats ?app )?(?:message |msg |text )?(.+?) to (.+?) (?:on|via|in|using|through) whats ?app$"),
             self._whatsapp_text_first),
            (re.compile(r"^(?:open whats ?app(?: and| then)? )?(?:send|write|drop|shoot)(?: an?)?(?: whats ?app)?(?: message| msg| text)?"
                        r"(?: (?:on|via|in|using|through) whats ?app)? to (.+)$"), self._whatsapp_to),
            (re.compile(r"^(?:open whats ?app(?: and| then)? )?(?:whats ?app|message|msg|text) (.+)$"), self._whatsapp_to),
            (re.compile(r"^(?:send|write|compose|draft)(?: an?)? (?:e-?mail|mail)(?: to (.+?))?(?: (saying|about|regarding|with subject|subject) (.+))?$"),
             self._email),
            (re.compile(r"^e-?mail (.+?)(?: (saying|about|regarding|with subject|subject) (.+))?$"),
             lambda m: self._email_to(m.group(1), m.group(2), m.group(3))),
            (re.compile(r"^send (.+?) to (.+)$"), self._send_known),
            # timers, alarms, reminders
            (re.compile(r"^(?:set (?:a |an )?)?(?:timer|alarm) (?:for|of|at) (.+)$|^wake me(?: up)? at (.+)$"), self._timer),
            (re.compile(r"^remind me (?:in|at) (.+?) to (.+)$"), lambda m: self._reminder(m.group(2), m.group(1))),
            (re.compile(r"^remind me to (.+?) (?:in|at) (.+)$"), lambda m: self._reminder(m.group(1), m.group(2))),
            (re.compile(r"^(?:(?:what(?:'s| is)|how(?:'s| is)) the )?weather(?: like)?(?:(?: in| for| at| of)? (.+))?$"), self._weather),
            # about this computer
            *[(re.compile(rf"^(?:(?:what(?:'s| is)|check|show|tell me|how(?:'s| is))(?: me)?(?: the| my)? )?{words}$"
                          rf"|^how much (?:{words})(?: is)?(?: left| used| free| remaining| available)?(?: do i have)?$"),
               lambda m, k=kind: self._status(k)) for kind, words in STATUS_WORDS.items()],
            (re.compile(r"^(?:am i|are we) (?:online|connected)(?: to the internet)?$|^(?:check )?(?:my |the )?(?:internet|wi-?fi)(?: connection| status)?$"
                        r"|^is (?:the )?internet (?:working|on|connected)$"), lambda m: self._status("internet")),
            (re.compile(r"^(?:hello|hi|hey|salam|assalam[a-z ]*)\b"), lambda m: Reply("Hello! How can I help you?")),
            (re.compile(r"^(?:what(?:'s| is) your name|who are you)$"), lambda m: Reply("I'm your voice assistant, written in Python.")),
            # the web
            (re.compile(r"^translate (.+?) (?:to|into|in) ([a-z]+)$|^how (?:do you|do i|to) say (.+?) in ([a-z]+)$"), self._translate),
            (re.compile(r"^(?:(?:open|show|get|give|read|tell) (?:me )?)?(?:the )?(?:latest |top |breaking |today's )?(?:news|headlines)(?: (?:about|on|for|of) (.+))?$"),
             self._news),
            (re.compile(r"^(?:navigate|get directions|give me directions|directions|take me)(?: to)? (.+)$"), self._directions),
            (re.compile(r"^(?:find|show|search for|look for)(?: me)? (.+?) (?:near me|nearby|near by|around me)$"),
             lambda m: self._maps(f"{m.group(1)} near me")),
            (re.compile(r"^(?:where(?:'s| is)|locate) (.+)$|^(?:show|find)(?: me)? (.+?) on (?:the |google )?maps?$"),
             lambda m: self._maps(m.group(1) or m.group(2))),
            (re.compile(r"^open (?:my |the )?(downloads|documents|desktop|pictures|music|videos|home)(?: folder)?$"), self._open_folder),
            (re.compile(r"^play (.+?) on spotify$"), self._play_spotify),
            (re.compile(r"^play (.+?)(?: on youtube)?$"), self._play),
            (re.compile(r"^(?:search youtube for|youtube) (.+)$"), self._youtube),
            (re.compile(r"^open (.+?) and (?:search|look up|find)(?: for)? (.+)$"),
             lambda m: self._search_on(m.group(2), m.group(1))),
            (re.compile(r"^(?:search|find|look up|look for)(?: for)? (.+?) (?:on|in|at|using|from) (.+)$"),
             lambda m: self._search_on(m.group(1), m.group(2))),
            (re.compile(r"^(?:search|find|look up) (.+?) for (.+)$"), lambda m: self._search_on(m.group(2), m.group(1))),
            (re.compile(r"^(?:search for|search|google|look up) (.+)$"), self._search),
            (re.compile(r"^(?:open|go to|launch|visit|start|run) (.+)$"), self._open),
            # typing and small talk
            (re.compile(r"^(?:type|dictate)(?: out)?[: ]+(.+)$"), self._type),
            (re.compile(r"^say (.+)$"), lambda m: Reply(self._restore(m.group(1)))),
            (re.compile(r"^(?:tell me |give me )?(?:a |an )?(?:quote|motivational quote|inspirational quote|some motivation)$|^(?:motivate|inspire) me$"),
             lambda m: Reply(self.rng.choice(QUOTES))),
            (re.compile(r"^(?:flip|toss) a coin$"), lambda m: Reply(f"It's {self.rng.choice(['heads', 'tails'])}.")),
            (re.compile(r"^roll a (?:dice|die)$"), lambda m: Reply(f"You rolled a {self.rng.randint(1, 6)}.")),
            (re.compile(r"\bjoke\b"), lambda m: Reply(self.rng.choice(JOKES))),
            (re.compile(r"\btime\b"), self._time),
            (re.compile(r"\b(?:date|today|day is it)\b"), self._date),
        ]

    # ------------------------------------------------------------ public
    def handle(self, text: str) -> Reply:
        self._raw = re.sub(r"\s+", " ", text.strip())
        command = strip_politeness(normalize(text))
        if not command:
            return Reply("I didn't catch that.")
        if self._followup:  # we asked a question (what to say? are you sure?)
            followup, self._followup = self._followup, None
            reply = followup(command)
            if reply is not None:
                return reply
        if self._pending:
            action, self._pending = self._pending, None
            if command in YES:
                return self._power_now(action)
            if command in NO:
                return Reply("Okay, cancelled.")
        command = to_english(command)
        texts, leave = [], False
        for part in split_compound(command):
            reply = self._handle_one(part)
            texts.append(reply.text)
            leave = leave or reply.exit
            if leave or self._pending or self._followup:
                break  # don't run the rest while we wait for an answer or after exit
        return Reply(" ".join(texts), exit=leave)

    @property
    def awaiting_confirmation(self) -> bool:
        return self._pending is not None or self._followup is not None

    def pop_alerts(self) -> List[str]:
        """Timer/reminder messages that fired and have not been spoken yet."""
        alerts = []
        while True:
            try:
                alerts.append(self._alerts.get_nowait())
            except queue.Empty:
                return alerts

    def _handle_one(self, command: str) -> Reply:
        for pattern, handler in self.routes:
            match = pattern.search(command)
            if match:
                reply = handler(match)
                if reply is not None:
                    return reply
        reply = self._convert(command) or self._maths(command) or self._knowledge(command)
        return reply or Reply("Sorry, I don't know how to do that yet. Say 'help' to hear what I can do.")

    def _restore(self, text: str) -> str:
        """Give `text` back its capital letters from what you actually typed (commands are matched in lower case)."""
        if text:
            found = list(re.finditer(r"(?<!\w)" + re.escape(text) + r"(?!\w)", self._raw, re.I))
            if found:
                return self._raw[found[-1].start():found[-1].end()]
        return text

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

    def _shortcut(self, name: str, reply: str) -> Reply:
        if not self.key_sender(name):
            return Reply("Sorry, I couldn't do that on this computer.")
        return Reply(reply)

    def _ask_power(self, action: str) -> Reply:
        self._pending = action
        verb = {"restart": "restart", "logoff": "sign out of"}.get(action, "shut down")
        return Reply(f"Are you sure you want to {verb} the computer? Say yes to confirm.")

    def _power_now(self, action: str) -> Reply:
        if not self.power_controller(action):
            if action == "cancel":
                return Reply("I couldn't cancel it. There may be no shutdown waiting.")
            return Reply("Sorry, I couldn't do that on this computer.")
        if action == "cancel":
            return Reply("Okay, the shutdown is cancelled.")
        if action == "lock":
            return Reply("Locking the computer.")
        if action == "sleep":
            return Reply("Putting the computer to sleep.")
        if action == "logoff":
            return Reply("Signing out.")
        verb = "Restarting" if action == "restart" else "Shutting down"
        return Reply(f"{verb} in {SHUTDOWN_DELAY} seconds. Say 'cancel shutdown' to stop it.")

    def _volume(self, action: str, value=None) -> Reply:
        if not self.volume_controller(action, value):
            return Reply("Sorry, I couldn't change the volume on this computer.")
        return Reply({"up": "Volume up.", "down": "Volume down.", "mute": "Toggled mute."}.get(action, f"Volume set to {value} percent."))

    def _set_volume(self, m) -> Reply:
        try:
            level = int(float(_number_words(m.group(1).strip())))
        except ValueError:
            return Reply("Which volume level, from 0 to 100?")
        if not 0 <= level <= 100:
            return Reply("The volume must be between 0 and 100.")
        return self._volume("set", level)

    def _brightness(self, action: str, value=None) -> Reply:
        if not self.brightness_controller(action, value):
            return Reply("Sorry, I couldn't change the brightness. This works on laptop screens, not most desktop monitors.")
        return Reply({"up": "Brighter.", "down": "Dimmer."}.get(action, f"Brightness set to {value} percent."))

    def _set_brightness(self, m) -> Reply:
        try:
            level = int(float(_number_words(m.group(1).strip())))
        except ValueError:
            return Reply("Which brightness level, from 0 to 100?")
        if not 0 <= level <= 100:
            return Reply("The brightness must be between 0 and 100.")
        return self._brightness("set", level)

    def _status(self, kind: str) -> Reply:
        text = self.status_reader(kind)
        return Reply(text or "Sorry, I can't read that on this computer.")

    def _close_app(self, m) -> Optional[Reply]:
        target = m.group(1).strip()
        result = self.app_closer(target)
        if result is None:
            return None  # not an app we know, let other routes try
        if result:
            return Reply(f"Closing {target}.")
        return Reply(f"I couldn't close {target}. It may not be running.")

    def _delete_note(self, m) -> Reply:
        try:
            number = int(_number_words(m.group(1).strip()))
        except ValueError:
            return Reply("Which note number should I delete?")
        removed = self.notes.remove(number)
        if removed is None:
            return Reply(f"I can't find note {number}.")
        return Reply(f"Deleted note {number}: {removed}.")

    # ---- contacts
    def _add_contact(self, m) -> Reply:
        name, phone_words, email = parse_contact_details(m.group(1))
        if not name:
            return Reply("Whose contact should I save? For example: add contact ali 0300 1234567.")
        phone = None
        if phone_words:
            phone = normalize_phone(phone_words, self.contacts.country_code)
            if not phone:
                return Reply("That doesn't look like a phone number. Try something like 0300 1234567.")
        if not phone and not email:
            return Reply(f"What is {name}'s phone number? Say: add contact {name} 0300 1234567.")
        self.contacts.add(name, phone=phone, email=email)
        saved = " and ".join(x for x in (f"number +{phone}" if phone else "", f"email {email}" if email else "") if x)
        return Reply(f"Saved {name.title()} with {saved}.")

    def _list_contacts(self, m) -> Reply:
        names = self.contacts.names()
        if not names:
            return Reply("You have no contacts yet. Say: add contact ali 0300 1234567.")
        return Reply(f"You have {len(names)} contact{'s' if len(names) != 1 else ''}: {', '.join(n.title() for n in names)}.")

    def _delete_contact(self, m) -> Reply:
        removed = self.contacts.remove(m.group(1).strip())
        return Reply(f"Deleted the contact {removed.title()}.") if removed else Reply(f"I can't find a contact called {m.group(1).strip()}.")

    def _contact_info(self, m) -> Reply:
        found = self.contacts.find(m.group(2).strip())
        if not found:
            return Reply(f"I can't find a contact called {m.group(2).strip()}.")
        name, entry = found
        if m.group(1) == "number":
            return Reply(f"{name.title()}'s number is +{entry['phone']}." if entry.get("phone") else f"{name.title()} has no number saved.")
        return Reply(f"{name.title()}'s email is {entry['email']}." if entry.get("email") else f"{name.title()} has no email saved.")

    # ---- messages
    def _resolve_recipient(self, who: str):
        """(display name, phone digits) for a contact name or a spoken phone number, or a Reply explaining the problem."""
        who = who.strip()
        if not who:
            return Reply("Who should I send it to?")
        phone = normalize_phone(who, self.contacts.country_code)
        if phone:
            return f"+{phone}", phone
        found = self.contacts.find(who)
        if found:
            name, entry = found
            if entry.get("phone"):
                return name.title(), entry["phone"]
            return Reply(f"{name.title()} has no phone number saved. Say: add contact {name} 0300 1234567.")
        return Reply(f"I don't have a contact called {who}. Say: add contact {who} 0300 1234567, or say the phone number.")

    def _whatsapp_to(self, m) -> Reply:
        rest = re.sub(r"\s+(?:on|via|in|using|through) whats ?app$", "", m.group(1).strip())
        if rest in ("web", "app"):
            return self._open(re.match(r"(.+)", "whatsapp web" if rest == "web" else "whatsapp"))
        who, text = split_recipient_and_text(rest, self.contacts.names())
        return self._message_flow(who, text)

    def _whatsapp_text_first(self, m) -> Reply:
        text, who = m.group(1).strip(), m.group(2).strip()
        if text in ("message", "msg", "text", "a message", "whatsapp", "whatsapp message"):
            text = ""
        return self._message_flow(who, text)

    def _send_known(self, m) -> Optional[Reply]:
        """'send hello to ali' - only when ali is a contact or a phone number, so 'send X to Y' can still mean other things."""
        who = m.group(2).strip()
        if not (normalize_phone(who, self.contacts.country_code) or self.contacts.find(who)):
            return None
        return self._message_flow(who, m.group(1).strip())

    def _message_flow(self, who: str, text: str) -> Reply:
        target = self._resolve_recipient(who)
        if isinstance(target, Reply):
            return target
        name, phone = target
        if not text:
            self._followup = lambda command: self._message_text_given(name, phone, command)
            return Reply(f"What should I say to {name}?")
        return self._confirm_or_send(name, phone, self._restore(text))

    def _message_text_given(self, name: str, phone: str, command: str) -> Reply:
        if command in NO:
            return Reply("Okay, cancelled.")
        # free speech might not be a message at all, so this always asks before sending
        return self._confirm_or_send(name, phone, self._restore(command), force=True)

    def _confirm_or_send(self, name: str, phone: str, text: str, force: bool = False) -> Reply:
        if not (self.confirm_messages or force):
            return self._send_whatsapp(name, phone, text)
        self._followup = lambda command: self._confirm_send(command, name, phone, text)
        return Reply(f"Send '{text}' to {name} on WhatsApp? Say yes to confirm.")

    def _confirm_send(self, command: str, name: str, phone: str, text: str) -> Optional[Reply]:
        if command in YES:
            return self._send_whatsapp(name, phone, text)
        if command in NO:
            return Reply("Okay, I won't send it.")
        return None

    def _send_whatsapp(self, name: str, phone: str, text: str) -> Reply:
        in_app = self.app_launcher(whatsapp_app_url(phone, text))  # the desktop app, if it is installed
        if not in_app:
            self.opener(whatsapp_web_url(phone, text))
        if not self.auto_send:
            return Reply(f"I opened the chat with {name} with your message typed in. Press Enter to send it.")
        delay = self.send_delay if self.send_delay is not None else (self.APP_SEND_DELAY if in_app else self.WEB_SEND_DELAY)
        self.scheduler(delay, lambda: self.key_sender("enter"))  # WhatsApp has the message typed in; Enter sends it
        return Reply(f"Sending your message to {name} on WhatsApp. Please don't switch windows for a few seconds.")

    def _email(self, m) -> Reply:
        return self._email_to(m.group(1), m.group(2), m.group(3))

    def _email_to(self, who: Optional[str], connector: Optional[str], text: Optional[str]) -> Reply:
        to = ""
        if who:
            who = who.strip()
            found = self.contacts.find(who)
            if re.fullmatch(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", who):
                to = who
            elif found and found[1].get("email"):
                to = found[1]["email"]
            else:
                return Reply(f"I don't have an email address for {who}. Say: add contact {who} email {who} at gmail dot com.")
        text = self._restore(text.strip()) if text else ""
        is_subject = connector in ("about", "regarding", "with subject", "subject")
        self.opener(gmail_compose_url(to, subject=text if is_subject else "", body="" if is_subject else text))
        return Reply("Opening a new email" + (f" to {to}" if to else "") + ". Check it and press send.")

    # ---- timers and alarms
    def _alert(self, message: str) -> None:
        if self.alert_sink:
            self.alert_sink(message)
        else:
            self._alerts.put(message)

    def _schedule(self, seconds: float, message: str) -> None:
        holder = {}

        def fire():
            if holder.get("handle") in self._timers:
                self._timers.remove(holder["handle"])
            self._alert(message)

        holder["handle"] = self.scheduler(seconds, fire)
        self._timers.append(holder["handle"])

    def _clock(self, text: str):
        return parse_clock_time(text, self.now())

    def _timer(self, m) -> Reply:
        text = (m.group(1) or m.group(2)).strip()
        seconds = parse_duration(text)
        if seconds is None:
            clock = self._clock(text)
            if clock:
                label = f"{clock[1].strftime('%I:%M %p').lstrip('0')}"
                self._schedule(clock[0], f"Alarm! It's {label}.")
                return Reply(f"Okay, alarm set for {label}.")
            return Reply("How long should the timer be? For example, set a timer for 5 minutes, or set an alarm for 7 am.")
        if not 0 < seconds <= MAX_SECONDS:
            return Reply("Please choose a time between 1 second and 24 hours.")
        length = format_duration(seconds)
        self._schedule(seconds, f"Time's up! Your timer for {length} is done.")
        return Reply(f"Okay, timer set for {length}.")

    def _reminder(self, task: str, when: str) -> Reply:
        task = self._restore(task.strip())
        seconds = parse_duration(when)
        if seconds is None:
            clock = self._clock(when)
            if clock:
                label = clock[1].strftime("%I:%M %p").lstrip("0")
                self._schedule(clock[0], f"Reminder: {task}.")
                return Reply(f"Okay, I'll remind you at {label}: {task}.")
        if seconds is None or not 0 < seconds <= MAX_SECONDS:
            return Reply("Please give a time between 1 second and 24 hours, for example in 10 minutes or at 5 pm.")
        self._schedule(seconds, f"Reminder: {task}.")
        return Reply(f"Okay, I'll remind you in {format_duration(seconds)}: {task}.")

    def _cancel_timers(self, m) -> Reply:
        count = len(self._timers)
        for handle in self._timers:
            handle.cancel()
        self._timers.clear()
        return Reply(f"Cancelled {count} timer{'s' if count != 1 else ''}." if count else "You have no active timers.")

    # ---- the web
    def _weather(self, m) -> Reply:
        place = (m.group(1) or "").strip()
        self.opener("https://www.google.com/search?q=" + quote_plus(f"weather {place}".strip()))
        return Reply(f"Showing the weather{' for ' + place if place else ''}.")

    def _translate(self, m) -> Reply:
        text, language = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        code = LANGUAGES.get(language)
        if not code:
            return Reply(f"I don't know the language {language}. Try urdu, hindi, arabic, french, spanish or german.")
        text = self._restore(text.strip())
        self.opener(f"https://translate.google.com/?sl=auto&tl={code}&text={quote_plus(text)}&op=translate")
        return Reply(f"Translating '{text}' to {language.title()}.")

    def _news(self, m) -> Reply:
        topic = (m.group(1) or "").strip()
        self.opener(f"https://news.google.com/search?q={quote_plus(topic)}" if topic else "https://news.google.com")
        return Reply(f"Showing the news about {topic}." if topic else "Showing the latest news.")

    def _directions(self, m) -> Reply:
        place = self._restore(m.group(1).strip())
        self.opener(f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(place)}")
        return Reply(f"Getting directions to {place}.")

    def _maps(self, place: str) -> Reply:
        place = self._restore(place.strip())
        self.opener(f"https://www.google.com/maps/search/{quote_plus(place.strip())}")
        return Reply(f"Showing {place.strip()} on the map.")

    def _open_folder(self, m) -> Reply:
        name = m.group(1)
        path = self.home / FOLDERS[name]
        if not self.app_launcher(str(path)):
            return Reply(f"I couldn't open your {name} folder on this computer.")
        return Reply(f"Opening your {name} folder.")

    def _knowledge(self, command: str) -> Optional[Reply]:
        match = KNOWLEDGE.match(command)
        if not match:
            return None
        topic = match.group(1).strip()
        text = self.summary_finder(topic)
        return Reply(text) if text else Reply(f"Sorry, I couldn't find anything about {topic}.")

    def _search(self, m) -> Reply:
        query = m.group(1).strip()
        self.opener(f"https://www.google.com/search?q={quote_plus(query)}")
        return Reply(f"Searching the web for {query}.")

    def _search_on(self, query: str, site: str) -> Optional[Reply]:
        """'search headphones on amazon'. Unknown site -> None, so it becomes a normal web search."""
        url = search_url(site.strip(), query.strip(), self.custom_sites)
        if url is None:
            return None
        self.opener(url)
        return Reply(f"Searching {site.strip()} for {query.strip()}.")

    def _play(self, m) -> Reply:
        query = m.group(1).strip()
        video = self.video_finder(query)
        if video:
            self.opener(video)
            return Reply(f"Playing {query} on YouTube.")
        self.opener(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
        return Reply(f"I couldn't find a video to play, so I'm showing YouTube results for {query}.")

    def _play_spotify(self, m) -> Reply:
        query = m.group(1).strip()
        if not self.app_launcher(f"spotify:search:{quote(query)}"):  # the Spotify app, if installed
            self.opener(f"https://open.spotify.com/search/{quote(query)}")
        return Reply(f"Searching Spotify for {query}.")

    def _youtube(self, m) -> Reply:
        query = m.group(1).strip()
        self.opener(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
        return Reply(f"Searching YouTube for {query}.")

    def _open(self, m) -> Reply:
        target = m.group(1).strip()
        names = [n for n in re.split(r"\s*,\s*|\s+and\s+", target) if n]
        if len(names) > 1 and all(find_site(n, self.custom_sites) or find_app(n, self.custom_apps) for n in names):
            return Reply(" ".join(self._open_one(n).text for n in names))  # "open youtube, google and github"
        return self._open_one(target)

    def _open_one(self, target: str) -> Reply:
        site = find_site(target, self.custom_sites)
        if site:
            self.opener(site)
            return Reply(f"Opening {target}.")
        app = find_app(target, self.custom_apps)
        if app:
            if self.app_launcher(app):
                return Reply(f"Opening {target}.")
            web = WEB_FALLBACKS.get(app)
            if web:
                self.opener(web)
                return Reply(f"The {target} app isn't available, so I'm opening it in the browser.")
            return Reply(f"I couldn't open {target} on this computer.")
        if re.match(r"^https?://\S+$", target):
            self.opener(target)
            return Reply("Opening the link.")
        if DOMAIN.match(target.replace(" dot ", ".").replace(" ", "")):
            domain = target.replace(" dot ", ".").replace(" ", "")
            self.opener(f"https://{domain}")
            return Reply(f"Opening {domain}.")
        return Reply(f"I don't know the website or app {target}. Try a name like youtube, notepad or calculator, "
                     "a domain like example.com, or add your own app to apps.json or site to sites.json.")

    def _type(self, m) -> Reply:
        text = self._restore(m.group(1).strip())
        if not self.text_typer(text):
            return Reply("Sorry, I couldn't type that. It works on Windows, for up to 500 characters.")
        return Reply("Typed.")

    # ---- numbers
    def _convert(self, command: str) -> Optional[Reply]:
        parsed = parse_conversion(command)
        if not parsed:
            return None
        amount, src, dst = parsed
        result = convert_units(amount, src, dst)
        if result:
            value, src_label, dst_label = result
            return Reply(f"{format_number(amount)} {src_label} is {format_number(round(value, 4))} {dst_label}.")
        a, b = currency_code(src), currency_code(dst)
        if not (a and b):
            return None
        rate = self.rate_fetcher(a, b)
        if rate is None:
            self.opener("https://www.google.com/search?q=" + quote_plus(f"{format_number(amount)} {a} to {b}"))
            return Reply("I couldn't get the live rate, so I'm showing it on Google.")
        return Reply(f"{format_number(amount)} {src} is about {amount * rate:,.2f} {dst}.")

    def _maths(self, command: str) -> Optional[Reply]:
        expression = re.sub(r"^(?:calculate|compute|solve|what is|what's|how much is)\s+", "", command)
        try:
            return Reply(f"The answer is {format_number(calculate(expression))}.")
        except CalcError as exc:
            if str(exc) == "not a calculation":
                return None
            return Reply(f"Sorry, {exc}.")
