"""The database stores, on SQLite always and on Postgres when one is given.

Set HAMILTON_TEST_DATABASE_URL to a Postgres database to run the Postgres half.
"""

import os
import threading
import uuid

import pytest

pytest.importorskip("sqlalchemy")

from conftest import DEMO_PACK  # noqa: E402
from sqlalchemy import inspect, select  # noqa: E402

from hamilton_harness import db  # noqa: E402
from hamilton_harness.llm import ScriptedModel  # noqa: E402
from hamilton_harness.pack import load_pack  # noqa: E402
from hamilton_harness.runtime import Agent  # noqa: E402
from hamilton_harness.stats import overview  # noqa: E402
from hamilton_harness.trace import Trace  # noqa: E402

POSTGRES = os.environ.get("HAMILTON_TEST_DATABASE_URL", "")


@pytest.fixture(params=["sqlite", "postgres"])
def engine(request, tmp_path):
    if request.param == "postgres":
        if not POSTGRES:
            pytest.skip("set HAMILTON_TEST_DATABASE_URL to test on Postgres")
        return db.connect(POSTGRES)
    return db.connect(f"sqlite:///{tmp_path / 'hamilton.db'}")


@pytest.fixture
def rep():
    # A rep of its own per test, so tests sharing one Postgres never see each other's rows.
    return f"test-{uuid.uuid4().hex[:8]}"


def test_records_are_numbered_per_type_and_listed_newest_first(engine, rep):
    store = db.DbRecordStore(engine, rep)
    first = store.add("order", {"product": "Drift Runner"}, conversation_id="abc")
    store.add("quote", {"quantity": 40})
    second = store.add("order", {"product": "Trail Loop"})
    assert (first.id, second.id) == ("ORD-0001", "ORD-0002")
    assert len(store.list()) == 3
    assert [r.id for r in store.list("order")] == ["ORD-0002", "ORD-0001"]
    assert store.list("quote")[0].data == {"quantity": 40}
    assert store.list("order")[-1].conversation_id == "abc"


def test_a_record_status_can_change(engine, rep):
    store = db.DbRecordStore(engine, rep)
    record = store.add("order", {"product": "Drift Runner"})
    changed = store.set_status(record.id, "confirmed")
    assert changed is not None and changed.status == "confirmed"
    assert store.list()[0].status == "confirmed"
    assert store.set_status("ORD-9999", "done") is None


def test_reps_sharing_a_database_never_see_each_other(engine, rep):
    mine, theirs = db.DbRecordStore(engine, rep), db.DbRecordStore(engine, rep + "-other")
    mine.add("order", {"product": "Drift Runner"})
    assert theirs.list() == []
    assert theirs.add("order", {"product": "Court Classic"}).id == "ORD-0001"
    assert theirs.set_status("ORD-0001", "done").data == {"product": "Court Classic"}
    assert mine.list()[0].status == "new"


def test_orders_taken_at_the_same_moment_get_different_numbers(engine, rep):
    if engine.dialect.name != "postgresql":
        pytest.skip("SQLite takes one writer at a time")
    store = db.DbRecordStore(engine, rep)
    ids: list[str] = []
    threads = [
        threading.Thread(target=lambda: ids.append(store.add("order", {}).id)) for _ in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(ids) == [f"ORD-{n:04d}" for n in range(1, 7)]


def test_customer_facts_are_kept_under_a_hash_of_the_id(engine, rep):
    store = db.DbCustomerStore(engine, rep)
    assert store.load("priya@example.com") == {}
    store.save("priya@example.com", {"name": "Priya"})
    store.save("priya@example.com", {"name": "Priya", "size": "8"})
    assert store.load("priya@example.com") == {"name": "Priya", "size": "8"}
    assert db.DbCustomerStore(engine, rep + "-other").load("priya@example.com") == {}
    with engine.connect() as connection:
        keys = connection.scalars(select(db.customers_table.c.customer_key)).all()
    assert "priya@example.com" not in keys


def _trace(conversation_id, turn, *events):
    trace = Trace(conversation_id, turn)
    for kind, data in events:
        trace.add(kind, **data)
    return trace


def test_turns_are_recorded_and_summarised(engine, rep):
    store = db.DbTraceStore(engine, rep)
    store.write(_trace("aaaaaaaaaaaa", 1, ("customer", {"text": "where is my order"})))
    store.write(_trace("aaaaaaaaaaaa", 2, ("customer", {"text": "a person please"})))
    store.write(_trace("aaaaaaaaaaaa", 2, ("handoff", {"reason": "requested"})))
    store.write(_trace("bbbbbbbbbbbb", 1, ("scope_refused", {"detector": "math"})))

    listed = store.conversations()
    assert [c["id"] for c in listed] == ["bbbbbbbbbbbb", "aaaaaaaaaaaa"]
    first = listed[1]
    assert first["opening"] == "where is my order"
    assert first["turns"] == 2 and first["handed_off"] and not first["refused"]
    assert listed[0]["refused"]

    events = store.events("aaaaaaaaaaaa")
    assert [e["kind"] for e in events] == ["customer", "customer", "handoff"]
    assert events[2]["reason"] == "requested"
    assert store.events("cccccccccccc") is None
    assert store.events("../../etc") is None
    assert db.DbTraceStore(engine, rep + "-other").conversations() == []


def test_a_rep_on_the_database_records_everything_there(engine, rep):
    customers, records, traces = (
        db.DbCustomerStore(engine, rep),
        db.DbRecordStore(engine, rep),
        db.DbTraceStore(engine, rep),
    )
    pack = load_pack(DEMO_PACK)
    model = ScriptedModel(
        [
            {"tool": "lookup_order", "args": {"order_id": "LS-4471"}},
            "It's on the way, arriving Thursday 8 October.",
        ]
    )
    agent = Agent(pack, model, store=customers, records=records, traces=traces, retry_wait=0)
    conversation = agent.start("priya@example.com")
    agent.respond(conversation, "where is LS-4471")
    assert agent.with_pack(pack).traces is traces
    summary = overview(traces, records)
    assert summary["conversations"]["total"] == 1
    assert traces.events(conversation.id)[0]["kind"] == "customer"


def test_postgres_tables_live_in_their_own_schema(engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("only Postgres has schemas")
    names = inspect(engine).get_table_names(schema=db.SCHEMA)
    assert {"records", "customers", "trace_events"} <= set(names)
    assert "records" not in inspect(engine).get_table_names(schema="public")


@pytest.mark.parametrize(
    ("given", "used"),
    [
        ("postgres://u:p@db.example.co:5432/postgres", "postgresql+psycopg://"),
        ("postgresql://u:p@db.example.co:5432/postgres", "postgresql+psycopg://"),
        ("sqlite:///x.db", "sqlite:///"),
    ],
)
def test_a_supabase_url_is_pointed_at_the_driver(given, used):
    assert db._driver_url(given).startswith(used)


def test_the_password_never_reaches_the_console(tmp_path):
    engine = db.connect(f"sqlite:///{tmp_path / 'h.db'}")
    assert db.describe(engine).startswith("sqlite:///")
    from sqlalchemy import create_engine

    remote = create_engine("postgresql+psycopg://user:s3cret@db.example.co/postgres")
    assert "s3cret" not in db.describe(remote)
