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
from assistant import keys, system
from assistant.apps import load_custom_apps
from assistant.timers import format_duration, parse_duration
from assistant.wiki import summary as wiki_summary
from assistant.youtube import first_video_url

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
        self.launched = []
        self.launch_ok = True
        self.scheduled = []   # (seconds, fire) pairs; tests call fire() instead of waiting
        self.volume_calls = []
        self.power_calls = []
        self.system_ok = True
        self.keys_pressed = []
        self.summaries = {"ada lovelace": "Ada Lovelace was an English mathematician."}
        self.a = Assistant(notes=NoteStore(Path(self._tmp.name) / "n.json"), opener=self.opened.append,
                           now=lambda: FIXED, rng=random.Random(1), video_finder=lambda q: None,
                           app_launcher=self._launch, scheduler=self._schedule,
                           summary_finder=lambda topic: self.summaries.get(topic),
                           volume_controller=self._volume, power_controller=self._power,
                           key_sender=self._keys)

    def tearDown(self):
        self._tmp.cleanup()

    def _schedule(self, seconds, fire):
        handle = mock.Mock()
        self.scheduled.append((seconds, fire, handle))
        return handle

    def _keys(self, name):
        self.keys_pressed.append(name)
        return self.system_ok

    def _volume(self, action, value=None):
        self.volume_calls.append((action, value))
        return self.system_ok

    def _power(self, action):
        self.power_calls.append(action)
        return self.system_ok

    def _launch(self, command):
        self.launched.append(command)
        return self.launch_ok

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

    def test_natural_phrasing_for_open(self):
        for phrase in ["can you open youtube", "please open youtube", "go to youtube",
                       "launch YouTube", "open you tube", "could you please open youtube"]:
            self.opened.clear()
            self.assertEqual(self.say(phrase).split()[0], "Opening", phrase)
            self.assertEqual(self.opened, ["https://www.youtube.com"], phrase)
        self.say("open stack overflow")
        self.assertEqual(self.opened[-1], "https://stackoverflow.com")

    def test_open_desktop_apps(self):
        cases = {"open notepad": "notepad", "open calculator": "calc", "can you open VS Code": "code",
                 "launch note pad": "notepad", "start chrome": "chrome", "open task manager": "taskmgr"}
        for phrase, command in cases.items():
            self.assertEqual(self.say(phrase).split()[0], "Opening", phrase)
            self.assertEqual(self.launched[-1], command, phrase)
        self.assertEqual(self.opened, [])  # apps are not opened in the browser

    def test_whatsapp_and_other_store_apps(self):
        for phrase, command in {"open whatsapp": "whatsapp:", "open spotify": "spotify:",
                                "open camera": "microsoft.windows.camera:", "open control panel": "control"}.items():
            self.assertEqual(self.say(phrase).split()[0], "Opening", phrase)
            self.assertEqual(self.launched[-1], command, phrase)

    def test_app_that_is_not_installed_falls_back_to_the_website(self):
        self.launch_ok = False
        self.assertIn("opening it in the browser", self.say("open whatsapp"))
        self.assertEqual(self.opened[-1], "https://web.whatsapp.com")
        self.assertIn("couldn't open notepad", self.say("open notepad"))  # no website for this one

    def test_custom_apps_from_apps_json(self):
        self.a.custom_apps = {"my game": r"C:\Games\game.exe", "notepad": "notepad++"}
        self.assertEqual(self.say("open my game").split()[0], "Opening")
        self.assertEqual(self.launched[-1], r"C:\Games\game.exe")
        self.say("open notepad")
        self.assertEqual(self.launched[-1], "notepad++")  # your own list beats the built-in one

    def test_app_that_cannot_start_is_reported(self):
        self.launch_ok = False
        self.assertIn("couldn't open notepad", self.say("open notepad"))

    def test_sites_still_win_and_unknown_apps_are_refused(self):
        self.say("open youtube")
        self.assertEqual((self.opened[-1], self.launched), ("https://www.youtube.com", []))
        self.assertIn("website or app", self.say("open mystery program"))
        self.assertEqual(self.launched, [])

    def test_timer_fires_an_alert(self):
        self.assertEqual(self.say("set a timer for 5 minutes"), "Okay, timer set for 5 minutes.")
        seconds, fire, _ = self.scheduled[-1]
        self.assertEqual(seconds, 300)
        self.assertEqual(self.a.pop_alerts(), [])
        fire()
        self.assertEqual(self.a.pop_alerts(), ["Time's up! Your timer for 5 minutes is done."])
        self.assertEqual(self.a.pop_alerts(), [])

    def test_timer_words_and_limits(self):
        self.say("timer for ten seconds")
        self.say("set a timer for an hour")
        self.assertEqual([s[0] for s in self.scheduled], [10, 3600])
        self.assertIn("How long", self.say("set a timer for a while"))
        self.assertIn("between 1 second and 24 hours", self.say("set a timer for 48 hours"))
        self.assertEqual(len(self.scheduled), 2)

    def test_reminders_in_both_word_orders(self):
        self.assertIn("call mom", self.say("remind me in 10 minutes to call mom"))
        self.assertIn("call mom", self.say("remind me to call mom in 2 hours"))
        self.assertEqual([s[0] for s in self.scheduled], [600, 7200])
        self.scheduled[0][1]()
        self.assertEqual(self.a.pop_alerts(), ["Reminder: call mom."])

    def test_cancel_timers_does_not_exit(self):
        self.say("timer for 1 minute")
        self.say("timer for 2 minutes")
        reply = self.a.handle("stop my timers")
        self.assertFalse(reply.exit)
        self.assertEqual(reply.text, "Cancelled 2 timers.")
        self.assertTrue(all(s[2].cancel.called for s in self.scheduled))
        self.assertEqual(self.say("cancel timers"), "You have no active timers.")

    def test_fired_timer_is_not_cancelled_later(self):
        self.say("timer for 1 minute")
        self.scheduled[0][1]()
        self.assertEqual(self.say("cancel timers"), "You have no active timers.")

    def test_alert_sink_gets_alerts_immediately(self):
        got = []
        self.a.alert_sink = got.append
        self.say("timer for 5 seconds")
        self.scheduled[0][1]()
        self.assertEqual(got, ["Time's up! Your timer for 5 seconds is done."])
        self.assertEqual(self.a.pop_alerts(), [])

    def test_delete_one_note(self):
        self.say("take a note buy milk")
        self.say("take a note call mom")
        self.assertEqual(self.say("delete note 1"), "Deleted note 1: buy milk.")
        self.assertIn("call mom", self.say("read my notes"))
        self.assertNotIn("buy milk", self.say("read my notes"))
        self.assertEqual(self.say("remove note five"), "I can't find note 5.")
        self.assertIn("Which note", self.say("delete note abc"))

    def test_weather_opens_search(self):
        self.assertEqual(self.say("what's the weather in karachi"), "Showing the weather for karachi.")
        self.assertEqual(self.opened[-1], "https://www.google.com/search?q=weather+karachi")
        self.assertEqual(self.say("weather"), "Showing the weather.")
        self.assertEqual(self.opened[-1], "https://www.google.com/search?q=weather")

    def test_knowledge_questions(self):
        self.assertEqual(self.say("who is Ada Lovelace"), "Ada Lovelace was an English mathematician.")
        self.assertEqual(self.say("tell me about ada lovelace"), "Ada Lovelace was an English mathematician.")
        self.assertIn("couldn't find anything about zzz", self.say("what is zzz"))

    def test_maths_and_time_beat_knowledge_lookup(self):
        self.assertEqual(self.say("what is 2 plus 2"), "The answer is 4.")
        self.assertEqual(self.say("what is the time"), "It's 3:05 PM.")
        self.assertIn("voice assistant", self.say("who are you"))

    def test_shutdown_asks_first_and_runs_only_after_yes(self):
        self.assertIn("Are you sure", self.say("shut down the computer"))
        self.assertEqual(self.power_calls, [])
        self.assertTrue(self.a.awaiting_confirmation)
        reply = self.say("yes")
        self.assertEqual(self.power_calls, ["shutdown"])
        self.assertIn("cancel shutdown", reply)
        self.assertFalse(self.a.awaiting_confirmation)

    def test_restart_and_plain_shut_down_do_not_exit_the_assistant(self):
        reply = self.a.handle("restart")
        self.assertFalse(reply.exit)
        self.assertIn("restart", reply.text)
        reply = self.a.handle("shut down")
        self.assertFalse(reply.exit)
        self.say("yes")
        self.assertEqual(self.power_calls, ["shutdown"])
        self.assertTrue(self.a.handle("exit").exit)

    def test_declining_or_changing_the_subject_never_shuts_down(self):
        self.say("shut down")
        self.assertEqual(self.say("no"), "Okay, cancelled.")
        self.say("restart the pc")
        self.assertEqual(self.say("what time is it"), "It's 3:05 PM.")  # answers normally, drops the request
        self.say("yes")  # nothing is waiting any more
        self.assertEqual(self.power_calls, [])

    def test_cancel_shutdown_and_lock_need_no_confirmation(self):
        self.assertIn("cancelled", self.say("cancel shutdown"))
        self.assertEqual(self.say("lock the computer"), "Locking the computer.")
        self.assertEqual(self.power_calls, ["cancel", "lock"])
        self.system_ok = False
        self.assertIn("no shutdown waiting", self.say("abort shutdown"))
        self.assertIn("couldn't do that", self.say("lock my pc"))

    def test_power_failure_is_reported(self):
        self.system_ok = False
        self.say("shut down")
        self.assertIn("couldn't do that", self.say("yes"))

    def test_volume_commands(self):
        cases = {"volume up": ("up", None), "turn the volume down": ("down", None), "louder": ("up", None),
                 "lower the volume": ("down", None), "mute": ("mute", None), "unmute": ("mute", None),
                 "set volume to 50": ("set", 50), "set the volume to fifty percent": ("set", 50),
                 "volume 30": ("set", 30), "volume to zero": ("set", 0)}
        for phrase, call in cases.items():
            self.volume_calls.clear()
            self.assertTrue(self.say(phrase).startswith(("Volume", "Toggled")), phrase)
            self.assertEqual(self.volume_calls, [call], phrase)

    def test_volume_rejects_bad_levels_and_reports_failure(self):
        self.assertIn("between 0 and 100", self.say("set volume to 150"))
        self.assertIn("Which volume level", self.say("set volume to loud"))
        self.assertEqual(self.volume_calls, [])
        self.system_ok = False
        self.assertIn("couldn't change the volume", self.say("volume up"))

    def test_spoken_keyboard_shortcuts(self):
        cases = {
            "refresh": "refresh", "Refresh the page": "refresh", "reload": "refresh", "press F5": "refresh",
            "hard refresh": "hard_refresh", "go back": "back", "back": "back", "go forward": "forward",
            "new tab": "new_tab", "open a new tab": "new_tab", "close this tab": "close_tab",
            "next tab": "next_tab", "previous tab": "previous_tab", "reopen closed tab": "reopen_tab",
            "scroll down": "scroll_down", "scroll up": "scroll_up", "go to the top of the page": "top",
            "scroll to the bottom": "bottom", "zoom in": "zoom_in", "zoom out": "zoom_out", "reset zoom": "zoom_reset",
            "full screen": "fullscreen", "copy": "copy", "paste": "paste", "cut that": "cut",
            "select all": "select_all", "undo": "undo", "redo": "redo", "save": "save", "find on page": "find",
            "switch window": "switch_window", "show desktop": "show_desktop", "take a screenshot": "screenshot",
            "press enter": "enter", "pause": "media_play_pause", "resume music": "media_play_pause",
            "next song": "media_next", "previous song": "media_prev",
        }
        for phrase, shortcut in cases.items():
            self.keys_pressed.clear()
            reply = self.a.handle(phrase)
            self.assertEqual(self.keys_pressed, [shortcut], phrase)
            self.assertFalse(reply.exit, phrase)
        self.assertEqual(self.opened, [])
        self.assertEqual(self.launched, [])

    def test_shortcut_phrases_do_not_steal_other_commands(self):
        self.say("take a note save the report")
        self.say("open new york times")
        self.say("search for how to refresh a page")
        self.say("play next to me on youtube")
        self.assertEqual(self.keys_pressed, [])
        self.assertTrue(self.a.handle("stop").exit)

    def test_shortcut_failure_is_reported(self):
        self.system_ok = False
        self.assertIn("couldn't do that", self.say("refresh"))

    def test_search_is_url_encoded(self):
        self.say("search for python & django tutorials")
        self.assertEqual(self.opened[-1], "https://www.google.com/search?q=python+%26+django+tutorials")

    def test_youtube_search(self):
        self.say("search youtube for lofi music")
        self.assertEqual(self.opened[-1], "https://www.youtube.com/results?search_query=lofi+music")

    def test_play_opens_first_video(self):
        self.a.video_finder = lambda q: "https://www.youtube.com/watch?v=abcdefghijk"
        self.assertEqual(self.say("play lofi music on youtube"), "Playing lofi music on YouTube.")
        self.assertEqual(self.opened[-1], "https://www.youtube.com/watch?v=abcdefghijk")

    def test_play_falls_back_to_search_results(self):
        reply = self.say("play lofi music")  # setUp's finder finds nothing
        self.assertIn("showing YouTube results", reply)
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


class YouTubeLookupTests(unittest.TestCase):
    class FakeResponse:
        def __init__(self, text): self.text = text
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def read(self): return self.text.encode()

    def test_picks_first_video_result(self):
        html = '{"adRenderer":{"videoId":"zzzzzzzzzzz"}} "videoRenderer":{"videoId":"jfKfPfyJRdk","x":1} "videoRenderer":{"videoId":"second12345"}'
        seen = []
        def fake(request, timeout):
            seen.append(request.full_url)
            return self.FakeResponse(html)
        self.assertEqual(first_video_url("lofi music", fetch=fake), "https://www.youtube.com/watch?v=jfKfPfyJRdk")
        self.assertEqual(seen, ["https://www.youtube.com/results?search_query=lofi+music"])

    def test_returns_none_when_offline_or_page_changed(self):
        def offline(request, timeout):
            raise OSError("no internet")
        self.assertIsNone(first_video_url("x", fetch=offline))
        self.assertIsNone(first_video_url("x", fetch=lambda r, timeout: self.FakeResponse("<html>nothing</html>")))


class SystemControlTests(unittest.TestCase):
    def test_volume_key_presses(self):
        presses = []
        self.assertTrue(system.volume("up", press=presses.append))
        self.assertEqual(presses, [system.VK_VOLUME_UP] * 5)
        presses.clear()
        system.volume("set", 50, press=presses.append)  # 50 steps down to zero, 25 steps up
        self.assertEqual(presses.count(system.VK_VOLUME_DOWN), 50)
        self.assertEqual(presses.count(system.VK_VOLUME_UP), 25)
        presses.clear()
        system.volume("mute", press=presses.append)
        self.assertEqual(presses, [system.VK_VOLUME_MUTE])
        self.assertFalse(system.volume("set", 101, press=presses.append))
        self.assertFalse(system.volume("explode", press=presses.append))

    def test_power_commands_have_a_delay_so_they_can_be_cancelled(self):
        ran = []
        run = lambda cmd, check: ran.append(cmd)
        for action in ("shutdown", "restart", "cancel", "lock"):
            self.assertTrue(system.power(action, run=run))
        self.assertEqual(ran[0], ["shutdown", "/s", "/t", "30"])
        self.assertEqual(ran[1], ["shutdown", "/r", "/t", "30"])
        self.assertEqual(ran[2], ["shutdown", "/a"])
        self.assertEqual(ran[3][0], "rundll32.exe")
        self.assertFalse(system.power("format_disk", run=run))

    def test_power_failure_returns_false(self):
        def boom(cmd, check):
            raise OSError("no such program")
        self.assertFalse(system.power("shutdown", run=boom))

    def test_nothing_happens_when_not_on_windows(self):
        with mock.patch("assistant.system.platform.system", return_value="Linux"):
            self.assertFalse(system.volume("up"))
            self.assertFalse(system.power("shutdown"))


class KeyShortcutTests(unittest.TestCase):
    def test_modifiers_are_pressed_first_and_released_last(self):
        events = []
        self.assertTrue(keys.send_shortcut("hard_refresh", key_event=lambda vk, up: events.append((vk, up))))
        self.assertEqual(events, [(keys.VK["CTRL"], False), (keys.VK["F5"], False),
                                  (keys.VK["F5"], True), (keys.VK["CTRL"], True)])

    def test_refresh_is_f5(self):
        events = []
        keys.send_shortcut("refresh", key_event=lambda vk, up: events.append((vk, up)))
        self.assertEqual(events, [(0x74, False), (0x74, True)])

    def test_unknown_shortcut_and_non_windows(self):
        self.assertFalse(keys.send_shortcut("format_disk", key_event=lambda vk, up: None))
        with mock.patch("assistant.keys.platform.system", return_value="Linux"):
            self.assertFalse(keys.send_shortcut("refresh"))

    def test_every_command_points_to_a_real_shortcut_with_known_keys(self):
        import re
        for pattern, name, reply in keys.COMMANDS:
            re.compile(pattern)
            self.assertIn(name, keys.SHORTCUTS, name)
            self.assertTrue(reply)
        for name, combo in keys.SHORTCUTS.items():
            self.assertTrue(all(k in keys.VK for k in combo), name)


class CustomAppsFileTests(unittest.TestCase):
    def test_load_custom_apps(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "apps.json"
            self.assertEqual(load_custom_apps(path), {})  # missing file
            path.write_text('{"My Game": "game.exe", "bad": 5, "empty": " "}', encoding="utf-8")
            self.assertEqual(load_custom_apps(path), {"my game": "game.exe"})
            path.write_text("{ not json", encoding="utf-8")
            self.assertEqual(load_custom_apps(path), {})
            path.write_text("[1, 2]", encoding="utf-8")
            self.assertEqual(load_custom_apps(path), {})


class TimerParsingTests(unittest.TestCase):
    def test_parse_duration(self):
        cases = {"5 minutes": 300, "30 sec": 30, "an hour": 3600, "a minute": 60, "two hours": 7200,
                 "1.5 hours": 5400, "twenty five minutes": 1500, "ten seconds": 10}
        for text, seconds in cases.items():
            self.assertEqual(parse_duration(text), seconds, text)
        for text in ["soon", "5", "five parsecs"]:
            self.assertIsNone(parse_duration(text), text)

    def test_format_duration(self):
        self.assertEqual(format_duration(1), "1 second")
        self.assertEqual(format_duration(90), "90 seconds")
        self.assertEqual(format_duration(300), "5 minutes")
        self.assertEqual(format_duration(3600), "1 hour")


class WikiTests(unittest.TestCase):
    class FakeResponse:
        def __init__(self, text): self.text = text
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def read(self): return self.text.encode()

    def test_returns_first_two_sentences(self):
        body = '{"type":"standard","extract":"Python is a language. It is popular. It was made by Guido."}'
        urls = []
        def fake(request, timeout):
            urls.append(request.full_url)
            return self.FakeResponse(body)
        self.assertEqual(wiki_summary("python", fetch=fake), "Python is a language. It is popular.")
        self.assertEqual(urls, ["https://en.wikipedia.org/api/rest_v1/page/summary/Python"])

    def test_missing_ambiguous_and_offline_give_none(self):
        def offline(request, timeout):
            raise OSError("no internet")
        self.assertIsNone(wiki_summary("x", fetch=offline))
        ambiguous = lambda r, timeout: self.FakeResponse('{"type":"disambiguation","extract":"X may refer to:"}')
        self.assertIsNone(wiki_summary("x", fetch=ambiguous))


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

    def test_loop_speaks_alerts_that_fired_while_waiting(self):
        assistant = self.make()
        assistant._alerts.put("Time's up!")
        io = ScriptedIO(["bye"])
        run_loop(io, assistant)
        self.assertEqual(io.spoken[:2], ["Hello! I'm ready. Say help to hear what I can do.", "Time's up!"])

    def test_yes_to_are_you_sure_needs_no_wake_word(self):
        calls = []
        assistant = self.make()
        assistant.power_controller = lambda action: calls.append(action) or True
        io = ScriptedIO(["jarvis shut down", "yes", "jarvis bye"])
        run_loop(io, assistant, wake_word="jarvis")
        self.assertEqual(calls, ["shutdown"])

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
