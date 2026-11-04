"""Contact book (JSON file) so you can say 'send a message to ali' instead of a phone number."""
from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ContactStore:
    """{"ali": {"phone": "923001234567", "email": "ali@example.com"}} - phone has country code, no plus."""

    def __init__(self, path="contacts.json", country_code: str = "92") -> None:
        self.path = Path(path)
        self.country_code = country_code

    def all(self) -> Dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}  # a corrupt file should not crash the assistant
        if not isinstance(data, dict):
            return {}
        return {str(k).lower(): v for k, v in data.items() if isinstance(v, dict)}

    def _save(self, data: Dict[str, dict]) -> None:
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def names(self) -> List[str]:
        return sorted(self.all())

    def add(self, name: str, phone: Optional[str] = None, email: Optional[str] = None) -> None:
        """Create the contact, or update the given fields of an existing one."""
        data = self.all()
        entry = data.get(name.strip().lower(), {})
        if phone:
            entry["phone"] = phone
        if email:
            entry["email"] = email
        data[name.strip().lower()] = entry
        self._save(data)

    def remove(self, name: str) -> Optional[str]:
        """Delete a contact. Returns its stored name, or None if nothing matched."""
        found = self.find(name)
        if not found:
            return None
        data = self.all()
        data.pop(found[0], None)
        self._save(data)
        return found[0]

    def find(self, name: str) -> Optional[Tuple[str, dict]]:
        """Best match for a spoken name: exact, then 'starts with', then a close spelling ('alley' -> 'ali')."""
        key = name.strip().lower()
        if not key:
            return None
        data = self.all()
        if key in data:
            return key, data[key]
        starts = [n for n in data if n.startswith(key) or key.startswith(n)]
        if len(starts) == 1:
            return starts[0], data[starts[0]]
        close = difflib.get_close_matches(key, list(data), n=1, cutoff=0.75)
        if close:
            return close[0], data[close[0]]
        return None
