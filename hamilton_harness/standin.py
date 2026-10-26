"""A stand-in for the model, so any pack can be shown with no API key.

A pack may ship its own stand-in in `offline_model.py`, written to act out that
company's conversations. A pack without one gets this: it answers with the
sentence from the notes that best fits the question, says what it is when
asked, and otherwise says it is not sure. It never takes an action.

It is not a model. It exists so a demo, a screenshot or a first look at a new
pack does not need a key, and every check around it runs exactly as it would
around the real thing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from hamilton_harness.knowledge import tokenize
from hamilton_harness.llm import Model, ModelResponse, Usage, load_offline_model
from hamilton_harness.pack.schema import Pack

_BOT = re.compile(r"\b(bot|robot|ai|human|real person|a person)\b", re.I)
_HELLO = re.compile(r"^\s*(hi|hey|hello|hiya|good (morning|afternoon|evening))\b[\s!.]*$", re.I)
_THANKS = re.compile(r"\b(thanks|thank you|thx|cheers)\b", re.I)
_NOTES = "Reference notes\n"


def _text_of(message: dict[str, Any]) -> str:
    content = message["content"]
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content if b.get("type") == "text")


def best_sentence(notes: str, question: str) -> str:
    """The sentence in a rendered block of notes that shares the most words with the question.

    Returns an empty string when no sentence shares a word.
    """
    asked = set(tokenize(question))
    scored = []
    for note in notes.replace("</context>", "").split("\n\n"):
        # The first line of each note is its "[file > heading]" label. The heading
        # names the subject, so its words count towards every sentence under it.
        label, _, body = note.partition("\n")
        heading = set(tokenize(label.split(">", 1)[-1]))
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(body.split())):
            if sentence.strip():
                score = len(asked & (heading | set(tokenize(sentence))))
                scored.append((score, -len(scored), sentence.strip()))
    best = max(scored, default=(0, 0, ""))
    return best[2] if best[0] else ""


class NotesModel:
    """Answers from the notes the harness looked up. See the module docstring."""

    name = "notes-stand-in"
    supports_system_turns = True

    def __init__(self, pack: Pack) -> None:
        self._pack = pack

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelResponse:
        text = self._answer(messages)
        content = [{"type": "text", "text": text}]
        return ModelResponse(
            content, text, [], "end_turn", Usage(0, len(text.split())), model=self.name
        )

    def _answer(self, messages: list[dict[str, Any]]) -> str:
        typed_at = max(
            i
            for i, m in enumerate(messages)
            if m["role"] == "user" and not isinstance(m["content"], list)
        )
        said = _text_of(messages[typed_at])
        if _BOT.search(said):
            return self._pack.persona.disclosure
        if _HELLO.match(said):
            return "Hi! What can I help you with?"
        if _THANKS.search(said):
            return "You're welcome."
        for message in messages[typed_at + 1 :]:
            if message["role"] == "system" and _NOTES in message["content"]:
                found = best_sentence(message["content"].split(_NOTES, 1)[1], said)
                if found:
                    return found
        return self._pack.scope.unsure_reply


def offline_model(pack: Pack) -> Model:
    """The pack's own stand-in if it ships one, otherwise one that answers from its notes."""
    if pack.root and (Path(pack.root) / "offline_model.py").exists():
        return load_offline_model(pack.root)
    return NotesModel(pack)
