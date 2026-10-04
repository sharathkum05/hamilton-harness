import json

from conftest import DEMO_PACK

from hamilton_harness.cli import main


def test_validate_describes_the_pack(capsys):
    assert main(["validate", str(DEMO_PACK)]) == 0
    out = capsys.readouterr().out
    assert "Maya at Loop Sneakers" in out
    assert "rules      6 (4 enforced in code)" in out
    assert "scenarios  16" in out


def test_validate_reports_a_broken_pack(tmp_path, capsys):
    assert main(["validate", str(tmp_path)]) == 2
    assert "persona.yaml is missing" in capsys.readouterr().err


def test_sim_replay_passes_and_exits_zero(capsys):
    assert main(["sim", str(DEMO_PACK)]) == 0
    out = capsys.readouterr().out
    assert "mode: replay" in out
    assert "16/16 scenarios passed" in out


def test_sim_json_output(capsys):
    assert main(["sim", str(DEMO_PACK), "--json", "--only", "bargain-hunter"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["scenarios"] == 1
    assert report["summary"]["replies_replaced"] == 1
    assert report["failures"] == {"bargain-hunter": []}


def test_sim_exits_nonzero_when_a_scenario_fails(tmp_path, capsys):
    scenarios = tmp_path / "s.yaml"
    scenarios.write_text(
        "- id: wrong\n  says: [hi]\n  replay: ['Hello!']\n  expect: {handoff: true}\n",
        encoding="utf-8",
    )
    assert main(["sim", str(DEMO_PACK), "--scenarios", str(scenarios)]) == 1
    assert "FAIL  wrong" in capsys.readouterr().out


def test_sim_rejects_an_unknown_scenario_id(capsys):
    assert main(["sim", str(DEMO_PACK), "--only", "nope"]) == 2
    assert "no scenario matches" in capsys.readouterr().err


def test_serve_builds_an_offline_app(tmp_path):
    from fastapi.testclient import TestClient

    from hamilton_harness.cli import build_parser, build_web_app

    args = build_parser().parse_args(
        ["serve", str(DEMO_PACK), "--offline", "--debug", "--state", str(tmp_path)]
    )
    client = TestClient(build_web_app(args))
    session_id = client.post("/api/conversations").json()["id"]
    reply = client.post(
        f"/api/conversations/{session_id}/messages", json={"text": "where is LS-4471"}
    ).json()
    assert "Thursday 8 October" in reply["bubbles"][0]["text"]
    assert reply["debug"]["actions"][0]["tool"] == "lookup_order"
    assert list((tmp_path / "traces").glob("*.jsonl"))


def test_admin_token_is_created_once_and_kept_private(tmp_path, monkeypatch):
    from hamilton_harness.cli import admin_token

    monkeypatch.delenv("HAMILTON_ADMIN_TOKEN", raising=False)
    first = admin_token(tmp_path)
    assert len(first) >= 24
    assert admin_token(tmp_path) == first
    assert (tmp_path / "admin-token").stat().st_mode & 0o077 == 0
    monkeypatch.setenv("HAMILTON_ADMIN_TOKEN", "from-env")
    assert admin_token(tmp_path) == "from-env"


def test_serve_admin_switches_the_dashboard_on(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from hamilton_harness.cli import build_parser, build_web_app

    monkeypatch.setenv("HAMILTON_ADMIN_TOKEN", "tok")
    base = ["serve", str(DEMO_PACK), "--offline", "--state", str(tmp_path)]
    on = TestClient(build_web_app(build_parser().parse_args([*base, "--admin"])))
    off = TestClient(build_web_app(build_parser().parse_args(base)))
    headers = {"Authorization": "Bearer tok"}
    assert on.get("/api/admin/pack", headers=headers).status_code == 200
    assert off.get("/api/admin/pack", headers=headers).status_code == 404
