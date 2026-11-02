"""Tiny JSON-backed note store."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List


class NoteStore:
    def __init__(self, path="notes.json") -> None:
        self.path = Path(path)

    def all(self) -> List[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []  # a corrupt file should not crash the assistant

    def add(self, text: str, when: datetime = None) -> None:
        notes = self.all()
        notes.append({"text": text.strip(), "time": (when or datetime.now()).isoformat(timespec="seconds")})
        self.path.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")

    def clear(self) -> int:
        count = len(self.all())
        if self.path.exists():
            self.path.unlink()
        return count
