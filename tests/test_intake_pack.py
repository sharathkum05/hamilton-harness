"""The lettings pack: an intake desk that collects details and never decides."""

from pathlib import Path

import pytest

from hamilton_harness.context import ContextBuilder
from hamilton_harness.guard import PolicyGuard
from hamilton_harness.pack import load_pack
from hamilton_harness.records import MemoryRecordStore
from hamilton_harness.scope import ScopeGate
from hamilton_harness.sim import load_scenarios, run_scenarios
from hamilton_harness.tools import ToolRegistry

LETTINGS = Path(__file__).parent.parent / "packs" / "kestrel-lettings"


@pytest.fixture(scope="module")
def lettings():
    return load_pack(LETTINGS)


@pytest.fixture
def guard(lettings):
    return PolicyGuard(lettings.policies, lettings.persona)


def test_pack_loads(lettings):
    assert lettings.persona.name == "Noor"
    assert lettings.scope.strict
    assert [r.tool_name for r in lettings.records] == ["create_application", "create_viewing"]
    assert ToolRegistry(lettings).names() == [
        "create_application",
        "create_viewing",
        "find_homes",
    ]
    assert len(lettings.knowledge) == 4


def test_fake_applicants_all_pass(lettings):
    scorecard = run_scenarios(lettings, load_scenarios(lettings))
    assert scorecard.ok, scorecard.render()
    summary = scorecard.summary()
    assert summary["off_topic_refused"] == 3
    assert summary["actions_blocked"] == 1
    assert summary["replies_replaced"] == 4


def test_find_homes_filters_by_bedrooms_and_rent(lettings):
    registry = ToolRegistry(lettings)
    everything = registry.call("find_homes", {}).data
    assert [h["home"] for h in everything["homes"]] == [
        "Marlowe Court 4",
        "Orchard Row 12",
        "Canal Wharf 7",
    ]
    cheap = registry.call("find_homes", {"max_rent_inr": 20000}).data
    assert [h["home"] for h in cheap["homes"]] == ["Canal Wharf 7"]
    big = registry.call("find_homes", {"min_bedrooms": 3}).data
    assert [h["home"] for h in big["homes"]] == ["Orchard Row 12"]
    nothing = registry.call("find_homes", {"max_rent_inr": 100})
    assert not nothing.ok
    assert "lettings team" in nothing.content


def test_the_notes_and_the_property_list_agree_on_rent(lettings):
    # The grounding check trusts both, so they must not contradict each other.
    notes = next(doc.text for doc in lettings.knowledge if doc.source == "homes.md")
    for home in ToolRegistry(lettings).call("find_homes", {}).data["homes"]:
        assert f"₹{home['rent_inr']:,}" in notes, home["home"]


def test_record_choices_match_the_property_list(lettings):
    listed = {h["home"] for h in ToolRegistry(lettings).call("find_homes", {}).data["homes"]}
    for record in lettings.records:
        home = next(f for f in record.fields if f.name == "home")
        assert set(home.choices) == listed


def test_an_application_lands_in_the_inbox_with_a_reference(lettings):
    store = MemoryRecordStore()
    registry = ToolRegistry(lettings, store)
    result = registry.call(
        "create_application",
        {
            "home": "Marlowe Court 4",
            "move_in_date": "1 December",
            "occupants": 2,
            "applicant_name": "Arjun Pillai",
            "email": "arjun@example.com",
            "phone": "5550134",
            "employment": "employed",
        },
    )
    assert result.ok
    assert result.data["reference"] == "APP-0001"
    assert [r.id for r in store.list("application")] == ["APP-0001"]


@pytest.mark.parametrize("occupants", [0, 5, 7])
def test_a_household_outside_the_limit_is_blocked(guard, occupants):
    verdict = guard.check_action("create_application", {"occupants": occupants})
    assert verdict.action == "block"
    assert verdict.rule_ids == ["occupancy"]


@pytest.mark.parametrize("occupants", [1, 4])
def test_a_household_inside_the_limit_is_allowed(guard, occupants):
    assert guard.check_action("create_application", {"occupants": occupants}).allowed


@pytest.mark.parametrize(
    ("draft", "rule"),
    [
        ("Good news, you've been approved!", "no-decisions"),
        ("With that salary you'll definitely be approved.", "no-decisions"),
        ("You will easily qualify for this one.", "no-decisions"),
        ("Consider it done, the flat is yours.", "no-decisions"),
        ("I'm sorry, you have been declined.", "no-decisions"),
        ("Before we go on, are you married?", "fair-questions"),
        ("What is your nationality?", "fair-questions"),
        ("Are you planning to have children soon?", "fair-questions"),
        ("Orchard Row is better suited to families.", "fair-questions"),
        ("That's illegal.", "no-legal-advice"),
        ("You should sue.", "no-legal-advice"),
        ("By law, your landlord must return it within a month.", "no-legal-advice"),
    ],
)
def test_drafts_that_break_a_rule_are_replaced(guard, lettings, draft, rule):
    verdict = guard.check_reply(draft)
    assert not verdict.ok
    assert verdict.rule_id == rule
    safe = next(r.safe_reply for r in lettings.policies if r.id == rule)
    assert verdict.replacement == safe


@pytest.mark.parametrize(
    "draft",
    [
        "The lettings team will email you once you've been approved or not.",
        "They'll let you know if you're approved within 2 working days.",
        "I can't say whether you would qualify, because the team decides.",
        "You'll get an email with a secure link for your documents.",
        "How many people will live there, and when would you like to move in?",
        "Are you employed, self-employed or studying?",
        "The security deposit is 2 months' rent, returned at the end of the tenancy.",
        "Orchard Row suits up to 4 people.",
    ],
)
def test_honest_drafts_are_left_alone(guard, draft):
    assert guard.check_reply(draft).ok, draft


def test_safe_replies_pass_their_own_rules(guard, lettings):
    for rule in lettings.policies:
        assert guard.check_reply(rule.safe_reply).ok, rule.id
    assert guard.check_reply(lettings.handoff.message).ok
    assert guard.check_reply(lettings.scope.off_topic_reply).ok


@pytest.mark.parametrize(
    "message",
    [
        "what homes do you have with two bedrooms?",
        "is the studio still available",
        "can I bring my dog",
        "how do I apply",
        "how much is the deposit",
        "when can I book a viewing",
    ],
)
def test_ordinary_renting_questions_are_in_scope(lettings, message):
    context = ContextBuilder(lettings).for_turn(message, {})
    assert ScopeGate(lettings.scope).check(message, context).in_scope
