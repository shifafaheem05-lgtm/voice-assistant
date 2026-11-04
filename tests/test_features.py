"""Tests for the v2 features: WhatsApp and email, contacts, sites, conversions, Roman Urdu, alarms, PC control."""
import random
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from assistant import Assistant, apps, keys, system, sysinfo
from assistant.cli import run_loop
from assistant.contacts import ContactStore
from assistant.convert import convert_units, fetch_rate, parse_conversion
from assistant.engine import split_compound
from assistant.messaging import (normalize_phone, parse_contact_details, spoken_to_digits,
                                 split_recipient_and_text, whatsapp_app_url, whatsapp_web_url)
from assistant.notes import NoteStore
from assistant.sites import find_site, load_custom_sites, search_url
from assistant.timers import parse_clock_time
from assistant.urdu import to_english

NOW = datetime(2026, 11, 5, 15, 0)


class MessagingHelperTests(unittest.TestCase):
    def test_phone_numbers(self):
        cases = {"0300 1234567": "923001234567", "+92 300 1234567": "923001234567", "0092 300 1234567": "923001234567",
                 "3001234567": "923001234567", "923001234567": "923001234567", "0300-1234567": "923001234567"}
        for raw, expected in cases.items():
            self.assertEqual(normalize_phone(raw), expected, raw)
        self.assertEqual(normalize_phone("0300 1234567", country_code="1"), "13001234567")

    def test_spoken_phone_numbers(self):
        self.assertEqual(spoken_to_digits("zero three double zero"), "0 3 00")
        self.assertEqual(normalize_phone("zero three zero zero one two three four five six seven"), "923001234567")
        self.assertEqual(normalize_phone("plus nine two three zero zero one two three four five six seven"), "923001234567")

    def test_not_phone_numbers(self):
        for text in ["ali", "", "12", "call me at 5", "0300 abc"]:
            self.assertIsNone(normalize_phone(text), text)

    def test_links_are_encoded(self):
        self.assertEqual(whatsapp_app_url("923001234567", "hi & bye?"), "whatsapp://send?phone=923001234567&text=hi%20%26%20bye%3F")
        self.assertEqual(whatsapp_web_url("923001234567", "a b"), "https://web.whatsapp.com/send?phone=923001234567&text=a%20b")

    def test_split_recipient_and_text(self):
        names = ["ali", "ahmed khan"]
        cases = {
            "ali saying hello there": ("ali", "hello there"),
            "ali that I am late": ("ali", "that I am late"),  # no keyword -> known name wins
            "ahmed khan see you": ("ahmed khan", "see you"),
            "sara: how are you": ("sara", "how are you"),
            "sara hello": ("sara", "hello"),
            "0300 1234567 call me": ("0300 1234567", "call me"),
            "zero three zero zero one two three four five six seven hello": ("zero three zero zero one two three four five six seven", "hello"),
            "ali": ("ali", ""),
            "ali with the message good night": ("ali", "good night"),
        }
        for rest, expected in cases.items():
            self.assertEqual(split_recipient_and_text(rest, names), expected, rest)

    def test_parse_contact_details(self):
        self.assertEqual(parse_contact_details("ali 0300 1234567"), ("ali", "0300 1234567", None))
        self.assertEqual(parse_contact_details("ali phone number is 0300 1234567"), ("ali", "0300 1234567", None))
        self.assertEqual(parse_contact_details("sara email sara at gmail dot com"), ("sara", None, "sara@gmail.com"))
        self.assertEqual(parse_contact_details("bob bob@x.org 0300 1234567"), ("bob", "0300 1234567", "bob@x.org"))
        self.assertEqual(parse_contact_details("ali"), ("ali", None, None))


class ContactStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = ContactStore(Path(self._tmp.name) / "c.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_add_find_remove(self):
        self.store.add("Ali", phone="923001234567")
        self.store.add("ali", email="ali@example.com")  # updates, keeps the phone
        self.assertEqual(self.store.find("ALI")[1], {"phone": "923001234567", "email": "ali@example.com"})
        self.assertEqual(self.store.names(), ["ali"])
        self.assertEqual(self.store.remove("ali"), "ali")
        self.assertIsNone(self.store.find("ali"))
        self.assertIsNone(self.store.remove("ali"))

    def test_fuzzy_names(self):
        self.store.add("ali", phone="1")
        self.store.add("ahmed khan", phone="2")
        self.assertEqual(self.store.find("alli")[0], "ali")   # speech recognition guesses
        self.assertEqual(self.store.find("ahmed")[0], "ahmed khan")
        self.assertIsNone(self.store.find("zebra"))
        self.assertIsNone(self.store.find(""))

    def test_corrupt_file_is_ignored(self):
        self.store.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.store.all(), {})
        self.store.path.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(self.store.all(), {})


class FeatureTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.opened, self.launched, self.keys_pressed, self.scheduled = [], [], [], []
        self.launch_ok = False       # False = the WhatsApp desktop app is not installed -> WhatsApp Web
        self.typed = []
        self.closed = []
        self.brightness_calls = []
        self.rates = {("USD", "PKR"): 280.0}
        self.contacts = ContactStore(Path(self._tmp.name) / "c.json")
        self.make()

    def make(self, **kwargs):
        options = dict(
            notes=NoteStore(Path(self._tmp.name) / "n.json"), contacts=self.contacts, opener=self.opened.append,
            now=lambda: NOW, rng=random.Random(1), video_finder=lambda q: None, app_launcher=self._launch,
            scheduler=self._schedule, summary_finder=lambda t: None, volume_controller=lambda *a: True,
            power_controller=lambda a: True, key_sender=self._key, text_typer=self._type,
            brightness_controller=lambda action, value=None: self.brightness_calls.append((action, value)) or True,
            app_closer=self._close, status_reader=lambda kind: f"status of {kind}",
            rate_fetcher=lambda a, b: self.rates.get((a, b)), home=Path("/home/me"))
        options.update(kwargs)
        self.a = Assistant(**options)

    def tearDown(self):
        self._tmp.cleanup()

    def _launch(self, command):
        self.launched.append(command)
        return self.launch_ok

    def _schedule(self, seconds, fire):
        handle = mock.Mock()
        self.scheduled.append((seconds, fire, handle))
        return handle

    def _key(self, name):
        self.keys_pressed.append(name)
        return True

    def _type(self, text):
        self.typed.append(text)
        return True

    def _close(self, name):
        self.closed.append(name)
        return None if name == "unknownapp" else True

    def say(self, text):
        return self.a.handle(text).text


class WhatsAppTests(FeatureTestCase):
    def setUp(self):
        super().setUp()
        self.contacts.add("ali", phone="923001234567")
        self.contacts.add("ahmed khan", phone="923121234567")

    def test_message_is_confirmed_then_sent(self):
        reply = self.say("send a message to ali saying Hello Ali, I'll be late")
        self.assertEqual(reply, "Send 'Hello Ali, I'll be late' to Ali on WhatsApp? Say yes to confirm.")
        self.assertTrue(self.a.awaiting_confirmation)
        self.assertEqual(self.opened, [])  # nothing is sent before the yes
        self.assertIn("Sending your message to Ali", self.say("yes"))
        self.assertEqual(self.opened[-1], "https://web.whatsapp.com/send?phone=923001234567&text=Hello%20Ali%2C%20I%27ll%20be%20late")
        self.assertFalse(self.a.awaiting_confirmation)

    def test_enter_is_pressed_after_the_chat_has_loaded(self):
        self.say("whatsapp ali hello")
        self.say("yes")
        seconds, fire, _ = self.scheduled[-1]
        self.assertEqual(seconds, Assistant.WEB_SEND_DELAY)
        self.assertEqual(self.keys_pressed, [])   # not yet
        fire()
        self.assertEqual(self.keys_pressed, ["enter"])

    def test_desktop_app_is_preferred_when_installed(self):
        self.launch_ok = True
        self.say("message ali hello")
        self.say("yes")
        self.assertEqual(self.launched[-1], "whatsapp://send?phone=923001234567&text=hello")
        self.assertEqual(self.opened, [])
        self.assertEqual(self.scheduled[-1][0], Assistant.APP_SEND_DELAY)

    def test_custom_delay_and_no_auto_send(self):
        self.make(send_delay=3)
        self.say("message ali hi")
        self.say("yes")
        self.assertEqual(self.scheduled[-1][0], 3)
        self.make(auto_send=False)
        self.scheduled.clear()
        self.say("message ali hi")
        self.assertIn("Press Enter", self.say("yes"))
        self.assertEqual(self.scheduled, [])

    def test_no_confirm_option_sends_straight_away(self):
        self.make(confirm_messages=False)
        self.assertIn("Sending your message to Ali", self.say("send message to ali saying on my way"))
        self.assertIn("text=on%20my%20way", self.opened[-1])

    def test_decline_or_change_of_mind_sends_nothing(self):
        self.say("message ali hello")
        self.assertIn("won't send", self.say("no"))
        self.say("message ali hello")
        self.say("what time is it")           # something else: the message is dropped
        self.assertEqual(self.opened, [])
        self.assertFalse(self.a.awaiting_confirmation)
        self.assertEqual(self.scheduled, [])

    def test_asks_what_to_say(self):
        self.assertEqual(self.say("send a whatsapp message to ali"), "What should I say to Ali?")
        self.assertIn("Send 'How are you' to Ali", self.say("How are you"))
        self.say("yes")
        self.assertIn("text=How%20are%20you", self.opened[-1])  # capital letters kept

    def test_text_given_after_a_question_is_always_confirmed(self):
        self.make(confirm_messages=False)
        self.say("message ali")
        self.assertIn("Say yes to confirm", self.say("open youtube"))   # free speech is never sent unchecked
        self.assertEqual(self.opened, [])

    def test_cancel_when_asked_what_to_say(self):
        self.say("message ali")
        self.assertEqual(self.say("cancel"), "Okay, cancelled.")

    def test_phrasings(self):
        phrases = [
            "send hi to ali on whatsapp", "send message to ali saying hi",
            "open whatsapp and send message to ali saying hi", "whatsapp ali saying hi", "text ali hi",
            "send whatsapp to ali saying hi", "can you please message ali hi", "send hi to ali",
        ]
        for phrase in phrases:
            self.assertEqual(self.say(phrase), "Send 'hi' to Ali on WhatsApp? Say yes to confirm.", phrase)
            self.say("no")

    def test_open_whatsapp_and_send_does_not_cut_the_message_at_and(self):
        reply = self.say("open whatsapp and send message to ali saying bring tea and biscuits")
        self.assertIn("'bring tea and biscuits'", reply)

    def test_multi_word_contact_and_phone_numbers(self):
        self.assertIn("to Ahmed Khan", self.say("send message to ahmed khan good night"))
        self.say("no")
        self.assertIn("to +923005551234", self.say("message 0300 5551234 call me"))
        self.say("yes")
        self.assertIn("phone=923005551234", self.opened[-1])

    def test_unknown_contact_explains_how_to_add(self):
        reply = self.say("send message to bob saying hi")
        self.assertIn("don't have a contact called bob", reply)
        self.assertIn("add contact bob", reply)
        self.assertFalse(self.a.awaiting_confirmation)

    def test_contact_without_phone(self):
        self.contacts.add("sara", email="sara@example.com")
        self.assertIn("no phone number", self.say("message sara hi"))

    def test_send_x_to_y_only_for_known_recipients(self):
        self.assertIn("Sorry, I don't know", self.say("send the report to my printer"))
        self.assertIn("Send 'the report'", self.say("send the report to ali"))

    def test_whatsapp_web_word(self):
        self.say("whatsapp web")
        self.assertEqual(self.opened[-1], "https://web.whatsapp.com")

    def test_wake_word_not_needed_for_the_answer(self):
        class Script:
            def __init__(self, lines):
                self.lines, self.spoken = list(lines), []

            def listen(self):
                return self.lines.pop(0) if self.lines else "exit"

            def speak(self, text):
                self.spoken.append(text)

        io = Script(["jarvis, message ali hello", "yes", "jarvis exit"])
        run_loop(io, self.a, wake_word="jarvis", max_turns=3)
        self.assertTrue(any("Sending your message" in line for line in io.spoken))


class ContactCommandTests(FeatureTestCase):
    def test_add_list_lookup_delete(self):
        self.assertEqual(self.say("add contact ali 0300 1234567"), "Saved Ali with number +923001234567.")
        self.assertIn("sara@gmail.com", self.say("add contact sara email sara at gmail dot com"))
        self.assertEqual(self.say("list contacts"), "You have 2 contacts: Ali, Sara.")
        self.assertEqual(self.say("what is the number of ali"), "Ali's number is +923001234567.")
        self.assertEqual(self.say("what's the email of sara"), "Sara's email is sara@gmail.com.")
        self.assertIn("no number", self.say("what is the number of sara"))
        self.assertEqual(self.say("delete contact ali"), "Deleted the contact Ali.")
        self.assertIn("can't find", self.say("delete contact ali"))

    def test_bad_input(self):
        self.assertIn("doesn't look like a phone number", self.say("add contact ali 12"))
        self.assertIn("What is ali's phone number", self.say("add contact ali"))
        self.assertIn("no contacts yet", self.say("list contacts"))

    def test_spoken_digits(self):
        self.say("add contact ali zero three zero zero one two three four five six seven")
        self.assertEqual(self.contacts.find("ali")[1]["phone"], "923001234567")


class EmailTests(FeatureTestCase):
    def setUp(self):
        super().setUp()
        self.contacts.add("sara", email="sara@example.com")

    def test_compose_with_contact_subject_and_body(self):
        self.assertIn("sara@example.com", self.say("send an email to sara about the Project report"))
        self.assertEqual(self.opened[-1], "https://mail.google.com/mail/?view=cm&fs=1&to=sara%40example.com&su=the+Project+report&body=")
        self.say("email sara saying Please call me")
        self.assertTrue(self.opened[-1].endswith("&su=&body=Please+call+me"))

    def test_blank_email_and_unknown_contact(self):
        self.say("send email")
        self.assertEqual(self.opened[-1], "https://mail.google.com/mail/?view=cm&fs=1&to=&su=&body=")
        self.assertIn("don't have an email address for bob", self.say("send email to bob"))
        self.say("send email to bob@example.org")
        self.assertIn("to=bob%40example.org", self.opened[-1])


class SiteTests(FeatureTestCase):
    def test_many_sites_and_spoken_variants(self):
        for spoken, url in {"claude": "https://claude.ai", "chat gpt": "https://chatgpt.com", "you tube": "https://www.youtube.com",
                            "insta": "https://www.instagram.com", "google drive": "https://drive.google.com",
                            "daraz": "https://www.daraz.pk", "stack overflow": "https://stackoverflow.com"}.items():
            self.assertEqual(find_site(spoken), url, spoken)
        self.assertIsNone(find_site("no such site"))
        self.assertEqual(self.say("open claude"), "Opening claude.")
        self.assertEqual(self.opened[-1], "https://claude.ai")

    def test_open_several_at_once(self):
        self.say("open youtube, google and github")
        self.assertEqual(self.opened, ["https://www.youtube.com", "https://www.google.com", "https://github.com"])
        self.assertIn("don't know", self.say("open youtube and my secret files"))

    def test_open_link(self):
        self.say("open https://example.com/page")
        self.assertEqual(self.opened[-1], "https://example.com/page")

    def test_site_search(self):
        self.say("search amazon for usb cable")
        self.assertEqual(self.opened[-1], "https://www.amazon.com/s?k=usb+cable")
        self.say("search python tutorials on youtube")
        self.assertEqual(self.opened[-1], "https://www.youtube.com/results?search_query=python+tutorials")
        self.say("open github and search for voice assistant")
        self.assertEqual(self.opened[-1], "https://github.com/search?q=voice+assistant")
        self.say("find coffee shops on maps")
        self.assertEqual(self.opened[-1], "https://www.google.com/maps/search/coffee+shops")

    def test_unknown_site_becomes_a_normal_search(self):
        self.say("search for tips on python")
        self.assertEqual(self.opened[-1], "https://www.google.com/search?q=tips+on+python")
        self.say("search for headphones for kids")
        self.assertEqual(self.opened[-1], "https://www.google.com/search?q=headphones+for+kids")

    def test_custom_sites(self):
        path = Path(self._tmp.name) / "sites.json"
        path.write_text('{"My Blog": "https://blog.example.com", "wiki": "https://wiki.example.com/s?q={q}", "bad": "javascript:alert(1)"}',
                        encoding="utf-8")
        custom = load_custom_sites(path)
        self.assertNotIn("bad", custom)
        self.make(custom_sites=custom)
        self.say("open my blog")
        self.assertEqual(self.opened[-1], "https://blog.example.com")
        self.assertEqual(search_url("wiki", "a b", custom), "https://wiki.example.com/s?q=a+b")
        self.assertEqual(load_custom_sites(Path(self._tmp.name) / "missing.json"), {})

    def test_spotify(self):
        self.say("play tum hi ho on spotify")
        self.assertEqual(self.launched[-1], "spotify:search:tum%20hi%20ho")
        self.assertEqual(self.opened[-1], "https://open.spotify.com/search/tum%20hi%20ho")  # app missing -> web
        self.opened.clear()
        self.launch_ok = True
        self.say("play tum hi ho on spotify")
        self.assertEqual(self.opened, [])

    def test_translate_news_maps(self):
        self.say("translate Good Morning to urdu")
        self.assertEqual(self.opened[-1], "https://translate.google.com/?sl=auto&tl=ur&text=Good+Morning&op=translate")
        self.say("how do you say thank you in french")
        self.assertIn("tl=fr&text=thank+you", self.opened[-1])
        self.assertIn("don't know the language klingon", self.say("translate hello to klingon"))
        self.say("latest news about cricket")
        self.assertEqual(self.opened[-1], "https://news.google.com/search?q=cricket")
        self.say("news")
        self.assertEqual(self.opened[-1], "https://news.google.com")
        self.say("navigate to Islamabad Airport")
        self.assertEqual(self.opened[-1], "https://www.google.com/maps/dir/?api=1&destination=Islamabad+Airport")
        self.say("find pharmacy near me")
        self.assertEqual(self.opened[-1], "https://www.google.com/maps/search/pharmacy+near+me")
        self.say("where is Lahore")
        self.assertEqual(self.opened[-1], "https://www.google.com/maps/search/Lahore")

    def test_folders(self):
        self.assertEqual(self.say("open downloads folder"), "I couldn't open your downloads folder on this computer.")
        self.assertEqual(self.launched[-1], str(Path("/home/me/Downloads")))
        self.launch_ok = True
        self.assertEqual(self.say("open my documents"), "Opening your documents folder.")


class CompoundCommandTests(FeatureTestCase):
    def test_split(self):
        self.assertEqual(split_compound("open youtube and open notepad"), ["open youtube", "open notepad"])
        self.assertEqual(split_compound("open youtube then search for cats"), ["open youtube", "search for cats"])
        self.assertEqual(split_compound("search for salt and pepper"), ["search for salt and pepper"])
        self.assertEqual(split_compound("send message to ali saying hi and open youtube"), ["send message to ali saying hi and open youtube"])
        self.assertEqual(split_compound("take a note buy milk and open the door"), ["take a note buy milk and open the door"])
        self.assertEqual(split_compound("remind me to call mom and send email"), ["remind me to call mom and send email"])

    def test_runs_each_part(self):
        reply = self.say("open youtube and open github")
        self.assertEqual(reply, "Opening youtube. Opening github.")
        self.assertEqual(self.opened, ["https://www.youtube.com", "https://github.com"])

    def test_stops_when_waiting_for_an_answer(self):
        self.say("shut down and open youtube")
        self.assertEqual(self.opened, [])  # asked "are you sure?" first, the rest is not run

    def test_exit_ends_the_sentence(self):
        reply = self.a.handle("open youtube and what time is it")
        self.assertEqual(reply.text, "Opening youtube. It's 3:00 PM.")
        self.assertFalse(reply.exit)


class RomanUrduTests(FeatureTestCase):
    def test_rewrites(self):
        cases = {
            "youtube kholo": "open youtube", "notepad khol do": "open notepad", "chrome chalao": "open chrome",
            "ali ko hello bhejo": "send whatsapp message to ali saying hello",
            "ali ko whatsapp pe kaise ho bhejo": "send whatsapp message to ali saying kaise ho",
            "ali ko message bhejo ke main late hoon": "send whatsapp message to ali saying main late hoon",
            "whatsapp kholo aur ali ko hi bhejo": "send whatsapp message to ali saying hi",
            "youtube kholo aur google kholo": "open youtube and open google",
            "python tutorial search karo": "search for python tutorial",
            "youtube par lofi search karo": "search lofi on youtube",
            "tum hi ho bajao": "play tum hi ho",
            "notepad band karo": "close notepad",
            "time kya hai": "what time is it", "kitne baje hain": "what time is it",
            "mausam kaisa hai": "weather", "karachi ka mausam": "weather in karachi",
            "awaaz barhao": "volume up", "awaz kam karo": "volume down", "awaaz band karo": "mute",
            "computer band karo": "shut down", "screen lock karo": "lock the computer",
            "yaad rakho doodh lana hai": "take a note doodh lana hai",
            "5 minute ka timer lagao": "set a timer for 5 minutes", "2 ghante ka timer lagao": "set a timer for 2 hours",
            "ek mazaaq sunao": "tell me a joke", "khuda hafiz": "exit",
        }
        for roman, english in cases.items():
            self.assertEqual(to_english(roman), english, roman)

    def test_english_is_left_alone(self):
        for text in ["open youtube", "send message to ali saying bring tea aur biscuits", "what time is it"]:
            self.assertEqual(to_english(text), text)

    def test_end_to_end(self):
        self.contacts.add("ali", phone="923001234567")
        self.assertEqual(self.say("youtube kholo"), "Opening youtube.")
        self.assertEqual(self.say("Ali ko Hello Bhai bhejo"), "Send 'Hello Bhai' to Ali on WhatsApp? Say yes to confirm.")
        self.assertEqual(self.say("haan"), "Sending your message to Ali on WhatsApp. Please don't switch windows for a few seconds.")
        self.assertIn("timer set for 5 minutes", self.say("5 minute ka timer lagao"))
        self.assertTrue(self.a.handle("khuda hafiz").exit)


class ConversionTests(FeatureTestCase):
    def test_parse(self):
        self.assertEqual(parse_conversion("convert 10 km to miles"), (10.0, "km", "miles"))
        self.assertEqual(parse_conversion("how many miles in 10 km"), (10.0, "km", "miles"))
        self.assertEqual(parse_conversion("what is ten km in miles"), (10.0, "km", "miles"))
        self.assertIsNone(parse_conversion("what is 12 times 7"))
        self.assertIsNone(parse_conversion("2 to the power of 8"))

    def test_units(self):
        self.assertAlmostEqual(convert_units(10, "km", "miles")[0], 6.2137, places=3)
        self.assertAlmostEqual(convert_units(1, "kg", "pounds")[0], 2.2046, places=3)
        self.assertAlmostEqual(convert_units(100, "celsius", "fahrenheit")[0], 212)
        self.assertAlmostEqual(convert_units(0, "celsius", "kelvin")[0], 273.15)
        self.assertEqual(convert_units(2, "gb", "mb")[0], 2048)
        self.assertIsNone(convert_units(1, "km", "kg"))      # different kinds of thing
        self.assertIsNone(convert_units(1, "km", "banana"))

    def test_spoken(self):
        self.assertEqual(self.say("convert 10 km to miles"), "10 km is 6.2137 miles.")
        self.assertEqual(self.say("how many cm in 2 inches"), "2 inches is 5.08 cm.")
        self.assertEqual(self.say("100 celsius to fahrenheit"), "100 degrees Celsius is 212 degrees Fahrenheit.")
        self.assertEqual(self.say("what is 12 times 7"), "The answer is 84.")

    def test_currency(self):
        self.assertEqual(self.say("convert 100 dollars to rupees"), "100 dollars is about 28,000.00 rupees.")
        self.say("100 euros to rupees")   # no rate available (offline): falls back to Google
        self.assertEqual(self.opened[-1], "https://www.google.com/search?q=100+EUR+to+PKR")
        self.assertIn("I couldn't get the live rate", self.a.handle("100 euros to rupees").text)

    def test_fetch_rate(self):
        class Response:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return self.body

        good = Response(b'{"result": "success", "rates": {"PKR": 281.5}}')
        self.assertEqual(fetch_rate("USD", "PKR", fetch=lambda *a, **k: good), 281.5)
        self.assertIsNone(fetch_rate("USD", "PKR", fetch=lambda *a, **k: Response(b'{"result": "error"}')))

        def offline(*a, **k):
            raise OSError("no internet")
        self.assertIsNone(fetch_rate("USD", "PKR", fetch=offline))


class AlarmTests(FeatureTestCase):
    def test_clock_parsing(self):
        self.assertEqual(parse_clock_time("5:30 pm", NOW)[0], 9000)         # 15:00 -> 17:30
        self.assertEqual(parse_clock_time("7 am", NOW)[0], 16 * 3600)       # tomorrow morning
        self.assertEqual(parse_clock_time("17:45", NOW)[0], 9900)
        self.assertEqual(parse_clock_time("3 pm", NOW)[0], 24 * 3600)       # it is 3 pm now -> tomorrow
        self.assertEqual(parse_clock_time("twelve am", NOW)[0], 9 * 3600)
        for bad in ["5", "13 pm", "25:00", "soon"]:
            self.assertIsNone(parse_clock_time(bad, NOW), bad)

    def test_alarm_and_clock_reminder(self):
        self.assertEqual(self.say("set an alarm for 7 am"), "Okay, alarm set for 7:00 AM.")
        self.assertEqual(self.scheduled[-1][0], 16 * 3600)
        self.scheduled[-1][1]()
        self.assertEqual(self.a.pop_alerts(), ["Alarm! It's 7:00 AM."])
        self.assertEqual(self.say("remind me at 5 pm to Call Mom"), "Okay, I'll remind you at 5:00 PM: Call Mom.")
        self.assertEqual(self.say("remind me to drink water at 6:30 pm"), "Okay, I'll remind you at 6:30 PM: drink water.")
        self.assertIn("timer set for 5 minutes", self.say("set a timer for 5 minutes"))   # old behaviour unchanged
        self.assertIn("How long", self.say("set a timer for soon"))


class PcControlTests(FeatureTestCase):
    def test_spoken_commands_reach_the_controllers(self):
        self.say("brightness up")
        self.say("dim the screen")
        self.say("set brightness to fifty")
        self.assertEqual(self.brightness_calls, [("up", None), ("down", None), ("set", 50)])
        self.assertIn("between 0 and 100", self.say("brightness 150"))
        self.assertEqual(self.say("close notepad"), "Closing notepad.")
        self.assertEqual(self.say("close tab"), "Closing the tab.")           # keyboard shortcut still wins
        self.assertIn("Sorry, I don't know", self.say("close unknownapp"))
        self.assertEqual(self.say("how much battery is left"), "status of battery")
        self.assertEqual(self.say("what is my ip address"), "status of ip")
        self.assertEqual(self.say("disk space"), "status of disk")
        self.assertEqual(self.say("am I online"), "status of internet")
        self.assertEqual(self.say("how much memory is free"), "status of memory")
        self.assertEqual(self.say("cpu usage"), "status of cpu")

    def test_sleep_needs_a_clear_request_and_signout_asks_first(self):
        calls = []
        self.make(power_controller=lambda action: calls.append(action) or True)
        self.say("sleep")
        self.assertEqual(calls, [])
        self.assertEqual(self.say("put the computer to sleep"), "Putting the computer to sleep.")
        self.assertIn("sign out", self.say("sign out"))
        self.assertEqual(calls, ["sleep"])
        self.assertEqual(self.say("yes"), "Signing out.")
        self.assertEqual(calls, ["sleep", "logoff"])

    def test_typing_and_saying(self):
        self.assertEqual(self.say("type Hello World"), "Typed.")
        self.assertEqual(self.typed, ["Hello World"])
        self.assertEqual(self.say("say Hello There"), "Hello There")

    def test_status_text_when_unavailable(self):
        self.make(status_reader=lambda kind: None)
        self.assertIn("can't read that", self.say("battery"))

    def test_brightness_failure_message(self):
        self.make(brightness_controller=lambda *a: False)
        self.assertIn("laptop screens", self.say("brightness up"))


class LowLevelTests(unittest.TestCase):
    def test_brightness_sets_an_int_and_clamps(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="95\n")

        self.assertTrue(system.brightness("up", run=run))
        self.assertIn("WmiSetBrightness(1,100)", calls[-1][-1])          # 95 + 10, clamped to 100
        self.assertTrue(system.brightness("set", 40, run=run))
        self.assertIn("WmiSetBrightness(1,40)", calls[-1][-1])
        self.assertTrue(system.brightness("set", -5, run=run))
        self.assertIn("WmiSetBrightness(1,0)", calls[-1][-1])
        self.assertFalse(system.brightness("sideways", run=run))

        def broken(command, **kwargs):
            raise subprocess.CalledProcessError(1, command)
        self.assertFalse(system.brightness("up", run=broken))
        with mock.patch.object(system, "is_windows", return_value=False):
            self.assertFalse(system.brightness("up"))

    def test_sleep_and_logoff_commands(self):
        for action, expected in {"sleep": "SetSuspendState", "logoff": "/l"}.items():
            calls = []
            self.assertTrue(system.power(action, run=lambda cmd, check: calls.append(cmd)))
            self.assertIn(expected, " ".join(calls[0]))

    def test_close_app_only_known_programs(self):
        calls = []
        self.assertTrue(apps.close_app("Note Pad", run=lambda cmd, **k: calls.append(cmd)))
        self.assertEqual(calls[-1], ["taskkill", "/IM", "notepad.exe"])      # no /F: the app is asked to close nicely
        self.assertIsNone(apps.close_app("calc.exe & del *", run=lambda *a, **k: calls.append(a)))
        self.assertEqual(len(calls), 1)

        def not_running(cmd, **kwargs):
            raise subprocess.CalledProcessError(128, cmd)
        self.assertFalse(apps.close_app("notepad", run=not_running))

    def test_type_text_sends_utf16_units(self):
        sent = []
        self.assertTrue(keys.type_text("Hi", send=lambda units: sent.append(units) or True))
        self.assertEqual(sent[0], [ord("H"), ord("i")])
        keys.type_text("😀", send=lambda units: sent.append(units) or True)
        self.assertEqual(sent[1], [0xD83D, 0xDE00])                          # surrogate pair
        self.assertFalse(keys.type_text("", send=lambda u: True))
        self.assertFalse(keys.type_text("x" * 501, send=lambda u: True))
        with mock.patch("platform.system", return_value="Linux"):
            self.assertFalse(keys.type_text("hello"))

    def test_sysinfo_sentences(self):
        with mock.patch.object(sysinfo, "battery", return_value=(80, True)):
            self.assertEqual(sysinfo.status("battery"), "The battery is at 80 percent and charging.")
        with mock.patch.object(sysinfo, "battery", return_value=None):
            self.assertIsNone(sysinfo.status("battery"))
        with mock.patch.object(sysinfo, "memory", return_value=(60, 16.0, 6.4)):
            self.assertEqual(sysinfo.status("memory"), "Memory is 60 percent used. 6.4 of 16.0 gigabytes are free.")
        with mock.patch.object(sysinfo, "disk", return_value=(120.4, 476.9)):
            self.assertEqual(sysinfo.status("disk"), "You have 120 gigabytes free on a 477 gigabyte drive.")
        with mock.patch.object(sysinfo, "local_ip", return_value="192.168.1.5"):
            self.assertEqual(sysinfo.status("ip"), "Your local IP address is 192.168.1.5.")
        with mock.patch.object(sysinfo, "online", return_value=False):
            self.assertIn("can't reach", sysinfo.status("internet"))
        self.assertIsNone(sysinfo.status("nonsense"))

    def test_windows_only_readers_return_none_elsewhere(self):
        with mock.patch.object(sysinfo, "is_windows", return_value=False):
            self.assertIsNone(sysinfo.battery())
            self.assertIsNone(sysinfo.memory())
            self.assertIsNone(sysinfo.cpu_percent())


if __name__ == "__main__":
    unittest.main()
