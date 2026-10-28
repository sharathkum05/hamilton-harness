import json

from conftest import DEMO_PACK

from hamilton_harness.cli import main


def test_validate_describes_the_pack(capsys):
    assert main(["validate", str(DEMO_PACK)]) == 0
    out = capsys.readouterr().out
    assert "Maya at Loop Sneakers" in out
    assert "rules      6 (4 enforced in code)" in out
    assert "scenarios  16" in out


def test_init_writes_a_pack_that_validates_and_passes(tmp_path, capsys):
    target = tmp_path / "acme"
    assert main(["init", str(target), "--company", "Acme Tools", "--rep", "Jo"]) == 0
    out = capsys.readouterr().out
    assert "Wrote a starter pack for Acme Tools" in out
    assert "persona.yaml" in out
    assert f"hamilton-harness sim {target}" in out

    assert main(["validate", str(target)]) == 0
    assert "Jo at Acme Tools" in capsys.readouterr().out
    assert main(["sim", str(target)]) == 0
    assert "5/5 scenarios passed" in capsys.readouterr().out


def test_init_will_not_write_over_an_existing_pack(tmp_path, capsys):
    assert main(["init", str(tmp_path), "--company", "Acme Tools"]) == 0
    capsys.readouterr()
    assert main(["init", str(tmp_path), "--company", "Other Co"]) == 2
    assert "not empty" in capsys.readouterr().err
    assert "Acme Tools" in (tmp_path / "persona.yaml").read_text(encoding="utf-8")


def test_init_needs_a_company_name(tmp_path, capsys):
    assert main(["init", str(tmp_path / "pack"), "--company", "  "]) == 2
    assert "company name" in capsys.readouterr().err


def test_validate_is_quiet_about_a_pack_with_nothing_to_report(capsys):
    assert main(["validate", str(DEMO_PACK), "--strict"]) == 0
    assert "second look" not in capsys.readouterr().out


def _pack_with_a_banned_phrase_in_its_greeting(tmp_path):
    target = tmp_path / "acme"
    assert main(["init", str(target), "--company", "Acme Tools"]) == 0
    widget = target / "widget.yaml"
    text = widget.read_text(encoding="utf-8")
    text = text.replace("How can I help?", "As an AI, how can I help?")
    widget.write_text(text, encoding="utf-8")
    return target


def test_validate_lists_warnings_without_failing(tmp_path, capsys):
    target = _pack_with_a_banned_phrase_in_its_greeting(tmp_path)
    capsys.readouterr()
    assert main(["validate", str(target)]) == 0
    out = capsys.readouterr().out
    assert "Pack is valid." in out
    assert "1 thing worth a second look:" in out
    assert 'widget.yaml: greeting: contains the banned phrase "As an AI"' in out


def test_validate_strict_fails_on_a_warning(tmp_path, capsys):
    target = _pack_with_a_banned_phrase_in_its_greeting(tmp_path)
    assert main(["validate", str(target), "--strict"]) == 1


def test_validate_warns_when_a_pack_has_no_fake_customers(tmp_path, capsys):
    target = tmp_path / "acme"
    assert main(["init", str(target), "--company", "Acme Tools"]) == 0
    (target / "tests" / "scenarios.yaml").unlink()
    capsys.readouterr()
    assert main(["validate", str(target)]) == 0
    out = capsys.readouterr().out
    assert "scenarios  none" in out
    assert "tests/scenarios.yaml: is missing" in out


def test_serve_offline_works_for_a_pack_with_no_stand_in_of_its_own(tmp_path):
    from fastapi.testclient import TestClient

    from hamilton_harness.cli import build_parser, build_web_app

    dental = DEMO_PACK.parent / "brightside-dental"
    args = build_parser().parse_args(["serve", str(dental), "--offline", "--state", str(tmp_path)])
    client = TestClient(build_web_app(args))
    session_id = client.post("/api/conversations").json()["id"]
    reply = client.post(
        f"/api/conversations/{session_id}/messages", json={"text": "how much is whitening"}
    ).json()
    assert "₹12,000" in " ".join(b["text"] for b in reply["bubbles"])


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


def test_serve_admin_takes_the_admin_email_and_password(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from hamilton_harness.cli import build_parser, build_web_app

    monkeypatch.setenv("HAMILTON_ADMIN_EMAIL", "owner@shop.com")
    monkeypatch.setenv("HAMILTON_ADMIN_PASSWORD", "a-long-password")
    args = ["serve", str(DEMO_PACK), "--offline", "--admin", "--state", str(tmp_path)]
    client = TestClient(build_web_app(build_parser().parse_args(args)))
    login = {"email": "owner@shop.com", "password": "a-long-password"}
    assert client.post("/api/admin/session", json=login).status_code == 200
    assert client.get("/api/admin/pack").status_code == 200


def test_a_short_admin_password_stops_serve_with_a_message(tmp_path, monkeypatch, capsys):
    from hamilton_harness.cli import main

    monkeypatch.setenv("HAMILTON_ADMIN_PASSWORD", "short")
    code = main(["serve", str(DEMO_PACK), "--offline", "--admin", "--state", str(tmp_path)])
    assert code == 2
    assert "at least 8 characters" in capsys.readouterr().err


def test_studio_makes_a_blank_rep_once_and_serves_it_for_setup(tmp_path, monkeypatch, capsys):
    from fastapi.testclient import TestClient

    import hamilton_harness.cli as cli

    served = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: served.append(app))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("HAMILTON_ADMIN_TOKEN", "tok")
    root = tmp_path / "mine"
    assert cli.main(["studio", str(root), "--state", str(tmp_path / "state")]) == 0
    out = capsys.readouterr().out
    assert "made a blank rep" in out and "stand-in" in out
    assert "/admin" in out and "sign in as admin@hamilton.local" in out
    assert "The setup opens first" in out

    client = TestClient(served[0])
    auth = {"Authorization": "Bearer tok"}
    assert client.get("/api/admin/pack", headers=auth).json()["setup_pending"] is True
    answers = {"company": "Bloom Florists", "rep": "Ivy"}
    assert client.post("/api/admin/setup", headers=auth, json=answers).status_code == 200

    # A second run keeps what was built.
    assert cli.main(["studio", str(root), "--state", str(tmp_path / "state")]) == 0
    out = capsys.readouterr().out
    assert "Bloom Florists from" in out and "The setup opens first" not in out
