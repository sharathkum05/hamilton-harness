import pytest
from pydantic import ValidationError

from repkit.llm import ScriptedModel
from repkit.pack.schema import Pack, Persona, RecordField, RecordType
from repkit.records import FileRecordStore, MemoryRecordStore, input_schema
from repkit.runtime import Agent
from repkit.tools import ToolRegistry

ORDER = {
    "product": "Court Classic",
    "size": "9",
    "quantity": 2,
    "customer_name": "Ravi Menon",
    "phone": "5550123",
}


def test_references_are_numbered_per_type():
    store = MemoryRecordStore()
    assert store.add("order", {}).id == "ORD-0001"
    assert store.add("quote", {}).id == "QUO-0001"
    assert store.add("order", {}).id == "ORD-0002"
    assert {r.id for r in store.list("order")} == {"ORD-0001", "ORD-0002"}


def test_status_changes_are_kept(tmp_path):
    store = FileRecordStore(tmp_path / "records.json")
    record = store.add("order", ORDER, "abc123")
    assert store.set_status(record.id, "confirmed").status == "confirmed"
    reopened = FileRecordStore(tmp_path / "records.json")
    assert reopened.list()[0].status == "confirmed"
    assert reopened.list()[0].conversation_id == "abc123"
    assert reopened.set_status("ORD-9999", "done") is None


def test_a_corrupt_file_reads_as_empty(tmp_path):
    path = tmp_path / "records.json"
    path.write_text("{broken", encoding="utf-8")
    assert FileRecordStore(path).list() == []


def test_schema_is_built_from_the_fields(pack):
    schema = input_schema(pack.records[1])
    assert schema["properties"]["product"]["enum"] == [
        "Drift Runner",
        "Court Classic",
        "Trail Loop",
    ]
    assert schema["properties"]["quantity"] == {"type": "number", "description": "Pairs"}
    assert "notes" not in schema["required"]
    assert schema["additionalProperties"] is False


def test_choice_fields_need_choices():
    with pytest.raises(ValidationError, match="lists no choices"):
        RecordField(name="product", type="choice")


def test_a_record_cannot_clash_with_a_tool(pack):
    clash = RecordType(name="order", label="Order", description="d", fields=[RecordField(name="x")])
    tool = pack.tools[0].model_copy(update={"name": "create_order"})
    with pytest.raises(ValidationError, match="clashes with tool"):
        Pack(persona=Persona(name="M", company="C"), tools=[tool], records=[clash])


def test_each_record_type_becomes_an_action(pack):
    registry = ToolRegistry(pack)
    assert {"create_order", "create_quote"} <= set(registry.names())
    result = registry.call("create_order", ORDER, conversation_id="c1")
    assert result.ok and result.data["reference"] == "ORD-0001"
    assert registry.records.list()[0].data == ORDER


def test_incomplete_records_are_refused(pack):
    registry = ToolRegistry(pack)
    missing = {k: v for k, v in ORDER.items() if k != "phone"}
    assert "Invalid arguments" in registry.call("create_order", missing).content
    wrong = {**ORDER, "product": "Flip Flop"}
    assert not registry.call("create_order", wrong).ok
    assert registry.records.list() == []


def test_the_rep_takes_an_order_and_gives_the_reference(pack):
    steps = [{"tool": "create_order", "args": ORDER}, "Thanks, Ravi. Order ORD-0001 is in."]
    agent = Agent(pack, ScriptedModel(steps), retry_wait=0)
    conversation = agent.start()
    result = agent.respond(conversation, "I want to buy 2 pairs of Court Classic in UK 9")
    assert result.replaced_by == ""
    assert "ORD-0001" in result.text
    record = agent.records.list("order")[0]
    assert record.conversation_id == conversation.id
    assert conversation.facts["last_order"] == "ORD-0001"


def test_the_guard_applies_to_records(pack):
    big = {**ORDER, "quantity": 30}
    agent = Agent(pack, ScriptedModel([{"tool": "create_order", "args": big}, "ok"]), retry_wait=0)
    result = agent.respond(agent.start(), "put me down for 30 pairs of Court Classic")
    assert result.actions[0].outcome == "blocked"
    assert result.actions[0].rule_ids == ("order-size",)
    assert agent.records.list() == []


def test_records_survive_a_pack_reload(pack):
    agent = Agent(pack, ScriptedModel([]), retry_wait=0)
    agent.records.add("order", ORDER)
    assert agent.with_pack(pack).records.list()[0].id == "ORD-0001"
