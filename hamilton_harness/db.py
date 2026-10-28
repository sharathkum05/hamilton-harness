"""Keep records, customer memory and conversations in a database.

Set HAMILTON_DATABASE_URL to a Postgres connection string, such as the one
Supabase shows under Connect, and `serve`, `studio` and `demo` keep what the
rep takes down, what it remembers about customers and every recorded turn
there instead of in the state folder. The pack itself stays as files.

Several reps can share one database: every row carries the rep it belongs to.
On Postgres the tables live in their own `hamilton` schema, which Supabase does
not expose through its public API, so customer data is not readable with the
project's anon key.

Needs the optional packages: pip install "hamilton-harness[db]"
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Engine,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from hamilton_harness.records import Record, Status
from hamilton_harness.trace import CONVERSATION_ID, Trace, summarize

SCHEMA = "hamilton"

metadata = MetaData()

records_table = Table(
    "records",
    metadata,
    Column("rep", String(120), primary_key=True),
    Column("id", String(40), primary_key=True),
    Column("type", String(80), nullable=False),
    Column("data", JSON, nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("conversation_id", String(40), nullable=False, default=""),
)

customers_table = Table(
    "customers",
    metadata,
    Column("rep", String(120), primary_key=True),
    # A hash of the customer's id, which is often an email or a phone number.
    Column("customer_key", String(64), primary_key=True),
    Column("facts", JSON, nullable=False),
    Column("updated_at", String(40), nullable=False),
)

events_table = Table(
    "trace_events",
    metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("rep", String(120), nullable=False),
    Column("conversation_id", String(40), nullable=False),
    Column("turn", Integer, nullable=False),
    Column("at", Float, nullable=False),
    Column("kind", String(40), nullable=False),
    Column("data", JSON, nullable=False),
    Index("trace_events_conversation", "rep", "conversation_id"),
)


def _driver_url(url: str) -> str:
    """Point a plain postgres:// URL, as Supabase gives it, at the psycopg driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def connect(url: str) -> Engine:
    """Open the database and create the tables if they are not there yet."""
    url = _driver_url(url.strip())
    postgres = make_url(url).get_backend_name() == "postgresql"
    engine = create_engine(
        url,
        pool_pre_ping=True,
        # Supabase's pooler runs in transaction mode, which cannot keep prepared statements.
        connect_args={"prepare_threshold": None} if postgres else {},
    )
    if postgres:
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        engine = engine.execution_options(schema_translate_map={None: SCHEMA})
    metadata.create_all(engine)
    return engine


def describe(engine: Engine) -> str:
    """Where the data goes, for the console, with the password hidden."""
    return engine.url.render_as_string(hide_password=True)


class DbRecordStore:
    def __init__(self, engine: Engine, rep: str) -> None:
        self._engine, self._rep = engine, rep

    def add(self, type_name: str, data: dict[str, Any], conversation_id: str = "") -> Record:
        prefix = type_name[:3].upper()
        # Two servers can take an order at the same moment; the loser takes the next number.
        for _ in range(5):
            with self._engine.begin() as db:
                taken = db.scalar(
                    select(func.count())
                    .select_from(records_table)
                    .where(records_table.c.rep == self._rep, records_table.c.type == type_name)
                )
                record = Record(
                    id=f"{prefix}-{taken + 1:04d}",
                    type=type_name,
                    data=data,
                    conversation_id=conversation_id,
                )
                try:
                    db.execute(insert(records_table).values(rep=self._rep, **record.__dict__))
                except IntegrityError:
                    continue
                return record
        raise RuntimeError("could not number the record; too many taken at once")

    def list(self, type_name: str | None = None) -> list[Record]:
        query = select(records_table).where(records_table.c.rep == self._rep)
        if type_name is not None:
            query = query.where(records_table.c.type == type_name)
        with self._engine.connect() as db:
            # Times are to the second, so the reference breaks a tie: ORD-0002 came after ORD-0001.
            newest = (records_table.c.created_at.desc(), records_table.c.id.desc())
            rows = db.execute(query.order_by(*newest)).mappings()
            return [Record(**{k: v for k, v in row.items() if k != "rep"}) for row in rows]

    def set_status(self, record_id: str, status: Status) -> Record | None:
        where = (records_table.c.rep == self._rep) & (records_table.c.id == record_id)
        with self._engine.begin() as db:
            if not db.execute(update(records_table).where(where).values(status=status)).rowcount:
                return None
            row = db.execute(select(records_table).where(where)).mappings().one()
            return Record(**{k: v for k, v in row.items() if k != "rep"})


class DbCustomerStore:
    def __init__(self, engine: Engine, rep: str) -> None:
        self._engine, self._rep = engine, rep

    @staticmethod
    def _key(customer_id: str) -> str:
        return hashlib.sha256(customer_id.encode()).hexdigest()

    def load(self, customer_id: str) -> dict[str, str]:
        query = select(customers_table.c.facts).where(
            customers_table.c.rep == self._rep,
            customers_table.c.customer_key == self._key(customer_id),
        )
        with self._engine.connect() as db:
            facts = db.scalar(query)
        return dict(facts or {})

    def save(self, customer_id: str, facts: dict[str, str]) -> None:
        key = self._key(customer_id)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        where = (customers_table.c.rep == self._rep) & (customers_table.c.customer_key == key)
        with self._engine.begin() as db:
            changed = db.execute(
                update(customers_table).where(where).values(facts=dict(facts), updated_at=now)
            ).rowcount
            if not changed:
                db.execute(
                    insert(customers_table).values(
                        rep=self._rep, customer_key=key, facts=dict(facts), updated_at=now
                    )
                )


class DbTraceStore:
    def __init__(self, engine: Engine, rep: str) -> None:
        self._engine, self._rep = engine, rep

    def write(self, trace: Trace) -> None:
        rows = [
            {
                "rep": self._rep,
                "conversation_id": trace.conversation_id,
                "turn": trace.turn,
                "at": event.at,
                "kind": event.kind,
                "data": event.data,
            }
            for event in trace.events
        ]
        if rows:
            with self._engine.begin() as db:
                db.execute(insert(events_table), rows)

    def _rows(self, db: Any, conversation_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        query = (
            select(events_table)
            .where(
                events_table.c.rep == self._rep,
                events_table.c.conversation_id.in_(conversation_ids),
            )
            .order_by(events_table.c.seq)
        )
        grouped: dict[str, list[dict[str, Any]]] = {cid: [] for cid in conversation_ids}
        for row in db.execute(query).mappings():
            grouped[row["conversation_id"]].append(
                {"turn": row["turn"], "at": row["at"], "kind": row["kind"], **row["data"]}
            )
        return grouped

    def conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        latest = func.max(events_table.c.at).label("latest")
        recent = (
            select(events_table.c.conversation_id, latest)
            .where(events_table.c.rep == self._rep)
            .group_by(events_table.c.conversation_id)
            .order_by(latest.desc())
            .limit(limit)
        )
        with self._engine.connect() as db:
            order = [(row.conversation_id, row.latest) for row in db.execute(recent)]
            events = self._rows(db, [cid for cid, _ in order])
        return [summarize(cid, events[cid], latest) for cid, latest in order]

    def events(self, conversation_id: str) -> list[dict[str, Any]] | None:
        if not CONVERSATION_ID.fullmatch(conversation_id):
            return None
        with self._engine.connect() as db:
            events = self._rows(db, [conversation_id])[conversation_id]
        return events or None


def stores(url: str, rep: str) -> tuple[DbCustomerStore, DbRecordStore, DbTraceStore, str]:
    """The three stores for one rep, and where they are, for the console."""
    engine = connect(url)
    return (
        DbCustomerStore(engine, rep),
        DbRecordStore(engine, rep),
        DbTraceStore(engine, rep),
        describe(engine),
    )


__all__ = ["DbCustomerStore", "DbRecordStore", "DbTraceStore", "connect", "stores"]
