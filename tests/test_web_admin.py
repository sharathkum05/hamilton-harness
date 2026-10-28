import shutil

import pytest
from conftest import DEMO_PACK
from fastapi.testclient import TestClient

from hamilton_harness.llm import ScriptedModel
from hamilton_harness.pack import load_pack
from hamilton_harness.runtime import Agent
from hamilton_harness.web.app import create_app, sign_customer

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


def test_pack_is_returned_for_editing(client):
    pack = client.get("/api/admin/pack", headers=AUTH).json()
    assert pack["persona"]["name"] == "Maya"
    assert pack["scope"]["refuse"] == ["math", "coding", "writing", "trivia"]
    assert {rule["id"] for rule in pack["policies"]} >= {"refund-limit", "no-discounts"}
    assert pack["tools"][0]["name"] == "lookup_order"
    assert pack["scenarios"] == 16
    assert [r["name"] for r in pack["records"]] == ["order", "quote"]


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
    assert client.put("/api/admin/pack/secrets", headers=AUTH, json={}).status_code == 404


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
    assert report["summary"]["passed"] == 16
    injected = next(r for r in report["results"] if r["id"] == "prompt-injection")
    assert injected["passed"] is True and injected["failures"] == []
    assert report["warnings"] == []


def test_the_dashboard_test_run_carries_pack_warnings(client):
    saved = client.put(
        "/api/admin/pack/widget", headers=AUTH, json={"greeting": "Kindly ask me anything."}
    )
    assert saved.status_code == 200, saved.text
    report = client.post("/api/admin/sim", headers=AUTH).json()
    assert [(w["code"], w["where"]) for w in report["warnings"]] == [
        ("line-has-banned-phrase", "widget.yaml: greeting")
    ]


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


def test_records_are_listed_and_their_status_can_change(client):
    records = client.app.state.holder.agent.records
    records.add("order", {"product": "Court Classic", "quantity": 2}, "abc123")
    records.add("quote", {"product": "Drift Runner", "quantity": 40})
    listed = client.get("/api/admin/records", headers=AUTH).json()["records"]
    assert {r["id"] for r in listed} == {"ORD-0001", "QUO-0001"}
    only = client.get("/api/admin/records?type=quote", headers=AUTH).json()["records"]
    assert [r["id"] for r in only] == ["QUO-0001"]
    changed = client.patch(
        "/api/admin/records/ORD-0001", headers=AUTH, json={"status": "confirmed"}
    )
    assert changed.json()["status"] == "confirmed"
    bad = client.patch("/api/admin/records/ORD-0001", headers=AUTH, json={"status": "lost"})
    assert bad.status_code == 422
    missing = client.patch("/api/admin/records/X-1", headers=AUTH, json={"status": "done"})
    assert missing.status_code == 404
    assert client.get("/api/admin/records").status_code == 401


def test_overview_counts_what_has_happened(client):
    session_id = client.post("/api/conversations").json()["id"]
    client.post(f"/api/conversations/{session_id}/messages", json={"text": "what is 9 * 9"})
    client.app.state.holder.agent.records.add("quote", {"quantity": 40})
    stats = client.get("/api/admin/overview", headers=AUTH).json()
    assert stats["conversations"]["total"] == 1 and stats["conversations"]["refused"] == 1
    assert stats["records"]["waiting"] == 1
    assert stats["timeline"][-1]["conversations"] == 1
    assert client.get("/api/admin/overview").status_code == 401


EMAIL, PASSWORD = "admin@example.com", "demo-password-1"


@pytest.fixture
def browser(root, tmp_path):
    """A dashboard that also takes an email and password, as a browser would use it."""
    from hamilton_harness.web.auth import Credentials

    agent = Agent(load_pack(root), ScriptedModel([]), retry_wait=0, trace_dir=tmp_path / "traces")
    login = Credentials.from_password(EMAIL, PASSWORD)
    return TestClient(
        create_app(agent, admin_token=TOKEN, admin_credentials=login),
        base_url="http://testserver",
    )


def test_signing_in_with_the_password_opens_the_dashboard(browser):
    assert browser.get("/api/admin/session").status_code == 401
    assert browser.get("/api/admin/pack").status_code == 401
    signed = browser.post("/api/admin/session", json={"email": EMAIL, "password": PASSWORD})
    assert signed.status_code == 200
    cookie = signed.headers["set-cookie"]
    assert "httponly" in cookie.lower() and "samesite=strict" in cookie.lower()
    assert "path=/api/admin" in cookie.lower()
    assert browser.get("/api/admin/session").json() == {
        "email": EMAIL,
        "password": True,
        "demo": False,
    }
    assert browser.get("/api/admin/pack").status_code == 200


def test_a_wrong_password_is_refused_and_counted(browser):
    for _ in range(10):
        wrong = browser.post("/api/admin/session", json={"email": EMAIL, "password": "guess"})
        assert wrong.status_code == 401
    # Even the right password waits once an address has failed too often.
    blocked = browser.post("/api/admin/session", json={"email": EMAIL, "password": PASSWORD})
    assert blocked.status_code == 429


def test_signing_out_ends_the_session(browser):
    browser.post("/api/admin/session", json={"email": EMAIL, "password": PASSWORD})
    assert browser.delete("/api/admin/session").status_code == 200
    assert browser.get("/api/admin/pack").status_code == 401


def test_a_signed_in_cookie_cannot_make_changes_from_another_site(browser):
    browser.post("/api/admin/session", json={"email": EMAIL, "password": PASSWORD})
    widget = browser.get("/api/admin/pack").json()["widget"]
    elsewhere = {"origin": "https://attacker.example"}
    refused = browser.put("/api/admin/pack/widget", json=widget, headers=elsewhere)
    assert refused.status_code == 403
    here = {"origin": "http://testserver"}
    assert browser.put("/api/admin/pack/widget", json=widget, headers=here).status_code == 200


def test_the_token_still_works_beside_the_password(browser):
    assert browser.get("/api/admin/session", headers=AUTH).json() == {
        "email": None,
        "password": True,
        "demo": False,
    }
    assert browser.get("/api/admin/pack", headers=AUTH).status_code == 200


def test_without_credentials_only_the_token_signs_in(client):
    refused = client.post("/api/admin/session", json={"email": EMAIL, "password": PASSWORD})
    assert refused.status_code == 400
    assert client.get("/api/admin/session").headers["x-hamilton-password"] == "off"


def test_setup_from_the_dashboard_rebuilds_the_running_rep(tmp_path):
    from hamilton_harness.scaffold import write_starter_pack
    from hamilton_harness.setup import mark_pending
    from hamilton_harness.standin import NotesModel

    root = tmp_path / "assistant"
    write_starter_pack(root, company="Your company", rep="Sam")
    mark_pending(root)
    pack = load_pack(root)
    client = TestClient(create_app(Agent(pack, NotesModel(pack), retry_wait=0), admin_token=TOKEN))
    assert client.get("/api/admin/pack", headers=AUTH).json()["setup_pending"] is True

    answers = {
        "company": "Bloom Florists",
        "rep": "Ivy",
        "knowledge": "## Delivery\nWe deliver across Chennai for ₹150, same day before 2 pm.",
    }
    assert client.post("/api/admin/setup", headers=AUTH, json=answers).status_code == 200
    assert client.get("/api/admin/pack", headers=AUTH).json()["setup_pending"] is False
    assert client.get("/api/config").json()["rep"]["company"] == "Bloom Florists"

    session = client.post("/api/conversations").json()["id"]
    reply = client.post(
        f"/api/conversations/{session}/messages", json={"text": "do you deliver in chennai?"}
    ).json()
    assert "₹150" in reply["bubbles"][0]["text"]
    bot = client.post(f"/api/conversations/{session}/messages", json={"text": "are you a bot?"})
    assert "Ivy" in bot.json()["bubbles"][0]["text"]


def test_a_bad_setup_answer_is_explained(client):
    refused = client.post(
        "/api/admin/setup", headers=AUTH, json={"company": "Acme", "rep": "Jo", "accent": "pink"}
    )
    assert refused.status_code == 422
    assert "hex colour" in refused.json()["detail"]


@pytest.fixture
def public(root, tmp_path):
    """The hosted demo's dashboard: open to anyone, read-only."""
    from hamilton_harness.records import MemoryRecordStore

    order = {
        "product": "Court Classic",
        "size": "9",
        "quantity": 1,
        "customer_name": "Priya",
        "phone": "5550123",
    }
    script = [{"tool": "create_order", "args": order}, "Done.", "Hi! How can I help?"]
    agent = Agent(
        load_pack(root),
        ScriptedModel(script),
        retry_wait=0,
        records=MemoryRecordStore(),
        trace_dir=tmp_path / "traces",
    )
    return create_app(agent, admin_demo=True)


def chat(app, text):
    """One visitor: a browser of their own, which keeps its own cookies."""
    client = TestClient(app)
    session = client.post("/api/conversations").json()["id"]
    client.post(f"/api/conversations/{session}/messages", json={"text": text})
    return client


def test_the_public_dashboard_needs_no_sign_in_and_says_it_is_a_demo(public):
    client = TestClient(public)
    assert client.get("/api/admin/session").json() == {
        "email": None,
        "password": False,
        "demo": True,
    }
    assert client.get("/api/admin/pack").status_code == 200


def test_the_public_dashboard_saves_nothing(public, root):
    client = TestClient(public)
    widget = client.get("/api/admin/pack").json()["widget"]
    refused = client.put("/api/admin/pack/widget", json={**widget, "greeting": "hacked"})
    assert refused.status_code == 403
    assert "read-only demo" in refused.json()["detail"]
    assert client.post("/api/admin/setup", json={"company": "X", "rep": "Y"}).status_code == 403
    assert client.delete("/api/admin/knowledge/faq.md").status_code == 403
    assert "hacked" not in (root / "widget.yaml").read_text(encoding="utf-8")
    # Running the fake customers or trying a tool changes nothing, so a visitor may.
    assert client.post("/api/admin/sim", json={}).status_code == 200
    tried = client.post("/api/admin/tools/lookup_order/try", json={"order_id": "LS-4471"})
    assert tried.status_code == 200 and tried.json()["ok"]
    assert client.put("/api/admin/pack/tools", json=[]).status_code == 403


def test_each_visitor_sees_only_their_own_chats_and_orders(public):
    priya = chat(public, "I want to buy Court Classic in UK 9, I'm Priya")
    arjun = chat(public, "hello there")
    stranger = TestClient(public)

    mine = priya.get("/api/admin/conversations").json()["conversations"]
    assert [c["opening"] for c in mine] == ["I want to buy Court Classic in UK 9, I'm Priya"]
    assert len(priya.get("/api/admin/records").json()["records"]) == 1
    assert priya.get("/api/admin/overview").json()["conversations"]["total"] == 1

    theirs = arjun.get("/api/admin/conversations").json()["conversations"]
    assert [c["opening"] for c in theirs] == ["hello there"]
    assert arjun.get("/api/admin/records").json()["records"] == []
    assert arjun.get(f"/api/admin/conversations/{mine[0]['id']}").status_code == 404

    assert stranger.get("/api/admin/conversations").json()["conversations"] == []
    assert stranger.get("/api/admin/overview").json()["records"]["total"] == 0


def api_tool(**changes):
    tool = {
        "name": "check_stock",
        "description": "Check how many pairs of a shoe are in stock.",
        "http": {"method": "GET", "url": "https://shop.example.com/stock/{product}"},
        "input_schema": {
            "type": "object",
            "properties": {"product": {"type": "string", "description": "Shoe name."}},
            "required": ["product"],
            "additionalProperties": False,
        },
    }
    return {**tool, **changes}


def test_api_tools_are_saved_beside_the_code_ones(client, root):
    assert client.put("/api/admin/pack/tools", headers=AUTH, json=[api_tool()]).status_code == 200
    tools = {t["name"]: t for t in client.get("/api/admin/pack", headers=AUTH).json()["tools"]}
    assert tools["check_stock"]["kind"] == "api"
    assert tools["check_stock"]["http"]["url"].endswith("/stock/{product}")
    assert tools["lookup_order"]["kind"] == "code"
    text = (root / "tools.yaml").read_text(encoding="utf-8")
    assert "handler: handlers:lookup_order" in text and "check_stock" in text

    # Saving the list again replaces the API tools and still keeps the code ones.
    assert client.put("/api/admin/pack/tools", headers=AUTH, json=[]).status_code == 200
    names = {t["name"] for t in client.get("/api/admin/pack", headers=AUTH).json()["tools"]}
    assert "check_stock" not in names and "lookup_order" in names


@pytest.mark.parametrize(
    ("tool", "message"),
    [
        (api_tool(name="lookup_order"), "already a tool called"),
        (api_tool(name="create_order"), "already a tool called"),
        (api_tool(name="Check Stock"), "lower case"),
        (api_tool(http=None, handler="handlers:lookup_order"), "only API tools"),
        (
            api_tool(http={"url": "https://x.example/stock"}, input_schema={"type": "nonsense"}),
            "inputs are not valid",
        ),
        (api_tool(http={"url": "https://x.example/{size}"}), "not one of its inputs"),
    ],
)
def test_a_bad_api_tool_is_refused_with_the_reason(client, root, tool, message):
    before = (root / "tools.yaml").read_text(encoding="utf-8")
    refused = client.put("/api/admin/pack/tools", headers=AUTH, json=[tool])
    assert refused.status_code == 422
    assert message in refused.json()["detail"]
    assert (root / "tools.yaml").read_text(encoding="utf-8") == before


def test_a_tool_can_be_tried_from_the_dashboard(client):
    tried = client.post(
        "/api/admin/tools/lookup_order/try", headers=AUTH, json={"order_id": "LS-4471"}
    ).json()
    assert tried["ok"] and "LS-4471" in tried["result"]
    wrong = client.post("/api/admin/tools/lookup_order/try", headers=AUTH, json={"order": 1})
    assert wrong.json()["ok"] is False and "Invalid arguments" in wrong.json()["result"]
    assert client.post("/api/admin/tools/nope/try", headers=AUTH, json={}).status_code == 404
    record = client.post("/api/admin/tools/create_order/try", headers=AUTH, json={})
    assert record.status_code == 422
