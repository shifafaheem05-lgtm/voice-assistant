"""Run the assistant:  python -m assistant   (typed)   or   python -m assistant --voice"""
from __future__ import annotations

import argparse
import sys

from .apps import load_custom_apps
from .contacts import ContactStore
from .engine import Assistant, strip_wake_word
from .sites import load_custom_sites
from .speech import SpeechUnavailable, TextIO, VoiceIO


def run_loop(io, assistant: Assistant, wake_word=None, max_turns=None) -> None:
    """Listen, answer, repeat until the user says exit. `io` needs listen() and speak()."""
    io.speak("Hello! I'm ready. Say help to hear what I can do.")
    turns = 0
    while max_turns is None or turns < max_turns:
        turns += 1
        for alert in assistant.pop_alerts():  # timers that fired while we were waiting
            io.speak(alert)
        heard = io.listen()
        if heard is None or not heard.strip():
            continue
        # a yes/no answer to "are you sure?" does not need the wake word
        command = heard if assistant.awaiting_confirmation else strip_wake_word(heard, wake_word)
        if command is None:
            continue  # wake word not said, ignore
        reply = assistant.handle(command)
        io.speak(reply.text)
        if reply.exit:
            break


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="assistant", description="A simple voice-controlled assistant.")
    p.add_argument("--voice", action="store_true", help="use microphone and speech (needs extra packages)")
    p.add_argument("--wake-word", help="only react to commands that start with this word, e.g. jarvis")
    p.add_argument("--language", default="en-US", help="speech recognition language (default en-US)")
    p.add_argument("--notes-file", default="notes.json")
    p.add_argument("--apps-file", default="apps.json", help="your own apps: {\"my game\": \"C:\\\\path\\\\game.exe\"}")
    p.add_argument("--sites-file", default="sites.json", help="your own websites: {\"my blog\": \"https://example.com\"}")
    p.add_argument("--contacts-file", default="contacts.json", help="contact book used for WhatsApp and email")
    p.add_argument("--country-code", default="92", help="added to phone numbers that start with 0 (default 92 = Pakistan)")
    p.add_argument("--no-confirm", action="store_true", help="send WhatsApp messages without asking 'are you sure?' first")
    p.add_argument("--no-auto-send", action="store_true", help="only type the WhatsApp message, don't press Enter for me")
    p.add_argument("--send-delay", type=float, help="seconds to wait for WhatsApp to open before pressing Enter")
    args = p.parse_args(argv)

    from .notes import NoteStore
    assistant = Assistant(notes=NoteStore(args.notes_file), custom_apps=load_custom_apps(args.apps_file),
                          contacts=ContactStore(args.contacts_file, args.country_code),
                          custom_sites=load_custom_sites(args.sites_file),
                          confirm_messages=not args.no_confirm, auto_send=not args.no_auto_send,
                          send_delay=args.send_delay)
    try:
        io = VoiceIO(args.language) if args.voice else TextIO()
        if isinstance(io, TextIO):
            assistant.alert_sink = io.speak  # typed mode blocks on input(), so alert right away
        run_loop(io, assistant, args.wake_word)
    except SpeechUnavailable as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nGoodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
