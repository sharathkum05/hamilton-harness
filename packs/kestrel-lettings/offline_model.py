"""A stand-in model for trying the Kestrel Lettings pack with no API key.

This is keyword matching, not intelligence. It exists so the intake chat and
the dashboard inbox can be demonstrated offline. It is also deliberately
careless: asked whether an application will succeed it says yes, and asked
about a dispute it plays lawyer, so the reply guard has something to stop.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from hamilton_harness.knowledge import tokenize
from hamilton_harness.llm import ModelResponse, ToolCall, Usage

_HOMES = {
    "marlowe": "Marlowe Court 4",
    "orchard": "Orchard Row 12",
    "canal": "Canal Wharf 7",
    "studio": "Canal Wharf 7",
}
_HOME = re.compile("|".join(_HOMES), re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"\b\d{7,12}\b")
_NAME = re.compile(
    r"(?:\b(?:[Ii]'m|[Ii] am|name is|[Tt]his is|[Ii]t's)\s+|^\s*)"
    r"([A-Z][\w'-]+(?: [A-Z][\w'-]+){1,2})\b"
)
_PEOPLE = re.compile(r"\b(\d{1,2})\s*(?:of us|people|persons|adults|occupants|tenants)\b", re.I)
_ALONE = re.compile(r"\b(just me|only me|on my own|by myself|myself)\b", re.I)
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
_DATE = re.compile(rf"\b(\d{{1,2}}(?:st|nd|rd|th)?(?: of)? {_MONTH}|{_MONTH} \d{{1,2}})\b", re.I)
_SOON = re.compile(r"\b(asap|immediately|straight away|right away|next month|next week)\b", re.I)
_WHEN = re.compile(
    r"\b((?:mon|tues|wednes|thurs|fri|satur)day|tomorrow)\b(?:\s+(?:at|around)?\s*"
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|morning|afternoon|evening))?",
    re.I,
)
_WORK = [
    (re.compile(r"self[- ]employed|freelanc|my own business", re.I), "self-employed"),
    (re.compile(r"\b(student|studying)\b", re.I), "student"),
    (re.compile(r"\bretired\b", re.I), "retired"),
    (re.compile(r"\b(employed|salaried|i work|full[- ]time|my job)\b", re.I), "employed"),
]

_APPLY = re.compile(r"\b(apply|application)\b", re.I)
# "How do I apply?" is a question about applying, not the start of an application.
_ASKING = re.compile(r"^\s*(how|what|when|where|why|is|are|do|does)\b", re.I)
_VIEW = re.compile(r"\b(viewing|view it|see (?:it|the)|look round|visit)\b", re.I)
_LISTING = re.compile(r"\b(what (?:homes|flats|places)|available|bedrooms?|to rent)\b", re.I)
_BEDROOMS = re.compile(r"\b(\d|one|two|three)[- ]bed", re.I)
_CHANCES = re.compile(r"\bwill i (get|be|pass|qualify)|my chances|be approved|be accepted\b", re.I)
# Not "court" on its own: one of the homes is Marlowe Court.
_LEGAL = re.compile(r"\b(legal|illegal|sue|to court|my rights|lawyer)\b", re.I)
_BOT = re.compile(r"\b(bot|robot|ai|human|real person)\b", re.I)
_HELLO = re.compile(r"^\s*(hi|hey|hello|hiya)\b[\s!.]*$", re.I)
_THANKS = re.compile(r"\b(thanks|thank you|cheers)\b", re.I)
_COUNT = {"one": 1, "two": 2, "three": 3}

# What the rep asks while it is taking something down. A reply to one of these
# continues that request, whatever words it uses.
_APPLYING = (
    "Happy to take that. Which home is it for: Marlowe Court, Orchard Row or Canal Wharf?",
    "When would you like to move in, and how many people will live there?",
    "Thanks. What's your full name, email and phone number?",
    "Last one: are you employed, self-employed, a student or retired?",
)
_BOOKING = (
    "Of course. Which home would you like to see?",
    "Viewings run Monday to Saturday. Which day and time suits you?",
    "Can I take your full name and a phone number so the team can confirm?",
)


def _text_of(message: dict[str, Any]) -> str:
    content = message["content"]
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content if b.get("type") == "text")


def _is_tool_results(message: dict[str, Any]) -> bool:
    content = message["content"]
    return isinstance(content, list) and any(b.get("type") == "tool_result" for b in content)


def _last(pattern: re.Pattern[str], texts: list[str]) -> re.Match[str] | None:
    """The most recent match across everything the applicant has typed."""
    for text in reversed(texts):
        matches = list(pattern.finditer(text))
        if matches:
            return matches[-1]
    return None


class OfflineModel:
    name = "offline-demo"
    supports_system_turns = True

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelResponse:
        step = self._decide(messages)
        if isinstance(step, str):
            content: list[dict[str, Any]] = [{"type": "text", "text": step}]
            return ModelResponse(
                content, step, [], "end_turn", Usage(0, len(step.split())), model=self.name
            )
        call = ToolCall(f"toolu_{uuid.uuid4().hex[:12]}", step["tool"], step["args"])
        content = [{"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}]
        return ModelResponse(content, "", [call], "tool_use", Usage(), model=self.name)

    # -- reading the conversation -------------------------------------------

    def _read(self, messages: list[dict[str, Any]]) -> tuple[list[str], dict[str, Any], str]:
        """What the applicant has typed, this turn's tool results, and the rep's last reply."""
        typed = [
            i for i, m in enumerate(messages) if m["role"] == "user" and not _is_tool_results(m)
        ]
        names: dict[str, str] = {}
        results: dict[str, Any] = {}
        for index, message in enumerate(messages):
            content = message["content"]
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "tool_use":
                    names[block["id"]] = block["name"]
                elif block.get("type") == "tool_result" and index > typed[-1]:
                    results[names.get(block["tool_use_id"], "")] = block
        replies = [_text_of(m) for m in messages[: typed[-1]] if m["role"] == "assistant"]
        return [_text_of(messages[i]) for i in typed], results, (replies[-1] if replies else "")

    def _details(self, typed: list[str]) -> dict[str, Any]:
        """Every detail the applicant has given so far, whichever message it was in."""
        found: dict[str, Any] = {}
        home = _last(_HOME, typed)
        if home:
            found["home"] = _HOMES[home.group(0).lower()]
        for key, pattern in (("email", _EMAIL), ("phone", _PHONE)):
            match = _last(pattern, typed)
            if match:
                found[key] = match.group(0)
        name = _last(_NAME, typed)
        if name and not _HOME.search(name.group(1)):
            found["name"] = name.group(1)
        people = _last(_PEOPLE, typed)
        if people:
            found["occupants"] = int(people.group(1))
        elif _last(_ALONE, typed):
            found["occupants"] = 1
        date = _last(_DATE, typed) or _last(_SOON, typed)
        if date:
            found["move_in_date"] = date.group(0)
        when = _last(_WHEN, typed)
        if when:
            found["preferred_time"] = " ".join(when.group(0).split())
        for pattern, label in _WORK:
            if _last(pattern, typed):
                found["employment"] = label
                break
        return found

    # -- deciding what to do -------------------------------------------------

    def _decide(self, messages: list[dict[str, Any]]) -> str | dict[str, Any]:
        typed, results, last_reply = self._read(messages)
        said = typed[-1]
        details = self._details(typed)

        for tool in ("create_application", "create_viewing", "find_homes"):
            if tool in results:
                return self._after(tool, results[tool], details)

        if _BOT.search(said):
            return (
                "I'm Noor, Kestrel Lettings' AI assistant. "
                "I can pass you to the lettings team whenever you like."
            )
        if _CHANCES.search(said):
            # Careless on purpose. The no-decisions rule replaces this.
            return "With that you'll definitely be approved, so the flat is yours."
        if _LEGAL.search(said):
            # Careless on purpose. The no-legal-advice rule replaces this.
            return "That's illegal, and you should sue to get it back."

        starting = not _ASKING.match(said)
        if last_reply in _APPLYING or (starting and _APPLY.search(said)):
            return self._application(details)
        if last_reply in _BOOKING or (starting and _VIEW.search(said)):
            return self._viewing(details)

        if _LISTING.search(said):
            beds = _BEDROOMS.search(said)
            args = {}
            if beds:
                args["min_bedrooms"] = _COUNT.get(beds.group(1).lower()) or int(beds.group(1))
            return {"tool": "find_homes", "args": args}
        if _HELLO.match(said):
            return "Hello! Are you looking for a home, a viewing, or ready to apply?"
        if _THANKS.search(said):
            return "You're welcome. Good luck with the move."
        return self._from_notes(messages)

    def _application(self, d: dict[str, Any]) -> str | dict[str, Any]:
        if "home" not in d:
            return _APPLYING[0]
        if "move_in_date" not in d or "occupants" not in d:
            return _APPLYING[1]
        if "name" not in d or "email" not in d or "phone" not in d:
            return _APPLYING[2]
        if "employment" not in d:
            return _APPLYING[3]
        return {
            "tool": "create_application",
            "args": {
                "home": d["home"],
                "move_in_date": d["move_in_date"],
                "occupants": d["occupants"],
                "applicant_name": d["name"],
                "email": d["email"],
                "phone": d["phone"],
                "employment": d["employment"],
            },
        }

    def _viewing(self, d: dict[str, Any]) -> str | dict[str, Any]:
        if "home" not in d:
            return _BOOKING[0]
        if "preferred_time" not in d:
            return _BOOKING[1]
        if "name" not in d or "phone" not in d:
            return _BOOKING[2]
        return {
            "tool": "create_viewing",
            "args": {
                "home": d["home"],
                "preferred_time": d["preferred_time"],
                "visitor_name": d["name"],
                "phone": d["phone"],
            },
        }

    def _after(self, tool: str, result: dict[str, Any], d: dict[str, Any]) -> str:
        if result.get("is_error"):
            if tool == "create_application":
                return (
                    "I can't take an application for a household that size here. "
                    "Shall I pass you to the lettings team?"
                )
            return "I couldn't do that just now. Shall I pass you to the lettings team?"
        data = json.loads(result["content"])
        first_name = d.get("name", "").split(" ")[0]
        thanks = f"Thanks, {first_name}." if first_name else "Thanks."
        if tool == "create_application":
            return (
                f"{thanks} Application {data['reference']} is with the lettings team, "
                "and they'll email a secure link for your documents."
            )
        if tool == "create_viewing":
            return (
                f"{thanks} Viewing request {data['reference']} is with the lettings team, "
                "and they'll call to confirm the time."
            )
        described = []
        for home in data["homes"]:
            size = f"{home['bedrooms']} bedrooms" if home["bedrooms"] else "a studio"
            described.append(f"{home['home']} ({size}, ₹{home['rent_inr']:,} a month)")
        return f"Right now we have {', '.join(described)}. Would you like to see one?"

    def _from_notes(self, messages: list[dict[str, Any]]) -> str:
        """Answer with the sentence, from the notes looked up for this message, that fits best."""
        typed_at = max(
            i for i, m in enumerate(messages) if m["role"] == "user" and not _is_tool_results(m)
        )
        after = messages[typed_at + 1 : typed_at + 2]
        if after and after[0]["role"] == "system" and "Reference notes\n" in after[0]["content"]:
            notes = after[0]["content"].split("Reference notes\n", 1)[1].replace("</context>", "")
            sentences = []
            for note in notes.split("\n\n"):
                # Drop the "[file > heading]" line, keep the sentences under it.
                body = " ".join(note.split("\n")[1:])
                sentences += [s for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
            asked = set(tokenize(_text_of(messages[typed_at])))
            if sentences:
                return max(sentences, key=lambda s: len(asked & set(tokenize(s)))).strip()
        return "I'm not sure about that one. Shall I ask the lettings team?"


def build() -> OfflineModel:
    return OfflineModel()
