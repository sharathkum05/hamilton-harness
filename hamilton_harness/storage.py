"""Where a served rep keeps what it takes down, remembers and records.

With HAMILTON_DATABASE_URL set, that is a database (see db.py), shared by any
number of servers. Without it, it is the state folder: fine for one server on
one machine, and nothing to set up.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from hamilton_harness.memory import FileStore
from hamilton_harness.pack import PackError
from hamilton_harness.records import FileRecordStore

DATABASE_ENV = "HAMILTON_DATABASE_URL"


def agent_storage(state: Path, rep: str) -> tuple[dict[str, Any], str]:
    """The stores to give an Agent, as keyword arguments, and a line saying where they are.

    `rep` names the rep's rows in a shared database, so two reps never mix.
    """
    url = os.environ.get(DATABASE_ENV, "").strip()
    if not url:
        stores = {
            "store": FileStore(state / "customers"),
            "records": FileRecordStore(state / "records.json"),
            "trace_dir": state / "traces",
        }
        return stores, f"files in {state}"
    try:
        from hamilton_harness import db
    except ImportError as exc:
        raise PackError(
            f'{DATABASE_ENV} needs the database packages: pip install "hamilton-harness[db]"'
        ) from exc
    try:
        customers, records, traces, where = db.stores(url, rep)
    except Exception as exc:  # noqa: BLE001 - any driver error means the same thing here
        # The driver's first line says what went wrong; the rest can repeat the address.
        reason = str(getattr(exc, "orig", None) or exc).strip().splitlines()[0]
        raise PackError(f"could not open the database in {DATABASE_ENV}: {reason}") from exc
    return {"store": customers, "records": records, "traces": traces}, where
