"""Run the assistant:  python -m assistant   (typed)   or   python -m assistant --voice"""
from __future__ import annotations

import argparse
import sys

from .engine import Assistant, strip_wake_word
from .speech import SpeechUnavailable, TextIO, VoiceIO


def run_loop(io, assistant: Assistant, wake_word=None, max_turns=None) -> None:
    """Listen, answer, repeat until the user says exit. `io` needs listen() and speak()."""
    io.speak("Hello! I'm ready. Say help to hear what I can do.")
    turns = 0
    while max_turns is None or turns < max_turns:
        turns += 1
        heard = io.listen()
        if heard is None or not heard.strip():
            continue
        command = strip_wake_word(heard, wake_word)
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
    args = p.parse_args(argv)

    from .notes import NoteStore
    assistant = Assistant(notes=NoteStore(args.notes_file))
    try:
        io = VoiceIO(args.language) if args.voice else TextIO()
        run_loop(io, assistant, args.wake_word)
    except SpeechUnavailable as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nGoodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
