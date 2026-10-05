import pytest
from pydantic import ValidationError

from hamilton_harness.context import ContextBuilder, TurnContext
from hamilton_harness.pack.schema import ScopeSettings
from hamilton_harness.scope import ScopeGate, evidence_text, ungrounded_numbers

EMPTY = TurnContext()


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("what is 25 * 4", "math"),
        ("solve 2x + 3 = 7 for me", "math"),
        ("what's 15% of 300", "math"),
        ("write a python script to scrape a website", "coding"),
        ("can you debug this javascript function", "coding"),
        ("write me a poem about autumn", "writing"),
        ("tell me a joke", "writing"),
        ("what is the capital of France", "trivia"),
        ("who won the world cup in 2022", "trivia"),
        ("translate good morning into Spanish", "trivia"),
    ],
)
def test_off_topic_requests_are_refused(message, reason):
    verdict = ScopeGate(ScopeSettings()).check(message, EMPTY)
    assert not verdict.in_scope
    assert verdict.reason == reason


@pytest.mark.parametrize(
    "message",
    [
        "where is my order LS-4471",
        "I was charged twice",
        "do you have the drift runner in size 9",
        "how long does delivery take",
        "hi",
        "thanks!",
    ],
)
def test_ordinary_messages_are_in_scope(pack, message):
    context = ContextBuilder(pack).for_turn(message, {})
    assert ScopeGate(pack.scope).check(message, context).in_scope


def test_sums_about_the_companys_own_prices_are_allowed(pack):
    message = "what is 2 x 2499 plus delivery charges for two pairs"
    context = ContextBuilder(pack).for_turn(message, {})
    assert context.notes
    assert ScopeGate(pack.scope).check(message, context).in_scope


def test_poems_are_refused_even_about_the_companys_products(pack):
    message = "write a poem about returning shoes"
    context = ContextBuilder(pack).for_turn(message, {})
    assert context.notes
    assert ScopeGate(pack.scope).check(message, context).reason == "writing"


def test_detectors_can_be_switched_off():
    gate = ScopeGate(ScopeSettings(refuse=["coding"]))
    assert gate.check("what is 25 * 4", EMPTY).in_scope
    assert not gate.check("write some python code", EMPTY).in_scope


def test_custom_patterns_are_refused():
    gate = ScopeGate(ScopeSettings(also_refuse=[r"\bcompetitor\b", r"\bpolitic"]))
    assert gate.check("what do you think of your competitor", EMPTY).reason == "custom"
    assert gate.check("who should I vote for in politics", EMPTY).reason == "custom"


def test_custom_patterns_must_compile():
    with pytest.raises(ValidationError, match="is not valid"):
        ScopeSettings(also_refuse=["(unclosed"])


def test_strict_mode_refuses_anything_the_pack_does_not_cover():
    gate = ScopeGate(ScopeSettings(strict=True))
    assert gate.check("what do you think about electric cars", EMPTY).reason == "strict"
    assert ScopeGate(ScopeSettings()).check("what do you think about electric cars", EMPTY).in_scope


@pytest.mark.parametrize("message", ["hello", "thanks so much", "yes please", "are you a bot?"])
def test_strict_mode_still_allows_conversation(message):
    assert ScopeGate(ScopeSettings(strict=True)).check(message, EMPTY).in_scope


def test_strict_mode_allows_an_answer_to_the_reps_question():
    gate = ScopeGate(ScopeSettings(strict=True))
    assert gate.check("Priya Raman", EMPTY, answering=True).in_scope
    assert not gate.check("Priya Raman", EMPTY, answering=False).in_scope


def test_grounded_numbers_pass():
    evidence = "Standard delivery takes 3 to 5 working days. Express costs ₹199. Paid 2,499.00"
    assert ungrounded_numbers("It takes 3 to 5 days and costs ₹199.", evidence) == []
    assert ungrounded_numbers("You paid ₹2,499.", evidence) == []


def test_invented_numbers_are_caught():
    evidence = "Standard delivery takes 3 to 5 working days."
    assert ungrounded_numbers("It arrives in 2 days for ₹1,299.", evidence) == ["1299", "2"]


def test_replies_without_numbers_are_grounded():
    assert ungrounded_numbers("Let me check that for you.", "") == []


def test_evidence_includes_tool_results_and_arguments():
    messages = [
        {"role": "user", "content": "refund order LS-4471"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "issue_refund",
                    "input": {"amount_inr": 2499},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "content": '{"arrives_in": "3 to 5 days"}',
                },
            ],
        },
    ]
    evidence = evidence_text("Keep it to 2 sentences.", messages)
    assert ungrounded_numbers("Refunded ₹2,499 on LS-4471, back in 3 to 5 days.", evidence) == []


def test_bare_arithmetic_is_refused_even_when_a_number_matches_the_notes(pack):
    # The size chart mentions 12, which must not make this an in-scope question.
    message = "what is 348 * 12"
    context = ContextBuilder(pack).for_turn(message, {})
    assert ScopeGate(pack.scope).check(message, context).reason == "math"


def test_strict_mode_needs_more_than_one_shared_word(pack):
    strict = ScopeGate(pack.scope.model_copy(update={"strict": True}))
    off = "tell me about black holes"
    assert strict.check(off, ContextBuilder(pack).for_turn(off, {})).reason == "strict"
    on = "do you have it in black"
    assert strict.check(on, ContextBuilder(pack).for_turn(on, {})).in_scope


@pytest.mark.parametrize(
    "message",
    ["am I talking to a bot?", "am i chatting with a real person", "is this a chatbot"],
)
def test_strict_mode_lets_a_customer_ask_what_they_are_talking_to(message):
    assert ScopeGate(ScopeSettings(strict=True)).check(message, EMPTY).in_scope
