import pytest

from repkit.handoff import HandoffDetector
from repkit.pack.schema import HandoffRules


@pytest.fixture
def detector(pack):
    return HandoffDetector(pack.handoff)


@pytest.mark.parametrize(
    "text",
    [
        "I want to talk to a human",
        "can i speak with your manager",
        "get me a real person",
        "just transfer me to a supervisor already",
        "human please",
    ],
)
def test_asking_for_a_person_hands_off(detector, text):
    decision = detector.check_message(text)
    assert decision is not None
    assert decision.reason == "requested"


@pytest.mark.parametrize(
    "text",
    [
        "are you a real person?",
        "r u a bot",
        "is this a human I'm talking to",
        "where is my order",
        "I need a bigger size",
        "can you get the manager's special in black",
    ],
)
def test_ordinary_messages_do_not_hand_off(detector, text):
    assert detector.check_message(text) is None


def test_trigger_phrases_hand_off(detector):
    decision = detector.check_message("If this isn't fixed I'm filing a CHARGEBACK.")
    assert decision.reason == "phrase"
    assert decision.detail == "chargeback"


def test_phrases_match_whole_words_only():
    detector = HandoffDetector(HandoffRules(phrases=["fraud"]))
    assert detector.check_message("the fraudster line was funny") is None


def test_requests_can_be_switched_off():
    detector = HandoffDetector(HandoffRules(on_request=False))
    assert detector.check_message("I want to talk to a human") is None


def test_repeated_guard_blocks_hand_off(detector):
    assert detector.check_guard_blocks(1) is None
    assert detector.check_guard_blocks(2).reason == "guard"


def test_decisions_carry_the_pack_message(detector, pack):
    assert detector.for_error("model timeout").message == pack.handoff.message
