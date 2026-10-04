import asyncio
import json
import shutil

import pytest
from conftest import DEMO_PACK

from repkit.mcp_server import build_server
from repkit.pack import load_pack


@pytest.fixture
def root(tmp_path):
    return shutil.copytree(DEMO_PACK, tmp_path / "pack")


def call(server, tool, **arguments):
    """Call a tool the way an MCP client would and return its JSON result."""
    result = asyncio.run(server.call_tool(tool, arguments))
    blocks = result[0] if isinstance(result, tuple) else getattr(result, "content", result)
    return json.loads(blocks[0].text)


def test_tools_are_listed_with_descriptions(root):
    tools = asyncio.run(build_server(root).list_tools())
    names = {tool.name for tool in tools}
    assert {"get_overview", "update_settings", "write_knowledge", "run_fake_customers"} <= names
    assert all(tool.description for tool in tools)


def test_overview_lists_knowledge_by_name(root):
    overview = call(build_server(root), "get_overview")
    assert overview["persona"]["name"] == "Maya"
    assert any(doc["name"] == "shipping.md" for doc in overview["knowledge"])
    assert "text" not in overview["knowledge"][0]


def test_claude_can_add_knowledge(root):
    server = build_server(root)
    text = "# Gift cards\n\n## Expiry\nLoop gift cards never expire.\n"
    assert call(server, "write_knowledge", name="gift-cards.md", text=text) == {
        "ok": True,
        "saved": "gift-cards.md",
    }
    assert call(server, "read_knowledge", name="gift-cards.md")["text"] == text
    assert any(doc.source == "gift-cards.md" for doc in load_pack(root).knowledge)


def test_claude_can_tighten_the_scope(root):
    server = build_server(root)
    result = call(server, "update_settings", section="scope", changes={"strict": True})
    assert result["ok"] is True and result["scope"]["strict"] is True
    assert load_pack(root).scope.strict is True


def test_a_bad_edit_comes_back_as_a_message_not_a_crash(root):
    result = call(
        build_server(root), "update_settings", section="widget", changes={"accent": "tomato"}
    )
    assert result["ok"] is False
    assert "hex colour" in result["error"]
    assert load_pack(root).widget.accent == "auto"


def test_claude_can_run_the_fake_customers(root):
    report = call(build_server(root), "run_fake_customers")
    assert report["summary"]["passed"] == 16
