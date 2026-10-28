"""Record what happened in a turn, step by step.

A trace is the answer to "why did the rep say that?". Every customer message,
context block, model call, action, guard verdict and reply edit becomes one
event, and a conversation's events can be written out as JSON lines.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Protocol

# Conversation ids are 12 hex characters; anything else is never looked up.
CONVERSATION_ID = re.compile(r"[0-9a-f]{12}")


def jsonable(value: Any) -> Any:
    """Best-effort conversion of SDK objects and dataclasses to plain JSON."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    for method in ("to_dict", "model_dump"):
        if hasattr(value, method):
            return jsonable(getattr(value, method)())
    return str(value)


@dataclass(frozen=True)
class Event:
    at: float
    kind: str
    data: dict[str, Any]


@dataclass
class Trace:
    conversation_id: str
    turn: int = 0
    events: list[Event] = field(default_factory=list)

    def add(self, kind: str, **data: Any) -> None:
        self.events.append(Event(time.time(), kind, jsonable(data)))

    def kinds(self) -> list[str]:
        return [event.kind for event in self.events]

    def first(self, kind: str) -> Event | None:
        return next((event for event in self.events if event.kind == kind), None)


class TraceWriter:
    """Appends each turn's events to `<directory>/<conversation id>.jsonl`."""

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)

    def path(self, conversation_id: str) -> Path:
        return self._dir / f"{conversation_id}.jsonl"

    def write(self, trace: Trace) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        with self.path(trace.conversation_id).open("a", encoding="utf-8") as handle:
            for event in trace.events:
                record = {"turn": trace.turn, "at": event.at, "kind": event.kind, **event.data}
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_trace(path: str | Path) -> list[dict[str, Any]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def summarize(conversation_id: str, events: list[dict[str, Any]], updated_at: float) -> dict:
    """One conversation as the dashboard lists it: how it opened and what stood out."""
    first = next((e.get("text", "") for e in events if e["kind"] == "customer"), "")
    return {
        "id": conversation_id,
        "turns": max((e.get("turn", 0) for e in events), default=0),
        "updated_at": updated_at,
        "opening": first[:140],
        "handed_off": any(e["kind"] == "handoff" for e in events),
        "blocked": any(
            e["kind"] == "reply_blocked"
            or (e["kind"] == "action" and e.get("outcome") == "blocked")
            for e in events
        ),
        "refused": any(e["kind"] == "scope_refused" for e in events),
    }


class TraceStore(Protocol):
    """Where turns are recorded, and read back for the dashboard."""

    def write(self, trace: Trace) -> None: ...

    def conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Summaries of the most recently active conversations, newest first."""
        ...

    def events(self, conversation_id: str) -> list[dict[str, Any]] | None:
        """Every event of one conversation, or None if there is no such conversation."""
        ...


class FileTraceStore:
    """One JSON-lines file per conversation in a folder."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self._writer = TraceWriter(directory)

    def write(self, trace: Trace) -> None:
        self._writer.write(trace)

    def conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.directory.is_dir():
            return []
        files = sorted(
            self.directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        return [summarize(p.stem, read_trace(p), p.stat().st_mtime) for p in files[:limit]]

    def events(self, conversation_id: str) -> list[dict[str, Any]] | None:
        if not CONVERSATION_ID.fullmatch(conversation_id):
            return None
        path = self._writer.path(conversation_id)
        return read_trace(path) if path.is_file() else None
