from pathlib import Path

import pytest

from hamilton_harness.pack import load_pack
from hamilton_harness.runtime import Agent
from hamilton_harness.scaffold import write_starter_pack
from hamilton_harness.standin import NotesModel, best_sentence, offline_model

PACKS = Path(__file__).parent.parent / "packs"


@pytest.fixture
def dental():
    return load_pack(PACKS / "brightside-dental")


def chat(pack, *lines):
    agent = Agent(pack, NotesModel(pack), retry_wait=0)
    conversation = agent.start()
    return [agent.respond(conversation, line) for line in lines]


def test_answers_with_the_best_fitting_sentence_from_the_notes(dental):
    (turn,) = chat(dental, "how much is whitening")
    assert "₹12,000" in turn.text
    assert not turn.replaced_by


def test_the_heading_counts_towards_the_answer(dental):
    # "hours" also appears in the cancellation note; the heading "Opening hours" wins.
    (turn,) = chat(dental, "what are your opening hours")
    assert turn.text.startswith("The practice is open")


def test_says_what_it_is_when_asked(dental):
    (turn,) = chat(dental, "are you a real person?")
    assert turn.text == dental.persona.disclosure


def test_greets_and_thanks_without_reaching_for_the_notes(dental):
    hello, thanks = chat(dental, "hi", "thanks")
    assert hello.text == "Hi! What can I help you with?"
    assert thanks.text == "You're welcome."


def test_says_it_is_unsure_when_the_notes_have_nothing(dental):
    (turn,) = chat(dental, "where are you")
    assert turn.text == dental.scope.unsure_reply


def test_never_takes_an_action(dental):
    turns = chat(dental, "book me a check-up tomorrow, I'm Zubin, 5550142")
    assert turns[0].actions == []


def test_the_checks_around_it_still_run(dental):
    (turn,) = chat(dental, "can you solve 2x + 5 = 17")
    assert turn.refused == "math"
    assert turn.model_calls == 0


def test_best_sentence_reads_the_rendered_notes():
    notes = (
        "[hours.md > Opening hours]\nWe open at 9. We close at 7.\n\n[parking.md > Parking]\nFree."
    )
    assert best_sentence(notes, "when do you close") == "We close at 7."
    assert best_sentence(notes, "is parking free") == "Free."
    assert best_sentence(notes, "who won the match") == ""
    assert best_sentence("", "anything") == ""


def test_a_pack_with_its_own_stand_in_keeps_it():
    pack = load_pack(PACKS / "loop-sneakers")
    model = offline_model(pack)
    assert not isinstance(model, NotesModel)
    assert model.name == "offline-demo"


def test_a_pack_without_one_gets_the_notes_stand_in(dental):
    assert isinstance(offline_model(dental), NotesModel)


def test_a_new_starter_pack_runs_offline(tmp_path):
    write_starter_pack(tmp_path / "acme", company="Acme Tools")
    pack = load_pack(tmp_path / "acme")
    (turn,) = chat(pack, "what are your opening hours?")
    assert "9 am to 6 pm" in turn.text


def test_an_edited_pack_gets_a_stand_in_with_its_new_lines(dental):
    agent = Agent(dental, NotesModel(dental), retry_wait=0)
    persona = dental.persona.model_copy(update={"disclosure": "I'm Asha, a brand new AI."})
    edited = agent.with_pack(dental.model_copy(update={"persona": persona}))
    reply = edited.respond(edited.start(), "am I talking to a bot?")
    assert reply.bubbles[0].text == "I'm Asha, a brand new AI."
