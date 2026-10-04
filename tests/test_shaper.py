from hamilton_harness.pack.schema import Persona
from hamilton_harness.shaper import ReplyShaper, split_sentences, strip_formatting, typing_delay


def persona(**kwargs):
    defaults = {"name": "Maya", "company": "Loop", "max_sentences": 2, "emoji": True}
    return Persona(**{**defaults, **kwargs})


def test_markdown_is_flattened():
    draft = "## Your order\n\n- **Shipped** yesterday\n- Due [Thursday](http://x.test)\n"
    assert strip_formatting(draft) == "Your order. Shipped yesterday. Due Thursday."


def test_dashes_become_commas():
    assert strip_formatting("It shipped — finally — today.") == "It shipped, finally, today."


def test_snake_case_is_not_mistaken_for_emphasis():
    assert strip_formatting("Use order_id and tracking_id.") == "Use order_id and tracking_id."


def test_sentences_split_without_breaking_amounts():
    text = "Refunding Rs. 2,499 now. It lands in 3.5 days! OK?"
    assert split_sentences(text) == ["Refunding Rs. 2,499 now.", "It lands in 3.5 days!", "OK?"]


def test_trailing_emoji_stays_with_its_sentence():
    assert split_sentences("Sent! 👍") == ["Sent! 👍"]


def test_long_reply_is_split_into_bubbles():
    shaped = ReplyShaper(persona()).shape("One. Two. Three. Four. Five.")
    assert [b.text for b in shaped.bubbles] == ["One. Two.", "Three. Four.", "Five."]
    assert shaped.dropped == []


def test_bubbles_are_capped_and_the_rest_is_reported():
    shaped = ReplyShaper(persona(max_sentences=1), max_bubbles=2).shape("One. Two. Three.")
    assert [b.text for b in shaped.bubbles] == ["One.", "Two."]
    assert shaped.dropped == ["Three."]


def test_banned_filler_sentences_are_dropped():
    shaper = ReplyShaper(persona(banned_phrases=["I apologize for the inconvenience"]))
    shaped = shaper.shape("I apologize for the inconvenience! Your order is due Thursday.")
    assert shaped.text == "Your order is due Thursday."
    assert shaped.removed_phrases == ["I apologize for the inconvenience"]


def test_banned_phrase_inside_a_useful_sentence_is_cut_out():
    shaper = ReplyShaper(persona(banned_phrases=["Rest assured"]))
    shaped = shaper.shape("Rest assured, your refund lands Thursday.")
    assert shaped.text == "Your refund lands Thursday."


def test_a_reply_is_never_shaped_down_to_nothing():
    shaper = ReplyShaper(persona(banned_phrases=["Kindly"]))
    assert shaper.shape("Kindly.").bubbles


def test_emoji_are_removed_when_the_persona_forbids_them():
    assert ReplyShaper(persona(emoji=False)).shape("Sent! 👍").text == "Sent!"
    assert ReplyShaper(persona(emoji=True)).shape("Sent! 👍").text == "Sent! 👍"


def test_typing_delay_is_bounded():
    assert typing_delay("ok") == 0.4
    assert typing_delay("x" * 500) == 2.5
    assert 0.4 < typing_delay("Found it, due Thursday.") < 2.5
