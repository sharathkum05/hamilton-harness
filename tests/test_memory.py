from repkit.memory import Conversation, FileStore, InMemoryStore, facts_from_result
from repkit.tools import ToolRegistry


def test_conversations_get_distinct_ids():
    assert Conversation().id != Conversation().id


def test_new_conversation_is_not_handed_off():
    assert Conversation().handed_off is False


def test_in_memory_store_round_trip():
    store = InMemoryStore()
    store.save("c1", {"name": "Priya"})
    loaded = store.load("c1")
    loaded["name"] = "changed"
    assert store.load("c1") == {"name": "Priya"}
    assert store.load("unknown") == {}


def test_file_store_round_trip(tmp_path):
    store = FileStore(tmp_path / "customers")
    store.save("priya@example.com", {"name": "Priya", "last_order": "LS-4471"})
    assert FileStore(tmp_path / "customers").load("priya@example.com")["last_order"] == "LS-4471"


def test_file_store_does_not_put_the_customer_id_in_the_file_name(tmp_path):
    FileStore(tmp_path).save("priya@example.com", {"name": "Priya"})
    assert all("priya" not in path.name for path in tmp_path.iterdir())


def test_file_store_survives_a_corrupt_file(tmp_path):
    store = FileStore(tmp_path)
    store.save("c1", {"name": "Priya"})
    next(tmp_path.iterdir()).write_text("{not json", encoding="utf-8")
    assert store.load("c1") == {}


def test_facts_are_picked_from_tool_results(pack):
    registry = ToolRegistry(pack)
    result = registry.call("lookup_order", {"order_id": "ls-4471"})
    facts = facts_from_result(registry.spec("lookup_order"), result.data)
    assert facts == {
        "name": "Priya",
        "last_order": "LS-4471",
        "last_item": "Drift Runner, black, UK 7",
    }


def test_missing_fields_are_skipped(pack):
    spec = ToolRegistry(pack).spec("lookup_order")
    assert facts_from_result(spec, {"customer": "Priya"}) == {"name": "Priya"}
    assert facts_from_result(spec, "not a dict") == {}
