"""Orders, quotes and anything else the rep takes down for the business.

A pack lists its record types in records.yaml. Each one becomes an action the
rep can take (`create_order`, `create_quote`), validated and guarded like any
other action. What the rep takes down lands in a store the business reads from
its dashboard, each with a reference the customer is given.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from hamilton_harness.pack.schema import RecordType

Status = Literal["new", "confirmed", "done", "cancelled"]
STATUSES: tuple[Status, ...] = ("new", "confirmed", "done", "cancelled")


@dataclass
class Record:
    id: str
    type: str
    data: dict[str, Any]
    status: Status = "new"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    conversation_id: str = ""


class RecordStore(Protocol):
    def add(self, type_name: str, data: dict[str, Any], conversation_id: str = "") -> Record: ...

    def list(self, type_name: str | None = None) -> list[Record]: ...

    def set_status(self, record_id: str, status: Status) -> Record | None: ...


class MemoryRecordStore:
    def __init__(self) -> None:
        self._records: list[Record] = []
        self._lock = threading.Lock()

    def _load(self) -> list[Record]:
        return self._records

    def _save(self, records: list[Record]) -> None:
        self._records = records

    def add(self, type_name: str, data: dict[str, Any], conversation_id: str = "") -> Record:
        with self._lock:
            records = self._load()
            # ORD-0001, QUO-0001: short enough to read out, numbered per type.
            number = sum(1 for r in records if r.type == type_name) + 1
            record = Record(
                id=f"{type_name[:3].upper()}-{number:04d}",
                type=type_name,
                data=data,
                conversation_id=conversation_id,
            )
            self._save([*records, record])
            return record

    def list(self, type_name: str | None = None) -> list[Record]:
        with self._lock:
            records = self._load()
        chosen = [r for r in records if type_name is None or r.type == type_name]
        return sorted(chosen, key=lambda r: r.created_at, reverse=True)

    def set_status(self, record_id: str, status: Status) -> Record | None:
        with self._lock:
            records = self._load()
            for record in records:
                if record.id == record_id:
                    record.status = status
                    self._save(records)
                    return record
        return None


class FileRecordStore(MemoryRecordStore):
    """Records in one JSON file. Fine for a small business; use a database beyond that."""

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self._path = Path(path)

    def _load(self) -> list[Record]:
        if not self._path.exists():
            return []
        try:
            return [Record(**item) for item in json.loads(self._path.read_text(encoding="utf-8"))]
        except (json.JSONDecodeError, TypeError):
            return []

    def _save(self, records: list[Record]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2)
        self._path.write_text(payload, encoding="utf-8")


def input_schema(record_type: RecordType) -> dict[str, Any]:
    """The JSON schema of the action that takes down this kind of record."""
    properties: dict[str, Any] = {}
    for item in record_type.fields:
        if item.type == "number":
            schema: dict[str, Any] = {"type": "number"}
        elif item.type == "choice":
            schema = {"type": "string", "enum": item.choices}
        else:
            schema = {"type": "string", "minLength": 1}
        if item.description or item.label:
            schema["description"] = item.description or item.label
        properties[item.name] = schema
    return {
        "type": "object",
        "properties": properties,
        "required": [item.name for item in record_type.fields if item.required],
        "additionalProperties": False,
    }


def tool_description(record_type: RecordType) -> str:
    return (
        f"{' '.join(record_type.description.split())} Ask the customer for every required "
        "field first and never guess one. Returns a reference to give the customer."
    )
