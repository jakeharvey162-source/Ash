from __future__ import annotations
import difflib, json, os, pathlib, re, time
from dataclasses import dataclass

@dataclass(frozen=True)
class WakeMatch:
    start: int
    end: int
    phrase: str

class WakeMatcher:
    def __init__(self, wake_word: str | None = None, fuzzy_threshold: float = 0.78) -> None:
        self._explicit_wake_word = wake_word is not None
        self.wake_word = (wake_word or os.environ.get("ASH_WAKE_WORD", "Ash")).strip()
        aliases = os.environ.get("ASH_WAKE_ALIASES", "hey ash,okay ash,ok ash,arise")
        self.aliases = [self.wake_word] + [x.strip() for x in aliases.split(",") if x.strip()]
        self.fuzzy_threshold = fuzzy_threshold
        self.preferences_path = pathlib.Path(
            os.environ.get("ASH_PREFERENCES_FILE", str(pathlib.Path.home() / ".ash" / "preferences.json"))
        ).expanduser()
        self._preferences_mtime = -1.0
        self._last_preferences_check = 0.0

    def _refresh_preferences(self) -> None:
        if self._explicit_wake_word:
            return
        now = time.monotonic()
        if now - self._last_preferences_check < 0.75:
            return
        self._last_preferences_check = now
        try:
            stat = self.preferences_path.stat()
            if stat.st_mtime == self._preferences_mtime:
                return
            data = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            wake = str(data.get("wake_word") or data.get("assistant_name") or "Ash").strip() or "Ash"
            aliases = [str(x).strip() for x in (data.get("wake_aliases") or []) if str(x).strip()]
            self.wake_word = wake
            self.aliases = [wake, f"hey {wake}", f"okay {wake}", f"ok {wake}", "arise", *aliases]
            self._preferences_mtime = stat.st_mtime
        except Exception:
            return

    def find(self, text: str) -> WakeMatch | None:
        self._refresh_preferences()
        for phrase in sorted(set(self.aliases), key=len, reverse=True):
            pattern = r"(?<![A-Za-z0-9_])" + re.escape(phrase) + r"(?![A-Za-z0-9_])"
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                return WakeMatch(m.start(), m.end(), m.group())
        if " " in self.wake_word or len(self.wake_word) < 4:
            return None
        for m in re.finditer(r"[a-zA-Z']+", text):
            word = m.group()
            if len(word) < 4:
                continue
            if difflib.SequenceMatcher(None, word.lower(), self.wake_word.lower()).ratio() >= self.fuzzy_threshold:
                return WakeMatch(m.start(), m.end(), word)
        return None

    @staticmethod
    def command_after(text: str, match: WakeMatch) -> str:
        return text[match.end:].strip(" ,.!?;:-")

    def extract(self, text: str) -> str | None:
        match = self.find(text)
        return None if not match else self.command_after(text, match)
