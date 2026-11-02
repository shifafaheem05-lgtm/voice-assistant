# Voice Controlled Assistant

A Python desktop assistant you can **talk to or type to**. It tells the time, opens websites, searches the web, does maths, takes notes and more. The command engine is separate from the microphone code, so the logic is fully unit-tested and the assistant also runs in plain **text mode** with no extra packages.

## Features

- **Time and date** – "what time is it", "what's the date today".
- **Open websites and search** – "open youtube", "search for python tutorials", "play lofi music on youtube".
- **Voice-friendly calculator** – "what is twelve times seven", "2 to the power of 10". It parses expressions safely (no `eval`) and handles divide-by-zero and huge numbers.
- **Notes** – "take a note buy milk", "read my notes", "clear my notes" (saved in a local JSON file).
- **Fun** – flip a coin, roll a dice, tell a joke.
- **Wake word** – optional `--wake-word jarvis` so it only reacts to "jarvis, ...".
- **Voice or text mode** – if voice packages or a microphone are missing, you get a clear message instead of a crash.
- **25 automated tests** covering the calculator, commands, notes, wake word and the main loop.

## Getting Started

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

## Example session

```
Assistant: Hello! I'm ready. Say help to hear what I can do.
You: what is twelve times seven
Assistant: The answer is 84.
You: take a note buy groceries
Assistant: Okay, I saved your note: buy groceries.
You: search for python tutorials
Assistant: Searching the web for python tutorials.
```

## Project Structure

```
assistant/
├── engine.py    routes a sentence to the right command
├── calc.py      safe spoken-maths calculator
├── notes.py     JSON note storage
├── speech.py    text and voice input/output back-ends
└── cli.py       main loop, wake word, command-line options
tests/             unit tests
```

## Author

**Shifa Faheem** – [GitHub](https://github.com/shifafaheem05-lgtm) · [LinkedIn](https://www.linkedin.com/in/shifa-faheem-dev)

Released under the [MIT License](LICENSE).
