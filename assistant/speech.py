"""Input/output back-ends: typed text (always works) and voice (optional extra packages)."""
from __future__ import annotations

from typing import Optional


class SpeechUnavailable(Exception):
    """Voice mode needs extra packages or a microphone that is not available."""


class TextIO:
    """Type your commands. Works everywhere, no extra packages."""

    def listen(self) -> Optional[str]:
        try:
            return input("You: ")
        except EOFError:
            return "exit"

    def speak(self, text: str) -> None:
        print(f"Assistant: {text}")


class VoiceIO:
    """Microphone input (Google Web Speech via SpeechRecognition) and spoken replies (pyttsx3).

    Needs:  pip install -r requirements-voice.txt   and an internet connection for recognition.
    """

    def __init__(self, language: str = "en-US") -> None:
        try:
            import speech_recognition as sr
            import pyttsx3
        except ImportError as exc:
            raise SpeechUnavailable(
                f"voice mode needs extra packages ({exc.name} is missing). "
                "Run: pip install -r requirements-voice.txt  - or use text mode (no --voice)."
            ) from None
        self._sr = sr
        self.language = language
        self.recognizer = sr.Recognizer()
        try:
            self.microphone = sr.Microphone()
        except (OSError, AttributeError) as exc:
            raise SpeechUnavailable(
                f"no usable microphone found ({exc}). Check it is connected, or use text mode."
            ) from None
        self.engine = pyttsx3.init()
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

    def listen(self) -> Optional[str]:
        sr = self._sr
        print("Listening...")
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=10)
            text = self.recognizer.recognize_google(audio, language=self.language)
            print(f"You said: {text}")
            return text
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return ""  # silence or unclear speech: just listen again
        except sr.RequestError as exc:
            raise SpeechUnavailable(f"speech recognition service unreachable: {exc}") from None

    def speak(self, text: str) -> None:
        print(f"Assistant: {text}")
        self.engine.say(text)
        self.engine.runAndWait()
