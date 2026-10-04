import json

from conftest import DEMO_PACK

from repkit.cli import main


def test_validate_describes_the_pack(capsys):
    assert main(["validate", str(DEMO_PACK)]) == 0
    out = capsys.readouterr().out
    assert "Maya at Loop Sneakers" in out
    assert "rules      5 (3 enforced in code)" in out
    assert "scenarios  13" in out


def test_validate_reports_a_broken_pack(tmp_path, capsys):
    assert main(["validate", str(tmp_path)]) == 2
    assert "persona.yaml is missing" in capsys.readouterr().err


def test_sim_replay_passes_and_exits_zero(capsys):
    assert main(["sim", str(DEMO_PACK)]) == 0
    out = capsys.readouterr().out
    assert "mode: replay" in out
    assert "13/13 scenarios passed" in out


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

    from repkit.cli import build_parser, build_web_app

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
