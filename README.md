# Voice Controlled Assistant

A Python desktop assistant you can **talk to or type to**. It opens apps and 70+ websites, sends WhatsApp messages and emails, searches the web or a single site, converts units and currencies, sets alarms, controls your PC, does maths, takes notes and more. The command engine is separate from the microphone code, so the logic is fully unit-tested and the assistant also runs in plain **text mode** with no extra packages.

## Features

**Messaging**
- **WhatsApp by voice** – "send a message to Ali saying I'll be late", "open whatsapp and send message to Ali hello", "message 0300 1234567 call me". It opens the chat with your message typed in, then presses Enter for you. It asks "are you sure?" first (turn that off with `--no-confirm`), and if you only say "message Ali" it asks what to say.
- **Contact book** – "add contact Ali 0300 1234567", "add contact Sara email sara at gmail dot com", "list contacts", "what is the number of Ali", "delete contact Ali". Saved in `contacts.json`.
- **Email** – "send an email to Sara about the project report", "email Sara saying please call me". Opens a Gmail compose window; you check it and press send.

**Web**
- **70+ websites** – "open claude", "open chatgpt", "open google drive", "open daraz", "open youtube, google and github" (add your own in `sites.json`).
- **Search a single site** – "search amazon for usb cable", "search python tutorials on youtube", "open github and search for voice assistant", "find coffee shops on maps".
- **Maps** – "navigate to Islamabad airport", "find pharmacy near me", "where is Lahore".
- **Translate** – "translate good morning to urdu", "how do you say thank you in french".
- **News, YouTube, Spotify** – "latest news about cricket", "play lofi on youtube", "play tum hi ho on spotify".
- **Quick answers** – "who is Ada Lovelace" (Wikipedia), "weather in Karachi".

**Numbers**
- **Voice-friendly calculator** – "what is twelve times seven", "2 to the power of 10" (safe parser, no `eval`).
- **Unit conversion** – "convert 10 km to miles", "how many cm in 2 inches", "100 fahrenheit to celsius", "2 gb to mb".
- **Live currency** – "100 dollars to rupees", "50 euros to pounds" (needs internet).

**Time**
- **Timers, alarms and reminders** – "set a timer for 5 minutes", "set an alarm for 7 am", "remind me at 5 pm to call mom", "remind me in 10 minutes to drink water", "cancel my timers".
- **Notes** – "take a note buy milk", "read my notes", "delete note 1", "clear my notes".

**Your PC (Windows)**
- **Apps** – "open notepad", "open whatsapp" (or anything in `apps.json`), "close notepad" (asks the program to close, it never force-kills), "open downloads folder".
- **Volume and brightness** – "set volume to 50", "mute", "brightness up", "set brightness to 40" (brightness works on laptop screens).
- **Power** – "lock the computer", "put the computer to sleep", "sign out", "shut down", "restart". Sign out, shut down and restart ask "are you sure?"; shutdown waits 30 seconds so "cancel shutdown" works.
- **System info** – "how much battery is left", "memory usage", "cpu usage", "disk space", "what is my ip address", "am I online".
- **Keyboard shortcuts** – "refresh", "go back", "new tab", "close tab", "scroll down", "zoom in", "copy", "paste", "take a screenshot", "pause" and more.
- **Typing for you** – "type Hello World" types into the window in front.

**Everything else**
- **Several commands in one sentence** – "open youtube and open notepad", "open youtube then search for cats".
- **Roman Urdu** – "youtube kholo", "Ali ko hello bhejo", "whatsapp kholo aur Ali ko kaise ho bhejo", "awaaz barhao", "mausam kaisa hai", "5 minute ka timer lagao", "notepad band karo". In voice mode use `--language en-IN`, which usually writes Urdu/Hindi words in Latin letters.
- **Fun** – flip a coin, roll a dice, tell a joke, a quote.
- **Wake word** – optional `--wake-word jarvis` so it only reacts to "jarvis, ...". Answers like "yes" don't need it.
- **Voice or text mode** – if voice packages or a microphone are missing, you get a clear message instead of a crash.
- **136 automated tests** for the calculator, commands, messaging, contacts, sites, conversions, Roman Urdu and PC control.

## Getting Started

**Windows, no coding tools needed:** double-click `install.bat` once, then double-click `run.bat` whenever you want the assistant (right-click `run.bat` → Send to → Desktop to get a desktop shortcut). It listens for "Jarvis, ..." and falls back to text mode if there is no microphone.

**With a terminal:**

```bash
git clone https://github.com/shifafaheem05-lgtm/voice-assistant.git
cd voice-assistant

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
```

**Text mode** (no extra packages):

```bash
python -m assistant
```

**Voice mode** (needs a microphone and internet):

```bash
pip install -r requirements-voice.txt
python -m assistant --voice
python -m assistant --voice --wake-word jarvis
```

If `pip install PyAudio` fails on a very new Python version, use Python 3.11 or 3.12 for voice mode, or use text mode.

Run the tests with `python -m unittest discover -s tests -t .`

## WhatsApp setup

1. Save the people you message once: say or type `add contact Ali 0300 1234567`. Numbers starting with `0` get your country code (default `92`, Pakistan). For another country start the assistant with `--country-code 91` (or type the full number with `+`).
2. Say `send a message to Ali saying hello`, then `yes`.
3. The assistant opens the **WhatsApp desktop app** if it is installed (otherwise WhatsApp Web, where you must already be logged in), waits a few seconds for the chat to load and presses Enter. **Don't click another window during those seconds.**

If Enter is pressed too early or too late, change the wait: `--send-delay 10`. If you want to press Enter yourself, use `--no-auto-send`.

## Options

| Option | What it does |
|---|---|
| `--voice` | use the microphone and speak the answers |
| `--wake-word jarvis` | only react to commands that start with this word |
| `--language en-IN` | speech recognition language (try `en-IN` for Roman Urdu) |
| `--country-code 92` | country code added to phone numbers that start with 0 |
| `--no-confirm` | send WhatsApp messages without asking first |
| `--no-auto-send` | open the chat and type the message, but don't press Enter |
| `--send-delay 8` | seconds to wait for WhatsApp before pressing Enter |
| `--contacts-file`, `--sites-file`, `--apps-file`, `--notes-file` | where your data is saved |

## Add your own apps

Copy `apps.example.json` to `apps.json` and list the apps you want, for example `"my game": "C:\\Games\\game.exe"`. Then say "open my game".

## Add your own websites

Copy `sites.example.json` to `sites.json`: `"my blog": "https://example.com"`. A link containing `{q}` also works for searching: `"my wiki": "https://wiki.example.com/search?q={q}"` lets you say "search python on my wiki".

## Example session

```
Assistant: Hello! I'm ready. Say help to hear what I can do.
You: what is twelve times seven
Assistant: The answer is 84.
You: take a note buy groceries
Assistant: Okay, I saved your note: buy groceries.
You: search for python tutorials
Assistant: Searching the web for python tutorials.
You: send a message to ali saying I'll be late
Assistant: Send 'I'll be late' to Ali on WhatsApp? Say yes to confirm.
You: yes
Assistant: Sending your message to Ali on WhatsApp. Please don't switch windows for a few seconds.
You: convert 10 km to miles
Assistant: 10 km is 6.2137 miles.
```

## Project Structure

```
assistant/
├── engine.py    routes a sentence to the right command
├── calc.py      safe spoken-maths calculator
├── convert.py   unit and currency conversion
├── notes.py     JSON note storage
├── contacts.py  contact book (contacts.json)
├── messaging.py phone numbers, WhatsApp and email links, splitting "ali saying hello"
├── sites.py     70+ websites and site-specific searches
├── urdu.py      Roman-Urdu commands rewritten to English
├── sysinfo.py   battery, memory, cpu, disk, ip, internet
├── apps.py      opens and closes desktop apps by name (Windows), plus your own from apps.json
├── timers.py    timers and reminders
├── wiki.py      Wikipedia summaries
├── youtube.py   finds the first video for "play ..."
├── system.py    volume, brightness and power control (Windows)
├── keys.py      spoken keyboard shortcuts and typing (Windows)
├── speech.py    text and voice input/output back-ends
└── cli.py       main loop, wake word, command-line options
tests/             unit tests (test_assistant.py, test_features.py)
```

## Author

**Shifa Faheem** – [GitHub](https://github.com/shifafaheem05-lgtm) · [LinkedIn](https://www.linkedin.com/in/shifa-faheem-dev)

Released under the [MIT License](LICENSE).
