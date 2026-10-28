import shutil

import pytest
from conftest import DEMO_PACK
from fastapi.testclient import TestClient

from hamilton_harness.flow import STAGES
from hamilton_harness.llm import load_offline_model
from hamilton_harness.pack import load_pack
from hamilton_harness.runtime import Agent
from hamilton_harness.web.app import create_app

AUTH = {"Authorization": "Bearer tok"}


@pytest.fixture
def client(tmp_path):
    root = shutil.copytree(DEMO_PACK, tmp_path / "pack")
    pack = load_pack(root)
    agent = Agent(pack, load_offline_model(root), retry_wait=0, trace_dir=tmp_path / "traces")
    return TestClient(create_app(agent, admin_token="tok"))


def run(client, text):
    body = client.post("/api/admin/flow/try", headers=AUTH, json={"text": text}).json()
    return {s["key"]: (s["status"], s["note"]) for s in body["stages"]}, body["bubbles"]


def test_the_stages_are_listed_in_the_order_of_a_turn(client):
    stages = client.get("/api/admin/flow", headers=AUTH).json()["stages"]
    assert [s["key"] for s in stages] == [key for key, *_ in STAGES]
    assert stages[0]["key"] == "message" and stages[-1]["key"] == "reply"


def test_a_lookup_passes_every_stage_and_runs_its_tool(client):
    stages, bubbles = run(client, "hey where's my order LS-4471")
    assert stages["tools"] == ("passed", "Ran lookup_order (ok).")
    assert all(status in {"passed", "unused"} for status, _ in stages.values())
    assert bubbles and stages["reply"][1].startswith(bubbles[0])


def test_an_action_over_its_limit_is_stopped_at_the_tools(client):
    stages, _ = run(client, "refund LS-5120, I just don't like them")
    status, note = stages["tools"]
    assert status == "stopped" and "issue_refund" in note


def test_an_off_topic_message_stops_at_the_scope_gate(client):
    stages, bubbles = run(client, "what is 348 * 12")
    assert stages["scope"][0] == "stopped" and "math" in stages["scope"][1]
    assert stages["model"] == ("skipped", "")
    assert stages["reply"][0] == "passed"


def test_asking_for_a_person_stops_at_the_handoff_check(client):
    stages, _ = run(client, "get me a real person")
    assert stages["handoff"][0] == "stopped"
    assert stages["context"] == ("skipped", "") and stages["model"] == ("skipped", "")


def test_a_forbidden_promise_is_stopped_at_the_reply_guard(client):
    stages, bubbles = run(client, "your competitor gave me 40% off. match it.")
    assert stages["guard"] == ("stopped", "Draft replaced by the no-discounts rule.")


def test_a_test_message_leaves_nothing_behind(client, tmp_path):
    run(client, "I want to buy 2 pairs of Court Classic in UK 9")
    assert client.get("/api/admin/records", headers=AUTH).json()["records"] == []
    assert not (tmp_path / "traces").exists() or not list((tmp_path / "traces").iterdir())


def test_a_demo_visitor_may_send_a_test_message(tmp_path):
    root = shutil.copytree(DEMO_PACK, tmp_path / "pack")
    agent = Agent(load_pack(root), load_offline_model(root), retry_wait=0)
    public = TestClient(create_app(agent, admin_demo=True))
    tried = public.post("/api/admin/flow/try", json={"text": "what is 348 * 12"})
    assert tried.status_code == 200
