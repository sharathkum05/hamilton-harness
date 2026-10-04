import json
import os
from datetime import UTC, date, datetime

from hamilton_harness.records import MemoryRecordStore
from hamilton_harness.stats import overview

TODAY = date(2026, 10, 4)


def trace(directory, name, when, kinds):
    path = directory / f"{name}.jsonl"
    lines = [{"turn": 1, "at": 0, "kind": kind, "text": "hello"} for kind in kinds]
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    stamp = datetime(*when, tzinfo=UTC).timestamp()
    os.utime(path, (stamp, stamp))


def test_empty_overview_has_a_full_timeline():
    stats = overview(None, MemoryRecordStore(), today=TODAY)
    assert stats["records"] == {"total": 0, "waiting": 0, "by_type": {}}
    assert stats["conversations"]["total"] == 0
    assert len(stats["timeline"]) == 14
    assert stats["timeline"][-1]["day"] == "2026-10-04"
    assert stats["timeline"][0]["day"] == "2026-09-21"


def test_counts_and_timeline(tmp_path):
    trace(tmp_path, "0123456789ab", (2026, 10, 4, 9), ["customer", "scope_refused"])
    trace(tmp_path, "0123456789ac", (2026, 10, 3, 9), ["customer", "handoff"])
    trace(tmp_path, "0123456789ad", (2026, 10, 3, 18), ["customer", "reply_blocked"])
    records = MemoryRecordStore()
    records.add("order", {"quantity": 2})
    quote = records.add("quote", {"quantity": 40})
    records.set_status(quote.id, "confirmed")
    today = datetime.now(UTC).date()

    stats = overview(tmp_path, records, today=TODAY)
    assert stats["conversations"] == {"total": 3, "handed_off": 1, "blocked": 1, "refused": 1}
    by_day = {point["day"]: point["conversations"] for point in stats["timeline"]}
    assert by_day["2026-10-04"] == 1 and by_day["2026-10-03"] == 2
    assert stats["records"] == {"total": 2, "waiting": 1, "by_type": {"order": 1, "quote": 1}}
    assert len(stats["recent_records"]) == 2
    assert stats["recent_conversations"][0]["id"] == "0123456789ab"
    # Records are stamped with the real clock, so they land on the real today.
    assert sum(p["records"] for p in overview(tmp_path, records, today=today)["timeline"]) == 2


def test_window_length_is_configurable():
    assert len(overview(None, MemoryRecordStore(), days=7, today=TODAY)["timeline"]) == 7
