"""Vercel entry point: the hosted demo.

It serves the product page, the demo and the chat for the Loop Sneakers pack on
the pack's stand-in model, so it needs no API key. Vercel's functions keep
nothing between restarts and can only write to /tmp, so conversations, orders
and traces here are temporary and the dashboard, which edits the pack on disk,
is left switched off. Run the server yourself for the real thing.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hamilton_harness.llm import load_offline_model  # noqa: E402
from hamilton_harness.memory import FileStore  # noqa: E402
from hamilton_harness.pack import load_pack  # noqa: E402
from hamilton_harness.records import FileRecordStore  # noqa: E402
from hamilton_harness.runtime import Agent  # noqa: E402
from hamilton_harness.web.app import create_app  # noqa: E402

STATE = Path(os.environ.get("HAMILTON_STATE", "/tmp/hamilton"))

pack = load_pack(ROOT / "packs" / "loop-sneakers")
agent = Agent(
    pack,
    load_offline_model(pack.root),
    store=FileStore(STATE / "customers"),
    records=FileRecordStore(STATE / "records.json"),
    trace_dir=STATE / "traces",
)
# debug=True switches on the inspector, which is the point of the demo.
app = create_app(agent, debug=True)
