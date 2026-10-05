import pytest

from hamilton_harness.pack import PackError, load_pack
from hamilton_harness.scaffold import TEMPLATE, write_starter_pack
from hamilton_harness.sim import load_scenarios, run_scenarios
from hamilton_harness.tools import ToolRegistry


def test_starter_pack_loads_with_the_names_given(tmp_path):
    write_starter_pack(tmp_path / "acme", company="Acme Tools", rep="Jo")
    pack = load_pack(tmp_path / "acme")
    assert pack.persona.name == "Jo"
    assert pack.persona.company == "Acme Tools"
    assert "Jo" in pack.persona.disclosure
    assert "Acme Tools" in pack.scope.covers
    assert pack.widget.greeting == "Hi, I'm Jo from Acme Tools. How can I help?"


def test_starter_pack_writes_every_template_file(tmp_path):
    written = write_starter_pack(tmp_path / "acme", company="Acme Tools")
    names = {str(path.relative_to(tmp_path / "acme")) for path in written}
    expected = {str(p.relative_to(TEMPLATE)) for p in TEMPLATE.rglob("*") if p.is_file()}
    assert names == expected
    assert "tests/scenarios.yaml" in names


def test_starter_pack_leaves_no_placeholder_behind(tmp_path):
    for path in write_starter_pack(tmp_path / "acme", company="Acme Tools"):
        assert "__" not in path.read_text(encoding="utf-8"), path.name


def test_starter_pack_can_take_an_enquiry(tmp_path):
    write_starter_pack(tmp_path / "acme", company="Acme Tools")
    pack = load_pack(tmp_path / "acme")
    assert ToolRegistry(pack).names() == ["create_enquiry"]


def test_starter_pack_passes_its_own_fake_customers(tmp_path):
    write_starter_pack(tmp_path / "acme", company="Acme Tools")
    pack = load_pack(tmp_path / "acme")
    scorecard = run_scenarios(pack, load_scenarios(pack))
    assert scorecard.ok, scorecard.render()
    assert scorecard.summary()["off_topic_refused"] == 1


@pytest.mark.parametrize(
    "company",
    ['Acme: "Tools" & Co', "O'Brien's Bakery", "Café Zürich #2", "{braces} [and] brackets"],
)
def test_awkward_company_names_survive_the_yaml(tmp_path, company):
    write_starter_pack(tmp_path / "pack", company=company)
    pack = load_pack(tmp_path / "pack")
    assert pack.persona.company == company
    assert company in pack.scope.off_topic_reply


def test_names_are_trimmed(tmp_path):
    write_starter_pack(tmp_path / "pack", company="  Acme Tools ", rep=" Jo ")
    pack = load_pack(tmp_path / "pack")
    assert (pack.persona.company, pack.persona.name) == ("Acme Tools", "Jo")


def test_refuses_a_folder_that_already_has_files(tmp_path):
    (tmp_path / "persona.yaml").write_text("name: Existing\n", encoding="utf-8")
    with pytest.raises(PackError, match="not empty"):
        write_starter_pack(tmp_path, company="Acme Tools")
    assert (tmp_path / "persona.yaml").read_text(encoding="utf-8") == "name: Existing\n"


def test_writes_into_an_empty_folder(tmp_path):
    assert write_starter_pack(tmp_path, company="Acme Tools")
    assert (tmp_path / "persona.yaml").exists()


def test_refuses_a_path_that_is_a_file(tmp_path):
    target = tmp_path / "pack"
    target.write_text("not a folder", encoding="utf-8")
    with pytest.raises(PackError, match="not a folder"):
        write_starter_pack(target, company="Acme Tools")


@pytest.mark.parametrize("company", ["", "   ", "two\nlines", "__REP__"])
def test_refuses_names_that_cannot_be_used(tmp_path, company):
    with pytest.raises(PackError):
        write_starter_pack(tmp_path / "pack", company=company)
    assert not (tmp_path / "pack").exists()


def test_refuses_an_empty_rep_name(tmp_path):
    with pytest.raises(PackError, match="name for the rep"):
        write_starter_pack(tmp_path / "pack", company="Acme Tools", rep=" ")
