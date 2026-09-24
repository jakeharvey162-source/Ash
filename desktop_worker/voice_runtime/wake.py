from __future__ import annotations
import difflib, os, re
from dataclasses import dataclass

@dataclass(frozen=True)
class WakeMatch:
    start: int
    end: int
    phrase: str

class WakeMatcher:
    def __init__(self, wake_word: str | None = None, fuzzy_threshold: float = 0.78) -> None:
        self.wake_word = (wake_word or os.environ.get("ASH_WAKE_WORD", "Ash")).strip()
        aliases = os.environ.get("ASH_WAKE_ALIASES", "hey ash,okay ash,ok ash")
        self.aliases = [self.wake_word] + [x.strip() for x in aliases.split(",") if x.strip()]
        self.fuzzy_threshold = fuzzy_threshold

    def find(self, text: str) -> WakeMatch | None:
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
