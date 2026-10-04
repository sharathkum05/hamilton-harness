"""Decide when a human takes over.

These checks run in code on the customer's own words and on what the guard
has blocked, so a handoff never depends on the model choosing to give up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hamilton_harness.pack.schema import HandoffRules

_WANTS = r"(?:talk|speak|chat|connect|transfer|escalate|get|give|want|need|put)\w*"
_HUMAN = r"(?:human|person|manager|supervisor|representative|someone real|real agent|live agent)"
_ASKS_FOR_HUMAN = [
    # The lookahead skips possessives: "the manager's special" is a product, not a request.
    re.compile(rf"\b{_WANTS}\b.{{0,40}}\b{_HUMAN}\b(?!['’]s)", re.IGNORECASE),
    re.compile(r"\breal (?:person|human)\b", re.IGNORECASE),
    re.compile(r"\b(?:human|agent|manager) (?:please|pls|now)\b", re.IGNORECASE),
]
# "Are you a real person?" is a question about the rep, not a request for one.
_ASKS_IF_HUMAN = re.compile(
    r"\b(?:are|r) (?:you|u)\b.{0,20}\b(?:human|person|bot|ai|robot|real)\b"
    r"|\b(?:am i|is this)\b.{0,30}\b(?:human|person|bot|ai|robot)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HandoffDecision:
    reason: str  # "phrase", "requested", "guard" or "error"
    detail: str
    message: str


class HandoffDetector:
    def __init__(self, rules: HandoffRules) -> None:
        self._rules = rules
        self._phrases = [
            (phrase, re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE))
            for phrase in rules.phrases
        ]

    def _decide(self, reason: str, detail: str) -> HandoffDecision:
        return HandoffDecision(reason, detail, self._rules.message)

    def check_message(self, text: str) -> HandoffDecision | None:
        """Look at what the customer wrote, before the model sees it."""
        for phrase, pattern in self._phrases:
            if pattern.search(text):
                return self._decide("phrase", phrase)
        if self._rules.on_request and not _ASKS_IF_HUMAN.search(text):
            for pattern in _ASKS_FOR_HUMAN:
                match = pattern.search(text)
                if match:
                    return self._decide("requested", match.group(0))
        return None

    def check_guard_blocks(self, blocks: int) -> HandoffDecision | None:
        if blocks >= self._rules.max_guard_blocks:
            return self._decide("guard", f"{blocks} blocked actions")
        return None

    def for_violation(self, rule_ids: list[str]) -> HandoffDecision:
        return self._decide("guard", ", ".join(rule_ids))

    def for_error(self, detail: str) -> HandoffDecision:
        return self._decide("error", detail)
