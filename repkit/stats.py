"""Numbers for the dashboard's overview: what the rep has been doing lately."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from repkit.editor import list_conversations
from repkit.records import RecordStore


def _day(moment: datetime) -> str:
    return moment.astimezone(UTC).date().isoformat()


def overview(
    trace_dir: Path | None, records: RecordStore, *, days: int = 14, today: date | None = None
) -> dict[str, Any]:
    """Counts, a day-by-day timeline and the latest items, for the dashboard's first screen."""
    conversations = list_conversations(trace_dir, limit=500)
    taken = records.list()
    end = today or datetime.now(UTC).date()
    window = [(end - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]

    chats_by_day = Counter(
        _day(datetime.fromtimestamp(c["updated_at"], UTC)) for c in conversations
    )
    records_by_day = Counter(_day(datetime.fromisoformat(r.created_at)) for r in taken)

    return {
        "records": {
            "total": len(taken),
            "waiting": sum(r.status == "new" for r in taken),
            "by_type": dict(Counter(r.type for r in taken)),
        },
        "conversations": {
            "total": len(conversations),
            "handed_off": sum(c["handed_off"] for c in conversations),
            "blocked": sum(c["blocked"] for c in conversations),
            "refused": sum(c["refused"] for c in conversations),
        },
        "timeline": [
            {"day": day, "conversations": chats_by_day[day], "records": records_by_day[day]}
            for day in window
        ],
        "recent_records": [asdict(r) for r in taken[:5]],
        "recent_conversations": conversations[:5],
    }
