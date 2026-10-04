"""Keep the rep on its own subject and stop it stating figures it was never given.

Two checks, both in code.

The scope gate runs before the model. A dental practice's rep has no business
solving equations or writing Python, so those requests are answered with the
pack's off-topic line and the model is never called.

The grounding check runs after the model. Any number in a reply (a price, a
date, a percentage, a number of days) must appear somewhere the rep could have
read it: a rule, a reference note, a tool result or the customer's own words.
A number from nowhere is an invented fact, and the reply is replaced.

Neither check proves a reply is true. They remove two common failures cheaply
and leave a trace when they fire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from hamilton_harness.context import TurnContext
from hamilton_harness.knowledge import tokenize
from hamilton_harness.pack.schema import ScopeSettings

_DETECTORS: dict[str, list[str]] = {
    "math": [
        r"\d\s*(?:[-+*/^×÷]|\bx\b|\btimes\b|\bplus\b|\bminus\b|\bdivided by\b)\s*\d",
        r"\b(?:solve|simplify|factori[sz]e|differentiate|integrate)\b",
        r"\b(?:equation|integral|derivative|square root|quadratic|algebra|calculus)\b",
        r"\bwhat(?:'s| is) \d+(?:\.\d+)? ?% of\b",
    ],
    "coding": [
        r"\b(?:write|give|show|make|create|generate|fix|debug)\b.{0,40}"
        r"\b(?:code|script|function|program|regex|sql query|algorithm)\b",
        r"\b(?:python|javascript|typescript|java|c\+\+|golang|rust|html|css)\b"
        r".{0,30}\b(?:code|script|function|program|snippet|error|bug)\b",
    ],
    "writing": [
        r"\b(?:write|compose|draft|give)\b.{0,30}"
        r"\b(?:poem|essay|story|song|lyrics|joke|speech|cover letter|haiku|rap|limerick)\b",
        r"\btell me (?:a|another) (?:joke|story)\b",
        r"\b(?:do|help with) my homework\b",
    ],
    "trivia": [
        r"\b(?:capital|president|prime minister|population|currency) of\b",
        r"\bwho (?:is|was|won|invented|discovered|wrote|painted)\b",
        r"\btranslate\b.{0,60}\b(?:to|into)\b",
        r"\b(?:meaning of life|weather (?:today|tomorrow)|stock price|bitcoin)\b",
    ],
}

# Messages that are part of any conversation, whatever the subject.
_CONVERSATIONAL = re.compile(
    r"^\W*(?:hi|hey|hello|hiya|yo|good (?:morning|afternoon|evening)|thanks|thank you|thx|"
    r"cheers|ok|okay|yes|yeah|yep|no|nope|nah|sure|please|pls|bye|goodbye|great|perfect|"
    r"cool|got it|sorry|help|hello there)\b[\w\s,'!.?]{0,24}$",
    re.IGNORECASE,
)
_ABOUT_THE_REP = re.compile(
    r"\b(?:are|r) (?:you|u)\b|\bwho (?:are|r) (?:you|u)\b|\bis this (?:a |an )?"
    r"(?:bot|ai|human|person|robot)\b|\bwhat can (?:you|u) (?:do|help)",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class ScopeVerdict:
    in_scope: bool
    # Which check refused: a detector name, "custom" or "strict".
    reason: str = ""
    matched: str = ""


IN_SCOPE = ScopeVerdict(True)


def _shared_words(message: str, context: TurnContext) -> tuple[int, int]:
    """How many of the message's words appear in the notes looked up for it, out of how many.

    Numbers are left out: "348 * 12" must not count as on topic because the
    size chart happens to mention a 12.
    """
    words = {word for word in tokenize(message) if word.isalpha()}
    known: set[str] = set()
    for chunk in context.notes:
        known.update(tokenize(f"{chunk.heading} {chunk.text}"))
    return len(words & known), len(words)


class ScopeGate:
    def __init__(self, settings: ScopeSettings) -> None:
        self._settings = settings
        self._detectors = [
            (kind, re.compile(pattern, re.IGNORECASE))
            for kind in settings.refuse
            for pattern in _DETECTORS[kind]
        ]
        self._custom = [re.compile(p, re.IGNORECASE) for p in settings.also_refuse]

    def check(self, message: str, context: TurnContext, *, answering: bool = False) -> ScopeVerdict:
        """Decide whether the rep should engage with this message at all.

        `context` is what the pack had to say about the message, and
        `answering` is true when the rep's last message was a question, so a
        short reply to it is not mistaken for a change of subject.
        """
        for pattern in self._custom:
            match = pattern.search(message)
            if match:
                return ScopeVerdict(False, "custom", match.group(0))

        shared, total = _shared_words(message, context)
        for kind, pattern in self._detectors:
            match = pattern.search(message)
            if not match:
                continue
            # "What's 2 x 2,499 for two pairs with shipping?" is sums about our own
            # prices. Everything else on the list is refused whatever it mentions.
            if kind == "math" and (context.rules or shared):
                continue
            return ScopeVerdict(False, kind, match.group(0))

        # One shared word is too weak for a longer message: "tell me about black holes"
        # would pass because a shoe comes in black.
        covered = bool(context.rules) or (total > 0 and shared >= min(2, total))
        if self._settings.strict and not covered:
            conversational = (
                answering or _CONVERSATIONAL.match(message) or _ABOUT_THE_REP.search(message)
            )
            if not conversational:
                return ScopeVerdict(False, "strict", "")
        return IN_SCOPE


def _numbers(text: str) -> set[str]:
    found = set()
    for raw in _NUMBER.findall(text):
        number = raw.replace(",", "").rstrip(".")
        if "." in number:
            number = number.rstrip("0").rstrip(".")
        found.add(number.lstrip("0") or "0")
    return found


def _flatten(content: Any) -> str:
    """All the text in a message's content, including tool arguments and results."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return " ".join(_flatten(value) for value in content.values())
    if isinstance(content, (list, tuple)):
        return " ".join(_flatten(item) for item in content)
    if isinstance(content, (int, float)) and not isinstance(content, bool):
        return str(content)
    for attribute in ("text", "content", "input"):
        if hasattr(content, attribute):
            return _flatten(getattr(content, attribute))
    return ""


def evidence_text(system_prompt: str, messages: list[dict[str, Any]]) -> str:
    """Everything the rep could have read: the prompt and the whole conversation."""
    return " ".join([system_prompt, *(_flatten(m.get("content")) for m in messages)])


def ungrounded_numbers(reply: str, evidence: str) -> list[str]:
    """Numbers the reply states that appear nowhere in the evidence."""
    return sorted(_numbers(reply) - _numbers(evidence))
