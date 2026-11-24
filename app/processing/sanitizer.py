"""Text sanitization and adversarial injection defense for incoming threat posts."""

from __future__ import annotations

import re
from typing import Dict, Set


ZERO_WIDTH_CHARS: Set[str] = {
    "\u200b",  # Zero-width space
    "\u200c",  # Zero-width non-joiner
    "\u200d",  # Zero-width joiner
    "\ufeff",  # Zero-width no-break space (BOM)
    "\u2060",  # Word joiner
    "\u00ad",  # Soft hyphen
    "\u200e",  # Left-to-right mark
    "\u200f",  # Right-to-left mark
}

INVISIBLE_CHARS: Set[str] = {
    "\u034f",  # Combining Grapheme Joiner
    "\u180e",  # Mongolian Vowel Separator
    "\u061c",  # Arabic Letter Mark
    "\u17b4",  # Khmer Vowel Inherent Aq
    "\u17b5",  # Khmer Vowel Inherent Aa
    "\u115f",  # Hangul Choseong Filler
    "\u1160",  # Hangul Jungseong Filler
    "\u3164",  # Hangul Filler
    "\uffa0",  # Halfwidth Hangul Filler
    *{chr(cp) for cp in range(0xFE00, 0xFE10)},  # Variation Selectors
}

LATIN_TO_CYRILLIC_HOMOGLYPHS: Dict[str, str] = {
    "a": "а", "A": "А",
    "b": "б", "B": "В",
    "c": "с", "C": "С",
    "e": "е", "E": "Е",
    "h": "һ", "H": "Н",
    "i": "і", "I": "І",
    "k": "к", "K": "К",
    "m": "м", "M": "М",
    "o": "о", "O": "О",
    "p": "р", "P": "Р",
    "s": "ѕ", "S": "Ѕ",
    "t": "т", "T": "Т",
    "x": "х", "X": "Х",
    "y": "у", "Y": "У",
}

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"override\s+risk", re.IGNORECASE),
    re.compile(r"bypass\s+mode", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"drop\s+table", re.IGNORECASE),
]


class TextSanitizer:
    """Sanitizes incoming threat posts against poisoning, zero-width chars, and injection."""

    def strip_zero_width_chars(self, text: str) -> str:
        """Strip all zero-width and invisible unicode characters."""
        if not text:
            return ""
        all_invisible = ZERO_WIDTH_CHARS.union(INVISIBLE_CHARS)
        return "".join(ch for ch in text if ch not in all_invisible)

    def normalize_homoglyphs(self, text: str) -> str:
        """Normalize mixed-script homoglyphs to consistent Cyrillic characters."""
        if not text:
            return ""
        has_cyrillic = bool(re.search(r"[\u0400-\u04FF]", text))
        if has_cyrillic:
            chars = [LATIN_TO_CYRILLIC_HOMOGLYPHS.get(ch, ch) for ch in text]
            return "".join(chars)
        return text

    def neutralize_prompt_injection(self, text: str) -> str:
        """Strip prompt injection attempts and SQL fragments."""
        cleaned = text
        for pattern in PROMPT_INJECTION_PATTERNS:
            cleaned = pattern.sub("", cleaned)
        return cleaned.strip()

    def strip_control_chars(self, text: str) -> str:
        """Strip ASCII and Unicode control characters while preserving newlines and Ukrainian apostrophes."""
        if not text:
            return ""
        out = []
        for ch in text:
            cp = ord(ch)
            if cp in (10, 13, 9):  # \n, \r, \t
                out.append(ch)
            elif (cp < 32) or (127 <= cp <= 159):
                continue
            else:
                out.append(ch)
        return "".join(out)

    def sanitize(self, text: str) -> str:
        """Full sanitization pipeline."""
        if not text:
            return ""
        t = self.strip_zero_width_chars(text)
        t = self.strip_control_chars(t)
        t = self.normalize_homoglyphs(t)
        t = self.neutralize_prompt_injection(t)
        return t.strip()


# Backward-compatible alias matching project spec
class SignalPoisoningGuard(TextSanitizer):
    """Signal poisoning guard implementing the TextSanitizer interface."""
    pass
