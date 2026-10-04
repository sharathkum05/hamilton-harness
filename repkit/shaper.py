"""Make a draft read like a chat message from a person.

The model is asked to write short, plain replies, and mostly does. The shaper
is the part that does not rely on asking: it strips formatting a chat window
would show literally, removes stock phrases, splits the reply into chat-sized
bubbles and works out how long each would take to type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from repkit.pack.schema import Persona

_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9\"'(₹$€£])")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_HEADING = re.compile(r"^\s*#{1,6}\s+")
_EMPHASIS = re.compile(r"(\*\*|\*|`)(?=\S)(.+?)(?<=\S)\1")
# Underscores only count as emphasis around a whole word, so order_id survives.
_UNDERSCORE_EMPHASIS = re.compile(r"(?<!\w)(__|_)(?=\S)(.+?)(?<=\S)\1(?!\w)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_EMOJI = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f000-\U0001f2ff\U0000fe0f\U0000200d]+"
)
_DASH = re.compile(r"\s*[—–]\s*")
# Abbreviations whose full stop does not end a sentence.
_ABBREVIATIONS = ("Mr.", "Mrs.", "Ms.", "Dr.", "Rs.", "No.", "vs.", "e.g.", "i.e.", "approx.")


@dataclass(frozen=True)
class Bubble:
    text: str
    # Seconds to wait before showing it, as if it were being typed.
    delay: float


@dataclass
class Shaped:
    bubbles: list[Bubble]
    dropped: list[str] = field(default_factory=list)
    removed_phrases: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(b.text for b in self.bubbles)


def _strip_inline(text: str) -> str:
    text = _LINK.sub(r"\1", text)
    previous = None
    while previous != text:
        previous = text
        text = _UNDERSCORE_EMPHASIS.sub(r"\2", _EMPHASIS.sub(r"\2", text))
    return text


def strip_formatting(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = _strip_inline(_HEADING.sub("", _BULLET.sub("", line))).strip()
        if line:
            # A list item with no full stop still has to end somewhere.
            lines.append(f"{line}." if re.search(r"\w$", line) else line)
    flat = _DASH.sub(", ", " ".join(lines))
    return re.sub(r"\s+", " ", flat).strip()


def split_sentences(text: str) -> list[str]:
    protected = text
    for index, abbreviation in enumerate(_ABBREVIATIONS):
        protected = protected.replace(abbreviation, f"\x00{index}\x00")
    sentences = []
    for piece in _SENTENCE_END.split(protected):
        for index, abbreviation in enumerate(_ABBREVIATIONS):
            piece = piece.replace(f"\x00{index}\x00", abbreviation)
        if piece.strip():
            sentences.append(piece.strip())
    return sentences


def typing_delay(
    text: str, *, per_char: float = 0.03, low: float = 0.4, high: float = 2.5
) -> float:
    return round(min(high, max(low, len(text) * per_char)), 2)


class ReplyShaper:
    def __init__(self, persona: Persona, *, max_bubbles: int = 3) -> None:
        self._persona = persona
        self._max_bubbles = max_bubbles
        self._banned = [
            (phrase, re.compile(re.escape(phrase), re.IGNORECASE))
            for phrase in persona.banned_phrases
        ]

    def _remove_banned(self, sentences: list[str], removed: list[str]) -> list[str]:
        kept = []
        for sentence in sentences:
            hits = [phrase for phrase, pattern in self._banned if pattern.search(sentence)]
            if not hits:
                kept.append(sentence)
                continue
            removed.extend(hits)
            stripped = sentence
            for _, pattern in self._banned:
                stripped = pattern.sub("", stripped)
            stripped = re.sub(r"\s+", " ", stripped).strip(" ,;:-")
            # Keep what is left only if it still says something.
            if len(re.findall(r"\w+", stripped)) >= 3:
                kept.append(stripped[0].upper() + stripped[1:])
        return kept

    def shape(self, draft: str) -> Shaped:
        removed: list[str] = []
        text = strip_formatting(draft)
        if not self._persona.emoji:
            text = re.sub(r"\s+", " ", _EMOJI.sub("", text)).strip()
        sentences = self._remove_banned(split_sentences(text), removed)
        if not sentences:
            # Never send nothing: an empty reply reads as the rep walking away.
            sentences = split_sentences(text) or [draft.strip()]

        size = self._persona.max_sentences
        groups = [" ".join(sentences[i : i + size]) for i in range(0, len(sentences), size)]
        kept, dropped = groups[: self._max_bubbles], groups[self._max_bubbles :]
        return Shaped(
            bubbles=[Bubble(text, typing_delay(text)) for text in kept],
            dropped=dropped,
            removed_phrases=removed,
        )
