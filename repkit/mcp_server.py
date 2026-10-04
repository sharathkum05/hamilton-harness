"""Let Claude manage a pack over MCP.

Connect Claude (Claude Desktop, Claude Code or any MCP client) to this server
and it can read the rep's settings, rewrite knowledge, tighten the scope, change
rules and run the fake customers, all through the same validated editor the
dashboard uses. An edit that would break the pack is refused with the reason,
so Claude can correct it.

    repkit mcp packs/your-company
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from repkit.editor import EditError, PackEditor, list_conversations, read_conversation
from repkit.records import FileRecordStore, Status

INSTRUCTIONS = """\
This server manages one company's AI rep (a "pack"): who the rep is, what it
knows, what it may promise, and when a human takes over.

Start with get_overview. Knowledge files are the facts the rep answers from;
anything not in them is something the rep should not state, so add facts there
rather than to the persona. After changing rules, scope or knowledge, call
run_fake_customers and report the result: it shows whether the rep still
refuses what it should. Edits are validated; if one is refused, the message
says which field was wrong.
"""

Section = Literal["persona", "scope", "widget", "handoff"]


def build_server(
    pack_root: str | Path,
    *,
    trace_dir: str | Path | None = None,
    records_path: str | Path | None = None,
) -> MCPServer:
    editor = PackEditor(pack_root)
    traces = Path(trace_dir) if trace_dir else None
    records = FileRecordStore(records_path) if records_path else None
    server = MCPServer("repkit", instructions=INSTRUCTIONS)

    def guarded(work):
        """Turn a refused edit into a message Claude can act on."""
        try:
            return work()
        except EditError as error:
            return {"ok": False, "error": str(error)}

    @server.tool()
    def get_overview() -> dict[str, Any]:
        """Everything about the rep at a glance: persona, scope, look, handoff rules,
        policy rules, the actions it can take, and the names of its knowledge files."""
        overview = editor.overview()
        overview["knowledge"] = [
            {"name": doc["source"], "characters": len(doc["text"])} for doc in overview["knowledge"]
        ]
        overview["examples"] = [chat["title"] for chat in overview["examples"]]
        return overview

    @server.tool()
    def update_settings(section: Section, changes: dict[str, Any]) -> dict[str, Any]:
        """Change some fields in one section and keep the rest.

        Sections: persona (name, company, role, voice, banned_phrases, disclosure),
        scope (covers, off_topic_reply, refuse, strict, ground_numbers),
        widget (greeting, accent, theme, title, suggestions, corners, font),
        handoff (phrases, on_request, message). Call get_overview for current values.
        """
        return guarded(
            lambda: {
                "ok": True,
                section: editor.update_section(section, changes).model_dump(mode="json"),
            }
        )

    @server.tool()
    def read_knowledge(name: str) -> dict[str, Any]:
        """Read one knowledge file, such as shipping.md."""
        return guarded(lambda: {"ok": True, "name": name, "text": editor.read_knowledge(name)})

    @server.tool()
    def write_knowledge(name: str, text: str) -> dict[str, Any]:
        """Create or replace a knowledge file. Use Markdown with clear headings: each
        heading becomes a section the rep can look up on its own."""

        def work() -> dict[str, Any]:
            editor.save_knowledge(name, text)
            return {"ok": True, "saved": name}

        return guarded(work)

    @server.tool()
    def delete_knowledge(name: str) -> dict[str, Any]:
        """Delete a knowledge file. The rep stops stating anything only that file held."""

        def work() -> dict[str, Any]:
            editor.delete_knowledge(name)
            return {"ok": True, "deleted": name}

        return guarded(work)

    @server.tool()
    def save_rules(rules: list[dict[str, Any]]) -> dict[str, Any]:
        """Replace the full list of policy rules. Read the current list from
        get_overview first, change what is needed, and send the whole list back."""
        return guarded(lambda: {"ok": True, "count": len(editor.save_policies(rules))})

    @server.tool()
    def run_fake_customers() -> dict[str, Any]:
        """Run the pack's test customers against the current configuration and
        return the scorecard. Run this after any change to rules, scope or knowledge."""
        return guarded(editor.run_fake_customers)

    @server.tool()
    def recent_conversations(limit: int = 20) -> dict[str, Any]:
        """Recent real conversations, newest first, flagged where the guard stepped
        in, a message was off topic, or a human took over."""
        return {"conversations": list_conversations(traces, limit=max(1, min(limit, 50)))}

    @server.tool()
    def get_conversation(conversation_id: str) -> dict[str, Any]:
        """Every recorded step of one conversation, to see why the rep answered as it did."""
        return guarded(lambda: {"ok": True, "events": read_conversation(traces, conversation_id)})

    @server.tool()
    def list_records(type: str | None = None) -> dict[str, Any]:
        """Orders, quotation requests and other records the rep has taken down for the
        business, newest first. Pass a type such as "order" or "quote" to filter."""
        if records is None:
            return {"records": []}
        return {"records": [asdict(record) for record in records.list(type)]}

    @server.tool()
    def set_record_status(record_id: str, status: Status) -> dict[str, Any]:
        """Mark a record new, confirmed, done or cancelled."""
        record = records.set_status(record_id, status) if records else None
        if record is None:
            return {"ok": False, "error": f"no record {record_id}"}
        return {"ok": True, "record": asdict(record)}

    return server
