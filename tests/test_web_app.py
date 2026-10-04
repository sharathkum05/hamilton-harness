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
