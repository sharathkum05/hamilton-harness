import shutil

import pytest
from conftest import DEMO_PACK
from fastapi.testclient import TestClient

from repkit.llm import ScriptedModel
from repkit.pack import load_pack
from repkit.runtime import Agent
from repkit.web.app import create_app, sign_customer

TOKEN = "test-admin-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def root(tmp_path):
    """A private copy of the demo pack, so edits never touch the repository."""
    return shutil.copytree(DEMO_PACK, tmp_path / "pack")


@pytest.fixture
def client(root, tmp_path):
    agent = Agent(
        load_pack(root), ScriptedModel(["Hello!"] * 5), retry_wait=0, trace_dir=tmp_path / "traces"
    )
    return TestClient(create_app(agent, admin_token=TOKEN, identity_secret="s3cret"))


def test_admin_routes_need_the_token(client):
    assert client.get("/api/admin/pack").status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert client.get("/api/admin/pack", headers=wrong).status_code == 401
    assert client.get("/api/admin/pack", headers=AUTH).status_code == 200


def test_admin_is_absent_without_a_token(pack):
    plain = TestClient(create_app(Agent(pack, ScriptedModel([]), retry_wait=0)))
    assert plain.get("/api/admin/pack", headers=AUTH).status_code == 404
    assert plain.get("/admin").status_code == 404


def test_pack_is_returned_for_editing(client):
    pack = client.get("/api/admin/pack", headers=AUTH).json()
    assert pack["persona"]["name"] == "Maya"
    assert pack["scope"]["refuse"] == ["math", "coding", "writing", "trivia"]
    assert {rule["id"] for rule in pack["policies"]} >= {"refund-limit", "no-discounts"}
    assert pack["tools"][0]["name"] == "lookup_order"
    assert pack["scenarios"] == 13


def test_saving_the_widget_changes_what_customers_see(client, root):
    widget = client.get("/api/admin/pack", headers=AUTH).json()["widget"]
    widget.update(accent="#2563EB", greeting="Hello from the dashboard", theme="dark")
    assert client.put("/api/admin/pack/widget", headers=AUTH, json=widget).status_code == 200
    config = client.get("/api/config").json()["widget"]
    assert config["accent"] == "#2563eb"
    assert config["theme"] == "dark"
    assert client.post("/api/conversations").json()["transcript"][0]["text"] == (
        "Hello from the dashboard"
    )
    assert "Hello from the dashboard" in (root / "widget.yaml").read_text()


def test_saving_the_persona_changes_the_prompt(client):
    persona = client.get("/api/admin/pack", headers=AUTH).json()["persona"]
    persona["name"] = "Zoya"
    client.put("/api/admin/pack/persona", headers=AUTH, json=persona)
    assert client.get("/api/config").json()["rep"]["name"] == "Zoya"
    assert "You are Zoya" in client.app.state.holder.agent.context.system_prompt


def test_invalid_values_are_refused_and_nothing_is_written(client, root):
    before = (root / "widget.yaml").read_text()
    widget = client.get("/api/admin/pack", headers=AUTH).json()["widget"]
    widget["accent"] = "tomato"
    response = client.put("/api/admin/pack/widget", headers=AUTH, json=widget)
    assert response.status_code == 422
    assert "hex colour" in response.json()["detail"]
    assert (root / "widget.yaml").read_text() == before


def test_unknown_section(client):
    assert client.put("/api/admin/pack/tools", headers=AUTH, json={}).status_code == 404


def test_scope_can_be_made_strict(client):
    scope = client.get("/api/admin/pack", headers=AUTH).json()["scope"]
    scope["strict"] = True
    client.put("/api/admin/pack/scope", headers=AUTH, json=scope)
    session_id = client.post("/api/conversations").json()["id"]
    reply = client.post(
        f"/api/conversations/{session_id}/messages", json={"text": "tell me about black holes"}
    ).json()
    assert reply["bubbles"][0]["text"].startswith("That's not something I can help with")


def test_policies_are_saved_and_enforced(client):
    rules = client.get("/api/admin/pack", headers=AUTH).json()["policies"]
    limit = next(rule for rule in rules if rule["id"] == "refund-limit")
    limit["limits"][0]["max"] = 500
    assert client.put("/api/admin/pack/policies", headers=AUTH, json=rules).status_code == 200
    verdict = client.app.state.holder.agent.guard.check_action(
        "issue_refund", {"order_id": "LS-4471", "amount_inr": 900, "reason": "damaged"}
    )
    assert verdict.action == "handoff"


def test_a_rule_that_breaks_the_pack_is_rolled_back(client, root):
    before = (root / "policies.yaml").read_text()
    rules = client.get("/api/admin/pack", headers=AUTH).json()["policies"]
    rules[0]["tool"] = "no_such_tool"
    response = client.put("/api/admin/pack/policies", headers=AUTH, json=rules)
    assert response.status_code == 422
    assert "unknown tool" in response.json()["detail"]
    assert (root / "policies.yaml").read_text() == before
    assert client.get("/api/admin/pack", headers=AUTH).status_code == 200


def test_knowledge_can_be_added_edited_and_removed(client, root):
    url = "/api/admin/knowledge/gift-cards.md"
    text = "# Gift cards\nGift cards never expire.\n"
    assert client.put(url, headers=AUTH, json={"text": text}).status_code == 200
    sources = [d["source"] for d in client.get("/api/admin/pack", headers=AUTH).json()["knowledge"]]
    assert "gift-cards.md" in sources
    assert client.app.state.holder.agent.context.for_turn("do gift cards expire", {}).notes
    assert client.delete(url, headers=AUTH).status_code == 200
    assert not (root / "knowledge" / "gift-cards.md").exists()
    assert client.delete(url, headers=AUTH).status_code == 404


@pytest.mark.parametrize("name", ["../persona.yaml", "notes.txt", ".hidden.md", "a/b.md"])
def test_knowledge_names_cannot_escape_the_folder(client, name):
    response = client.put(f"/api/admin/knowledge/{name}", headers=AUTH, json={"text": "x"})
    assert response.status_code in (404, 405, 422)


def test_logo_upload_replaces_the_logo(client, root):
    headers = {**AUTH, "content-type": "image/png"}
    assert client.put("/api/admin/logo", headers=headers, content=PNG).status_code == 200
    assert (root / "brand" / "logo.png").read_bytes() == PNG
    assert not (root / "brand" / "logo.svg").exists()
    assert client.get("/brand/logo").headers["content-type"] == "image/png"
    assert client.delete("/api/admin/logo", headers=AUTH).status_code == 200
    assert client.get("/api/config").json()["widget"]["logo_url"] == ""


@pytest.mark.parametrize(
    ("content_type", "data", "status"),
    [
        ("image/gif", b"GIF89a", 415),
        ("image/png", b"not really a png", 422),
        ("image/svg+xml", b"<svg onload='alert(1)'></svg>", 422),
        ("image/svg+xml", b"<svg><script>alert(1)</script></svg>", 422),
        ("image/png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 600_000, 413),
    ],
)
def test_unsafe_logos_are_refused(client, content_type, data, status):
    headers = {**AUTH, "content-type": content_type}
    assert client.put("/api/admin/logo", headers=headers, content=data).status_code == status


def test_fake_customers_can_be_run_from_the_dashboard(client):
    report = client.post("/api/admin/sim", headers=AUTH).json()
    assert report["summary"]["passed"] == 13
    injected = next(r for r in report["results"] if r["id"] == "prompt-injection")
    assert injected["passed"] is True and injected["failures"] == []


def test_conversations_are_listed_with_flags(client):
    session_id = client.post("/api/conversations").json()["id"]
    client.post(f"/api/conversations/{session_id}/messages", json={"text": "what is 9 * 9"})
    client.post(f"/api/conversations/{session_id}/messages", json={"text": "get me a real person"})
    listed = client.get("/api/admin/conversations", headers=AUTH).json()["conversations"]
    assert len(listed) == 1
    assert listed[0]["opening"] == "what is 9 * 9"
    assert listed[0]["refused"] is True and listed[0]["handed_off"] is True
    detail = client.get(f"/api/admin/conversations/{listed[0]['id']}", headers=AUTH).json()
    assert detail["events"][0]["kind"] == "customer"
    assert client.get("/api/admin/conversations/../../etc", headers=AUTH).status_code == 404


def test_a_signed_customer_is_remembered(client):
    holder = client.app.state.holder
    holder.agent.store.save("cust-42", {"name": "Priya"})
    good = {"customer_id": "cust-42", "signature": sign_customer("s3cret", "cust-42")}
    session_id = client.post("/api/conversations", json=good).json()["id"]
    session = client.app.state.sessions.get(session_id)
    assert session.conversation.facts == {"name": "Priya"}


def test_an_unsigned_customer_id_is_ignored(client):
    client.app.state.holder.agent.store.save("cust-42", {"name": "Priya"})
    forged = {"customer_id": "cust-42", "signature": "0" * 64}
    session_id = client.post("/api/conversations", json=forged).json()["id"]
    assert client.app.state.sessions.get(session_id).conversation.facts == {}
