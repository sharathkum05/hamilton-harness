import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hamilton_harness import demo
from hamilton_harness.cli import main
from hamilton_harness.pack import PackError

PACKS = Path(__file__).parent.parent / "packs"
TOKEN = "demo-token"


@pytest.fixture
def sites(tmp_path):
    return demo.prepare(demo.find_packs(PACKS), tmp_path / "state", first_port=9100, keep=False)


def test_finds_every_pack_in_the_folder():
    names = [p.name for p in demo.find_packs(PACKS)]
    assert names == ["brightside-dental", "kestrel-lettings", "loop-sneakers"]


def test_finds_nothing_in_a_missing_folder(tmp_path):
    assert demo.find_packs(tmp_path / "nope") == []


def test_each_pack_gets_its_own_copy_and_port(sites, tmp_path):
    assert [(s.name, s.port) for s in sites] == [
        ("brightside-dental", 9100),
        ("kestrel-lettings", 9101),
        ("loop-sneakers", 9102),
    ]
    for site in sites:
        assert site.pack_dir == tmp_path / "state" / site.name / "pack"
        assert (site.pack_dir / "persona.yaml").is_file()
        assert (site.folder / demo.MARKER).is_file()
        assert Path(site.pack.root) == site.pack_dir.resolve()


def test_a_fresh_run_throws_away_last_time(tmp_path):
    state = tmp_path / "state"
    (site,) = demo.prepare([PACKS / "loop-sneakers"], state, first_port=9100, keep=False)
    (site.pack_dir / "persona.yaml").write_text("name: Edited\\n", encoding="utf-8")
    (site.folder / "records.json").write_text("[]", encoding="utf-8")

    (again,) = demo.prepare([PACKS / "loop-sneakers"], state, first_port=9100, keep=False)
    assert again.pack.persona.name == "Maya"
    assert not (again.folder / "records.json").exists()


def test_keep_carries_on_from_last_time(tmp_path):
    state = tmp_path / "state"
    (site,) = demo.prepare([PACKS / "loop-sneakers"], state, first_port=9100, keep=False)
    persona = site.pack_dir / "persona.yaml"
    persona.write_text(persona.read_text(encoding="utf-8").replace("Maya", "Mira"), "utf-8")

    (again,) = demo.prepare([PACKS / "loop-sneakers"], state, first_port=9100, keep=True)
    assert again.pack.persona.name == "Mira"


def test_the_packs_in_the_repository_are_never_touched(sites):
    loop = next(s for s in sites if s.name == "loop-sneakers")
    persona = loop.pack_dir / "persona.yaml"
    persona.write_text(persona.read_text(encoding="utf-8").replace("Maya", "Mira"), "utf-8")
    assert "name: Maya" in (PACKS / "loop-sneakers" / "persona.yaml").read_text(encoding="utf-8")


def test_a_folder_it_did_not_make_is_never_deleted(tmp_path):
    state = tmp_path / "state"
    precious = state / "loop-sneakers"
    precious.mkdir(parents=True)
    (precious / "notes.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(PackError, match="was not made by a demo"):
        demo.prepare([PACKS / "loop-sneakers"], state, first_port=9100, keep=False)
    assert (precious / "notes.txt").read_text(encoding="utf-8") == "keep me"


def test_a_broken_pack_fails_before_anything_is_copied(tmp_path):
    broken = tmp_path / "broken"
    broken.mkdir()
    with pytest.raises(PackError, match="persona.yaml is missing"):
        demo.prepare([broken], tmp_path / "state", first_port=9100, keep=False)
    assert not (tmp_path / "state").exists()


def test_two_packs_with_the_same_folder_name_are_refused(tmp_path):
    with pytest.raises(PackError, match="share a folder name"):
        demo.prepare(
            [PACKS / "loop-sneakers", PACKS / "loop-sneakers"],
            tmp_path / "state",
            first_port=9100,
            keep=False,
        )


def test_no_packs_is_explained(tmp_path):
    with pytest.raises(PackError, match="no packs to show"):
        demo.prepare([], tmp_path / "state", first_port=9100, keep=False)


def test_every_rep_answers_with_no_api_key(sites):
    asked = {
        "brightside-dental": ("how much is whitening", "12,000"),
        "kestrel-lettings": ("what homes do you have available?", "Marlowe Court"),
        "loop-sneakers": ("where is my order LS-4471", "on the way"),
    }
    for site in sites:
        client = TestClient(demo.build_app(site, live=False, admin_token=TOKEN))
        assert client.get("/api/config").json()["debug"] is True
        session_id = client.post("/api/conversations").json()["id"]
        question, expected = asked[site.name]
        reply = client.post(f"/api/conversations/{session_id}/messages", json={"text": question})
        text = " ".join(bubble["text"] for bubble in reply.json()["bubbles"])
        assert expected in text, (site.name, text)


def test_dashboard_edits_land_in_the_copy(sites):
    dental = next(s for s in sites if s.name == "brightside-dental")
    client = TestClient(demo.build_app(dental, live=False, admin_token=TOKEN))
    headers = {"Authorization": f"Bearer {TOKEN}"}
    saved = client.put("/api/admin/pack/widget", headers=headers, json={"greeting": "Hello there."})
    assert saved.status_code == 200, saved.text
    assert "Hello there." in (dental.pack_dir / "widget.yaml").read_text(encoding="utf-8")
    original = (PACKS / "brightside-dental" / "widget.yaml").read_text(encoding="utf-8")
    assert "Hello there." not in original


def test_records_and_traces_stay_in_each_reps_folder(sites):
    lettings = next(s for s in sites if s.name == "kestrel-lettings")
    client = TestClient(demo.build_app(lettings, live=False, admin_token=TOKEN))
    session_id = client.post("/api/conversations").json()["id"]
    for line in [
        "can I book a viewing for the Canal Wharf studio",
        "Saturday at 11am",
        "Tara Bose, 5550121",
    ]:
        client.post(f"/api/conversations/{session_id}/messages", json={"text": line})
    assert "VIE-0001" in (lettings.folder / "records.json").read_text(encoding="utf-8")
    assert list((lettings.folder / "traces").glob("*.jsonl"))


def test_describe_lists_every_rep_and_dashboard(sites):
    text = demo.describe(sites, host="127.0.0.1", live=False, admin_token=TOKEN)
    assert "3 reps, using a stand-in for the model, no API key" in text
    assert "Brightside Dental  Asha, front desk" in text
    assert "http://127.0.0.1:9102" in text
    for site in sites:
        assert f"http://127.0.0.1:{site.port}/admin#token={TOKEN}" in text
    assert "/example" in text


def test_describe_says_how_to_sign_in(sites):
    from hamilton_harness.web.auth import AdminLogin

    login = AdminLogin("admin@hamilton.local", "pw-shown-once", False)
    text = demo.describe(sites, host="127.0.0.1", live=False, admin_token=TOKEN, login=login)
    assert "sign in as admin@hamilton.local, password: pw-shown-once" in text
    assert "Dashboards, already signed in:" in text


def test_describe_says_when_the_real_model_is_used(sites):
    assert "using the real model" in demo.describe(
        sites[:1], host="127.0.0.1", live=True, admin_token=TOKEN
    )


def test_a_port_in_use_is_found():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        assert demo.busy_ports("127.0.0.1", [port]) == [port]


def test_the_command_prepares_and_serves_every_pack(tmp_path, monkeypatch, capsys):
    served = []

    async def fake_serve_all(apps, host):
        served.extend((port, host) for _, port in apps)

    monkeypatch.setattr(demo, "serve_all", fake_serve_all)
    monkeypatch.setattr(demo, "busy_ports", lambda host, ports: [])
    monkeypatch.setenv("HAMILTON_ADMIN_TOKEN", TOKEN)
    monkeypatch.chdir(PACKS.parent)
    state = tmp_path / "state"
    assert main(["demo", "--port", "9200", "--state", str(state)]) == 0
    assert served == [(9200, "127.0.0.1"), (9201, "127.0.0.1"), (9202, "127.0.0.1")]
    out = capsys.readouterr().out
    assert "Hamilton demo: 3 reps" in out
    assert f"http://127.0.0.1:9200/admin#token={TOKEN}" in out


def test_the_command_can_show_chosen_packs(tmp_path, monkeypatch, capsys):
    served = []

    async def fake_serve_all(apps, host):
        served.extend(port for _, port in apps)

    monkeypatch.setattr(demo, "serve_all", fake_serve_all)
    monkeypatch.setattr(demo, "busy_ports", lambda host, ports: [])
    pack = str(PACKS / "kestrel-lettings")
    assert main(["demo", pack, "--port", "9300", "--state", str(tmp_path / "s")]) == 0
    assert served == [9300]
    assert "1 rep, using" in capsys.readouterr().out


def test_the_command_stops_when_a_port_is_taken(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(demo, "busy_ports", lambda host, ports: [ports[1]])
    monkeypatch.chdir(PACKS.parent)
    assert main(["demo", "--port", "9400", "--state", str(tmp_path / "s")]) == 2
    err = capsys.readouterr().err
    assert "port 9401 is already in use" in err
    assert "3 ports in a row" in err
    assert not (tmp_path / "s").exists()


def test_live_needs_an_api_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["demo", "--live", "--state", str(tmp_path / "s")]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_the_demo_lets_a_listed_site_embed_the_chat(sites):
    app = demo.build_app(
        sites[0], live=False, admin_token=TOKEN, allow_origins=["https://shop.example"]
    )
    client = TestClient(app)
    allowed = client.get("/api/config", headers={"Origin": "https://shop.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://shop.example"
    other = client.get("/api/config", headers={"Origin": "https://elsewhere.example"})
    assert "access-control-allow-origin" not in other.headers
