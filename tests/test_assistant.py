import random
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from assistant import Assistant
from assistant.calc import CalcError, calculate, format_number, to_expression
from assistant.cli import run_loop
from assistant.engine import normalize, strip_wake_word
from assistant.notes import NoteStore
from assistant.speech import SpeechUnavailable, VoiceIO

FIXED = datetime(2026, 10, 29, 15, 5)


class CalcTests(unittest.TestCase):
    def test_symbols_and_words(self):
        cases = {"2 + 3": 5, "12 times 7": 84, "10 divided by 4": 2.5, "9 minus 12": -3,
                 "2 to the power of 8": 256, "17 mod 5": 2, "3 x 4": 12, "5 multiplied by 6": 30,
                 "(2 + 3) * 4": 20, "1,000 plus 1": 1001}
        for text, expected in cases.items():
            self.assertEqual(calculate(text), expected, text)

    def test_number_words(self):
        self.assertEqual(calculate("five plus three"), 8)
        self.assertEqual(calculate("twenty one times two"), 42)
        self.assertEqual(calculate("twenty-one plus nineteen"), 40)

    def test_errors(self):
        with self.assertRaises(CalcError):
            calculate("5 divided by 0")
        with self.assertRaises(CalcError):
            calculate("2 to the power of 1000")
        with self.assertRaises(CalcError):
            calculate("99999999 times 99999999 times 99999999")

    def test_complex_results_are_rejected(self):
        with self.assertRaises(CalcError):
            calculate("(0 - 8) to the power of 0.5")

    def test_rejects_code_and_non_maths(self):
        for text in ["__import__('os').system('ls')", "open('x')", "hello world", "7", "plus", "2 + abc"]:
            with self.assertRaises(CalcError, msg=text):
                calculate(text)

    def test_formatting(self):
        self.assertEqual(format_number(84), "84")
        self.assertEqual(format_number(8.0), "8")
        self.assertEqual(format_number(2.5), "2.5")
        self.assertEqual(format_number(1234567), "1,234,567")

    def test_expression_conversion(self):
        self.assertEqual(to_expression("Twelve Times Seven"), "12 * 7")


class EngineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.opened = []
        self.a = Assistant(notes=NoteStore(Path(self._tmp.name) / "n.json"), opener=self.opened.append,
                           now=lambda: FIXED, rng=random.Random(1))

    def tearDown(self):
        self._tmp.cleanup()

    def say(self, text):
        return self.a.handle(text).text

    def test_greeting_and_name(self):
        self.assertIn("Hello", self.say("Hello there"))
        self.assertIn("voice assistant", self.say("what is your name"))

    def test_time_and_date(self):
        self.assertEqual(self.say("What time is it?"), "It's 3:05 PM.")
        self.assertEqual(self.say("what's the date today"), "Today is Thursday, 29 October 2026.")

    def test_time_and_date_words_do_not_hijack_other_commands(self):
        self.say("search for time management tips")
        self.assertEqual(self.opened[-1], "https://www.google.com/search?q=time+management+tips")
        self.say("search for today's weather")
        self.assertIn("today%27s+weather", self.opened[-1])
        self.say("play happy hour today on youtube")
        self.assertIn("search_query=happy+hour+today", self.opened[-1])
        self.assertNotIn("3:05", self.say("tell me a joke about time"))

    def test_time_does_not_trigger_on_timer_words(self):
        self.assertNotIn("3:05", self.say("sometimes I wonder"))

    def test_exit(self):
        for phrase in ["exit", "Goodbye!", "quit", "bye"]:
            self.assertTrue(self.a.handle(phrase).exit, phrase)
        self.assertFalse(self.a.handle("hello").exit)

    def test_open_sites(self):
        self.assertEqual(self.say("open youtube"), "Opening youtube.")
        self.assertEqual(self.opened[-1], "https://www.youtube.com")
        self.say("open example.com")
        self.assertEqual(self.opened[-1], "https://example.com")
        self.assertIn("don't know", self.say("open my secret files"))
        self.assertEqual(len(self.opened), 2)

    def test_search_is_url_encoded(self):
        self.say("search for python & django tutorials")
        self.assertEqual(self.opened[-1], "https://www.google.com/search?q=python+%26+django+tutorials")

    def test_youtube(self):
        self.say("play lofi music on youtube")
        self.assertEqual(self.opened[-1], "https://www.youtube.com/results?search_query=lofi+music")

    def test_maths_phrases(self):
        self.assertEqual(self.say("what is 12 times 7"), "The answer is 84.")
        self.assertEqual(self.say("calculate 100 divided by 8"), "The answer is 12.5.")
        self.assertIn("divide by zero", self.say("what is 5 divided by 0"))

    def test_notes_flow(self):
        self.assertEqual(self.say("read my notes"), "You have no notes.")
        self.assertIn("buy milk", self.say("take a note buy milk"))
        self.say("note: call the dentist")
        text = self.say("read my notes")
        self.assertIn("2 notes", text)
        self.assertIn("buy milk", text)
        self.assertIn("Deleted 2 notes", self.say("clear my notes"))
        self.assertEqual(self.say("read my notes"), "You have no notes.")

    def test_fun_commands(self):
        self.assertIn(self.say("flip a coin"), ["It's heads.", "It's tails."])
        self.assertRegex(self.say("roll a dice"), r"You rolled a [1-6]\.")
        self.assertTrue(self.say("tell me a joke"))

    def test_help_and_unknown(self):
        self.assertIn("take notes", self.say("help"))
        self.assertIn("Sorry", self.say("make me a sandwich"))
        self.assertEqual(self.say("   "), "I didn't catch that.")
        self.assertEqual(self.opened, [])


class NoteStoreTests(unittest.TestCase):
    def test_corrupt_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "n.json"
            path.write_text("{ not json")
            store = NoteStore(path)
            self.assertEqual(store.all(), [])
            store.add("works again")
            self.assertEqual(len(store.all()), 1)


class WakeWordTests(unittest.TestCase):
    def test_strip(self):
        self.assertEqual(strip_wake_word("Jarvis, what time is it", "jarvis"), "what time is it")
        self.assertEqual(strip_wake_word("hey jarvis open youtube", "jarvis"), "open youtube")
        self.assertIsNone(strip_wake_word("what time is it", "jarvis"))
        self.assertEqual(strip_wake_word("anything", None), "anything")

    def test_normalize(self):
        self.assertEqual(normalize("  What   TIME is it?! "), "what time is it")


class ScriptedIO:
    def __init__(self, inputs):
        self.inputs, self.spoken = list(inputs), []

    def listen(self):
        return self.inputs.pop(0) if self.inputs else "exit"

    def speak(self, text):
        self.spoken.append(text)


class LoopTests(unittest.TestCase):
    def make(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Assistant(notes=NoteStore(Path(tmp.name) / "n.json"), opener=lambda u: None, now=lambda: FIXED)

    def test_loop_until_exit(self):
        io = ScriptedIO(["", "what time is it", "bye", "never reached"])
        run_loop(io, self.make())
        self.assertEqual(io.spoken[1], "It's 3:05 PM.")
        self.assertEqual(io.spoken[-1], "Goodbye!")
        self.assertEqual(io.inputs, ["never reached"])

    def test_wake_word_filters_commands(self):
        io = ScriptedIO(["what time is it", "jarvis what time is it", "jarvis bye"])
        run_loop(io, self.make(), wake_word="jarvis")
        self.assertEqual(io.spoken.count("It's 3:05 PM."), 1)


class VoiceFallbackTests(unittest.TestCase):
    def test_missing_packages_give_helpful_error(self):
        with mock.patch.dict(sys.modules, {"speech_recognition": None, "pyttsx3": None}):
            with self.assertRaises(SpeechUnavailable) as ctx:
                VoiceIO()
        self.assertIn("requirements-voice.txt", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
