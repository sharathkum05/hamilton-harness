import pytest
from fastapi.testclient import TestClient

from repkit.llm import ScriptedModel
from repkit.runtime import Agent
from repkit.web.app import create_app


def make_client(pack, steps=(), **kwargs):
    agent = Agent(pack, ScriptedModel(list(steps)), retry_wait=0)
    return TestClient(create_app(agent, **kwargs))


@pytest.fixture
def client(pack):
    return make_client(pack)


def start(client):
    response = client.post("/api/conversations")
    assert response.status_code == 201
    return response.json()["id"]


def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_config_describes_the_rep_and_widget(client, pack):
    config = client.get("/api/config").json()
    assert config["rep"] == {"name": "Maya", "company": "Loop Sneakers", "role": "customer support"}
    assert config["disclosure"] == "AI assistant"
    assert config["widget"]["accent"] == pack.widget.accent
    assert config["widget"]["logo_url"].startswith("/brand/logo?v=")
    assert "logo" not in config["widget"]
    assert config["widget"]["theme"] == "auto"
    assert len(config["widget"]["suggestions"]) == 4
    assert config["debug"] is False


def test_config_does_not_leak_rules_or_tools(client):
    body = client.get("/api/config").text
    assert "refund-limit" not in body
    assert "issue_refund" not in body
    assert "banned_phrases" not in body


def test_new_conversation_opens_with_the_greeting(client, pack):
    created = client.post("/api/conversations").json()
    assert created["transcript"] == [{"from": "rep", "text": pack.widget.greeting}]
    assert created["handed_off"] is False


def test_conversation_can_be_fetched_again(client):
    session_id = start(client)
    assert client.get(f"/api/conversations/{session_id}").json()["id"] == session_id


def test_unknown_conversation_is_404(client):
    assert client.get("/api/conversations/nope").status_code == 404


def test_api_docs_are_not_served(client):
    assert client.get("/docs").status_code == 404


LOOKUP = {"tool": "lookup_order", "args": {"order_id": "LS-4471"}}


def send(client, session_id, text):
    return client.post(f"/api/conversations/{session_id}/messages", json={"text": text})


def test_message_returns_paced_bubbles(pack):
    client = make_client(pack, [LOOKUP, "Found it, Priya. It's due Thursday 8 October."])
    session_id = start(client)
    body = send(client, session_id, "where is LS-4471").json()
    assert body["bubbles"][0]["text"].startswith("Found it, Priya.")
    assert body["bubbles"][0]["delay"] > 0
    assert body["handed_off"] is False
    assert "debug" not in body


def test_transcript_records_both_sides(pack):
    client = make_client(pack, ["Hi! What's the order number?"])
    session_id = start(client)
    send(client, session_id, "  hello  ")
    transcript = client.get(f"/api/conversations/{session_id}").json()["transcript"]
    assert [m["from"] for m in transcript] == ["rep", "customer", "rep"]
    assert transcript[1]["text"] == "hello"


def test_handoff_is_reported(pack):
    client = make_client(pack)
    session_id = start(client)
    body = send(client, session_id, "get me a real person").json()
    assert body["handed_off"] is True
    assert body["bubbles"][0]["text"] == pack.handoff.message
    assert client.get(f"/api/conversations/{session_id}").json()["handed_off"] is True


@pytest.mark.parametrize("payload", [{"text": ""}, {"text": "   "}, {"text": "x" * 2001}, {}])
def test_bad_messages_are_rejected(client, payload):
    session_id = start(client)
    response = client.post(f"/api/conversations/{session_id}/messages", json=payload)
    assert response.status_code == 422


def test_message_to_unknown_conversation_is_404(client):
    assert send(client, "nope", "hi").status_code == 404


def test_a_second_message_mid_turn_is_refused(pack):
    client = make_client(pack, ["Hello!"])
    session_id = start(client)
    session = client.app.state.sessions.get(session_id)
    with session.lock:
        assert send(client, session_id, "hi").status_code == 409
    assert send(client, session_id, "hi").status_code == 200


def test_the_lock_is_released_when_a_turn_crashes(pack):
    def explode(messages):
        raise RuntimeError("bug")

    client = TestClient(
        create_app(Agent(pack, ScriptedModel([explode, "Hello!"]), retry_wait=0)),
        raise_server_exceptions=False,
    )
    session_id = start(client)
    assert send(client, session_id, "hi").status_code == 500
    assert send(client, session_id, "hi again").status_code == 200


def test_debug_mode_explains_the_turn(pack):
    refund = {
        "tool": "issue_refund",
        "args": {"order_id": "LS-6033", "amount_inr": 4199, "reason": "damaged"},
    }
    client = make_client(pack, [refund], debug=True)
    session_id = start(client)
    debug = send(client, session_id, "refund my damaged trail loops LS-6033").json()["debug"]
    assert debug["context"]["rules"] == ["refund-limit", "refund-reasons"]
    assert debug["actions"][0]["outcome"] == "blocked"
    assert debug["actions"][0]["rules"] == ["refund-limit"]
    assert debug["handoff"]["reason"] == "guard"
    assert debug["model_calls"] == 1


def test_trace_is_hidden_unless_debug_is_on(pack):
    client = make_client(pack, ["Hello!"])
    session_id = start(client)
    send(client, session_id, "hi")
    assert client.get(f"/api/conversations/{session_id}/trace").status_code == 404


def test_trace_lists_every_turn_in_debug_mode(pack):
    client = make_client(pack, [LOOKUP, "Due Thursday.", "Anytime!"], debug=True)
    session_id = start(client)
    send(client, session_id, "where is LS-4471")
    send(client, session_id, "thanks")
    turns = client.get(f"/api/conversations/{session_id}/trace").json()["turns"]
    assert len(turns) == 2
    assert [e["kind"] for e in turns[0]] == [
        "customer",
        "context",
        "model",
        "action",
        "model",
        "shaped",
        "turn_end",
    ]


def test_cross_origin_requests_are_refused_by_default(client):
    response = client.get("/api/config", headers={"Origin": "https://shop.example"})
    assert "access-control-allow-origin" not in response.headers


def test_listed_origins_may_embed_the_widget(pack):
    client = make_client(pack, allow_origins=["https://shop.example"])
    allowed = client.get("/api/config", headers={"Origin": "https://shop.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://shop.example"
    other = client.get("/api/config", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_demo_page_and_widget_assets_are_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert 'src="/widget.js"' in page.text
    script = client.get("/widget.js")
    assert script.headers["content-type"].startswith("text/javascript")
    assert "repkit:turn" in script.text


def test_chat_page_is_served_from_the_built_app(pack, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "index.js").write_text("console.log(1)", encoding="utf-8")
    client = make_client(pack, app_dir=tmp_path)
    page = client.get("/chat")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-cache"
    assert client.get("/app/assets/index.js").status_code == 200


def test_chat_page_explains_a_missing_build(pack, tmp_path):
    client = make_client(pack, app_dir=tmp_path / "missing")
    response = client.get("/chat")
    assert response.status_code == 503
    assert "npm --prefix web" in response.json()["detail"]


def test_logo_is_served_as_a_sandboxed_image(client):
    response = client.get("/brand/logo")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_pack_without_a_logo(pack):
    bare = pack.model_copy(update={"widget": pack.widget.model_copy(update={"logo": ""})})
    client = TestClient(create_app(Agent(bare, ScriptedModel([]), retry_wait=0)))
    assert client.get("/api/config").json()["widget"]["logo_url"] == ""
    assert client.get("/brand/logo").status_code == 404
