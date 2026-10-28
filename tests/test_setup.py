import pytest

from hamilton_harness.lint import lint_pack
from hamilton_harness.pack import PackError, load_pack
from hamilton_harness.scaffold import write_starter_pack
from hamilton_harness.setup import (
    TONES,
    apply_setup,
    mark_pending,
    needs_setup,
    read_answers,
)
from hamilton_harness.sim import load_scenarios, run_scenarios

ANSWERS = {
    "company": "Bloom Florists",
    "rep": "Ivy",
    "role": "orders and delivery",
    "covers": "Bloom Florists only: bouquets, prices, delivery areas and taking orders.",
    "knowledge": "## Delivery\nWe deliver across Chennai for ₹150, same day before 2 pm.",
    "tone": ["friendly", "direct"],
    "emoji": True,
    "greeting": "Hi, I'm Ivy from Bloom. Looking for flowers?",
    "suggestions": ["Do you deliver today?"],
    "accent": "#BE185D",
}


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "assistant"
    write_starter_pack(root, company="Your company", rep="Sam")
    mark_pending(root)
    return root


def test_setup_rebuilds_the_rep_from_the_answers(root):
    assert needs_setup(root)
    pack = apply_setup(root, read_answers(ANSWERS))
    assert not needs_setup(root)
    assert (pack.persona.name, pack.persona.company) == ("Ivy", "Bloom Florists")
    assert pack.persona.role == "orders and delivery"
    assert pack.persona.voice == [TONES["friendly"], TONES["direct"]]
    assert pack.persona.emoji is True
    # The lines that name the company are written for the new one.
    assert "Bloom Florists" in pack.persona.disclosure
    assert "Bloom Florists" in pack.scope.off_topic_reply
    assert pack.scope.covers.startswith("Bloom Florists only")
    assert pack.widget.greeting == ANSWERS["greeting"]
    assert pack.widget.suggestions == ["Do you deliver today?"]
    assert pack.widget.accent == "#be185d"
    assert "₹150" in (root / "knowledge" / "about.md").read_text(encoding="utf-8")
    assert not list(root.parent.glob(".assistant.*"))


def test_a_rep_set_up_from_answers_passes_its_fake_customers_and_lint(root):
    pack = apply_setup(root, read_answers(ANSWERS))
    scenarios = load_scenarios(pack)
    assert "opening-hours" not in {s.id for s in scenarios}
    scorecard = run_scenarios(pack, scenarios)
    assert scorecard.passed == len(scenarios)
    assert lint_pack(pack, scenarios) == []
    # Nothing left over quotes the starter's made-up opening hours.
    for path in root.rglob("*"):
        if path.is_file():
            assert "9 am to 6 pm" not in path.read_text(encoding="utf-8")


def test_only_names_are_needed(root):
    pack = apply_setup(root, read_answers({"company": "Acme Tools", "rep": "Jo"}))
    assert pack.persona.company == "Acme Tools"
    scorecard = run_scenarios(pack, load_scenarios(pack))
    assert scorecard.passed == len(scorecard.results)


def test_an_uploaded_logo_is_kept(root):
    (root / "brand").mkdir()
    (root / "brand" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    pack = apply_setup(root, read_answers(ANSWERS))
    assert pack.widget.logo == "brand/logo.png"
    assert (root / "brand" / "logo.png").exists()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"accent": "pink"}, "hex colour"),
        ({"company": ""}, "company"),
        ({"rep": "Sam\nmore"}, "cannot be used as a name"),
        ({"tone": ["grumpy"]}, "tone"),
        ({"surprise": 1}, "surprise"),
    ],
)
def test_a_bad_answer_is_refused_and_leaves_the_rep_as_it_was(root, change, message):
    before = (root / "persona.yaml").read_text(encoding="utf-8")
    with pytest.raises(PackError, match=message):
        apply_setup(root, read_answers({**ANSWERS, **change}))
    assert (root / "persona.yaml").read_text(encoding="utf-8") == before
    assert needs_setup(root)
    assert not list(root.parent.glob(".assistant.*"))
    load_pack(root)
