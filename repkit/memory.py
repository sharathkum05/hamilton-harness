"""What the rep remembers.

Two lifetimes: a Conversation holds one chat, and a CustomerStore keeps a few
facts about a customer between chats so they never have to repeat their name
or order number.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from repkit.handoff import HandoffDecision
from repkit.pack.schema import ToolSpec


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    customer_id: str | None = None
    # Sent to the model as is. Only ever appended to: rewriting earlier turns
    # breaks prompt caching and invalidates the model's saved reasoning.
    messages: list[dict[str, Any]] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)
    guard_blocks: int = 0
    turns: int = 0
    handoff: HandoffDecision | None = None
    # What the customer last saw from the rep.
    last_reply: str = ""

    @property
    def handed_off(self) -> bool:
        return self.handoff is not None


class CustomerStore(Protocol):
    def load(self, customer_id: str) -> dict[str, str]: ...

    def save(self, customer_id: str, facts: dict[str, str]) -> None: ...


class InMemoryStore:
    def __init__(self) -> None:
        self._facts: dict[str, dict[str, str]] = {}

    def load(self, customer_id: str) -> dict[str, str]:
        return dict(self._facts.get(customer_id, {}))

    def save(self, customer_id: str, facts: dict[str, str]) -> None:
        self._facts[customer_id] = dict(facts)


class FileStore:
    """One JSON file per customer. Fine for a demo; use a database in production."""

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)

    def _path(self, customer_id: str) -> Path:
        # Customer ids are often emails or phone numbers, which make poor file names.
        return self._dir / f"{hashlib.sha256(customer_id.encode()).hexdigest()[:24]}.json"

    def load(self, customer_id: str) -> dict[str, str]:
        path = self._path(customer_id)
        if not path.exists():
            return {}
        try:
            return dict(json.loads(path.read_text(encoding="utf-8")).get("facts", {}))
        except (json.JSONDecodeError, AttributeError):
            return {}

    def save(self, customer_id: str, facts: dict[str, str]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        record = {"facts": facts, "updated_at": datetime.now(UTC).isoformat(timespec="seconds")}
        self._path(customer_id).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def facts_from_result(spec: ToolSpec, data: Any) -> dict[str, str]:
    """Pick out the facts a tool's `remember` mapping asks for."""
    if not isinstance(data, dict):
        return {}
    return {
        fact: str(data[source])
        for fact, source in spec.remember.items()
        if data.get(source) not in (None, "")
    }
