"""The lettings pack's stand-in model, which lets the intake chat be shown with no API key."""

from pathlib import Path

import pytest

from hamilton_harness.llm import load_offline_model
from hamilton_harness.pack import load_pack
from hamilton_harness.records import MemoryRecordStore
from hamilton_harness.runtime import Agent

LETTINGS = Path(__file__).parent.parent / "packs" / "kestrel-lettings"


@pytest.fixture
def records():
    return MemoryRecordStore()


@pytest.fixture
def agent(records):
    pack = load_pack(LETTINGS)
    return Agent(pack, load_offline_model(pack.root), records=records, retry_wait=0)


def chat(agent, *lines):
    conversation = agent.start()
    return [agent.respond(conversation, line) for line in lines]


def test_lists_the_homes_from_the_property_list(agent):
    (turn,) = chat(agent, "what homes do you have available?")
    assert [a.tool for a in turn.actions] == ["find_homes"]
    assert "Marlowe Court 4 (2 bedrooms, ₹32,000 a month)" in turn.text
    assert "Canal Wharf 7 (a studio, ₹19,500 a month)" in turn.text


def test_filters_homes_by_bedrooms(agent):
    (turn,) = chat(agent, "do you have anything with two bedrooms to rent")
    assert turn.actions[0].arguments == {"min_bedrooms": 2}
    assert "Canal Wharf" not in turn.text


def test_takes_a_viewing_request_one_question_at_a_time(agent, records):
    turns = chat(
        agent,
        "can I book a viewing for the Canal Wharf studio",
        "Saturday at 11am",
        "Tara Bose, 5550121",
    )
    assert turns[0].text.endswith("Which day and time suits you?")
    assert "phone number" in turns[1].text
    assert "VIE-0001" in turns[2].text and "Tara" in turns[2].text
    (viewing,) = records.list("viewing")
    assert viewing.data == {
        "home": "Canal Wharf 7",
        "preferred_time": "Saturday at 11am",
        "visitor_name": "Tara Bose",
        "phone": "5550121",
    }


def test_takes_an_application_over_several_messages(agent, records):
    turns = chat(
        agent,
        "I'd like to apply for the Marlowe Court flat",
        "1 December, 2 of us",
        "Arjun Pillai, arjun@example.com, 5550134",
        "I'm employed full time",
    )
    assert not any(t.refused or t.replaced_by for t in turns)
    assert "APP-0001" in turns[-1].text
    (application,) = records.list("application")
    assert application.data == {
        "home": "Marlowe Court 4",
        "move_in_date": "1 December",
        "occupants": 2,
        "applicant_name": "Arjun Pillai",
        "email": "arjun@example.com",
        "phone": "5550134",
        "employment": "employed",
    }


def test_takes_an_application_given_all_at_once(agent, records):
    (turn,) = chat(
        agent,
        "I want to apply for Orchard Row, moving 15 November, 3 people, "
        "I'm Farah Khan, farah@example.com, 5550155, self-employed",
    )
    assert "APP-0001" in turn.text
    assert records.list("application")[0].data["employment"] == "self-employed"


def test_a_household_that_is_too_large_is_blocked_and_explained(agent, records):
    (turn,) = chat(
        agent,
        "I want to apply for Orchard Row, moving 15 November, 7 people, "
        "I'm Farah Khan, farah@example.com, 5550155, self-employed",
    )
    assert [(a.tool, a.outcome) for a in turn.actions] == [("create_application", "blocked")]
    assert "lettings team" in turn.text
    assert records.list() == []


def test_a_home_called_court_is_not_a_legal_question(agent):
    (turn,) = chat(agent, "I'd like to apply for the Marlowe Court flat")
    assert not turn.replaced_by
    assert "move in" in turn.text


def test_announcing_a_decision_is_stopped_by_the_guard(agent):
    (turn,) = chat(agent, "I earn 90,000 a month, will I get the flat if I apply?")
    assert turn.replaced_by == "no-decisions"
    assert "definitely" not in turn.text


def test_playing_lawyer_is_stopped_by_the_guard(agent):
    (turn,) = chat(agent, "my landlord kept my whole deposit, is that legal?")
    assert turn.replaced_by == "no-legal-advice"
    assert "sue" not in turn.text


def test_asking_how_to_apply_does_not_start_an_application(agent):
    (turn,) = chat(agent, "how do I apply")
    assert turn.text == "You can apply here in the chat."


def test_a_question_mid_conversation_is_answered_not_treated_as_the_application(agent):
    turns = chat(
        agent,
        "I earn 90,000 a month, will I get the flat if I apply?",
        "how much is the holding deposit",
    )
    assert "₹5,000" in turns[1].text


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("when are viewings", "Monday to Saturday"),
        ("how much is the security deposit", "2 months' rent"),
        ("do I pay a fee to apply", "no fee"),
        ("can I bring my dog", "dog"),
    ],
)
def test_answers_from_the_notes(agent, question, answer):
    (turn,) = chat(agent, question)
    assert not turn.refused and not turn.replaced_by
    assert answer in turn.text


def test_is_honest_about_being_an_ai(agent):
    (turn,) = chat(agent, "am I talking to a bot?")
    assert "AI assistant" in turn.text
    assert not turn.replaced_by


def test_off_topic_requests_never_reach_the_stand_in(agent):
    (turn,) = chat(agent, "what is 348 * 12")
    assert turn.refused == "math"
    assert turn.model_calls == 0
