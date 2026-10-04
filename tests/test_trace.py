from dataclasses import dataclass
from types import SimpleNamespace

from hamilton_harness.trace import Trace, TraceWriter, jsonable, read_trace


@dataclass
class Point:
    x: int
    tags: tuple


def test_jsonable_handles_dataclasses_and_sdk_objects():
    block = SimpleNamespace(model_dump=lambda: {"type": "text", "text": "hi"})
    assert jsonable({"p": Point(1, ("a",)), "b": [block], 3: object}) == {
        "p": {"x": 1, "tags": ["a"]},
        "b": [{"type": "text", "text": "hi"}],
        "3": str(object),
    }


def test_trace_collects_events_in_order():
    trace = Trace("c1")
    trace.add("customer", text="hi")
    trace.add("reply", bubbles=["hello"])
    assert trace.kinds() == ["customer", "reply"]
    assert trace.first("reply").data == {"bubbles": ["hello"]}
    assert trace.first("missing") is None


def test_turns_append_to_one_file(tmp_path):
    writer = TraceWriter(tmp_path / "traces")
    for turn, text in enumerate(["hi", "where is my order ₹"], start=1):
        trace = Trace("c1", turn=turn)
        trace.add("customer", text=text)
        writer.write(trace)
    records = read_trace(writer.path("c1"))
    assert [r["turn"] for r in records] == [1, 2]
    assert records[1]["text"] == "where is my order ₹"
    assert records[0]["kind"] == "customer"
