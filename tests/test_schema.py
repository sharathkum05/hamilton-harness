import pytest
from pydantic import ValidationError

from repkit.pack.schema import Limit, Pack, Persona, PolicyRule, ToolSpec

PERSONA = Persona(name="Maya", company="Loop Sneakers")
REFUND = ToolSpec(
    name="issue_refund",
    description="Refund an order.",
    input_schema={"type": "object", "properties": {}},
    handler="handlers:issue_refund",
)


def test_limit_needs_a_bound():
    with pytest.raises(ValidationError, match="needs max, min or allowed"):
        Limit(field="amount")


def test_enforceable_rule_must_name_a_tool():
    with pytest.raises(ValidationError, match="no tool"):
        PolicyRule(id="r1", text="Refunds up to 3000.", limits=[Limit(field="amount", max=3000)])


def test_rule_cannot_point_at_missing_tool():
    rule = PolicyRule(id="r1", text="No refunds.", tool="issue_refund", forbid=True)
    with pytest.raises(ValidationError, match="unknown tool 'issue_refund'"):
        Pack(persona=PERSONA, policies=[rule])


def test_duplicate_rule_ids_are_rejected():
    rule = PolicyRule(id="r1", text="Be kind.")
    with pytest.raises(ValidationError, match="duplicate policy ids"):
        Pack(persona=PERSONA, policies=[rule, rule])


def test_unknown_keys_are_rejected():
    with pytest.raises(ValidationError):
        Persona(name="Maya", company="Loop", vioce=["casual"])


def test_valid_pack_builds():
    rule = PolicyRule(
        id="refund-limit",
        text="Refunds up to 3000.",
        tool="issue_refund",
        limits=[Limit(field="amount_inr", max=3000)],
    )
    pack = Pack(persona=PERSONA, policies=[rule], tools=[REFUND])
    assert pack.handoff.max_guard_blocks == 2
    assert pack.model.name == "claude-opus-5-5"


def test_never_say_patterns_must_compile():
    with pytest.raises(ValidationError, match="is not valid"):
        PolicyRule(id="r1", text="No discounts.", never_say=["(unclosed"])


def test_widget_accent_must_be_a_hex_colour():
    from repkit.pack.schema import WidgetSettings

    assert WidgetSettings(accent="#FF5A1F").accent == "#ff5a1f"
    for bad in ("red", "#fff", "#12345g", "#0b6e6e; background: url(x)"):
        with pytest.raises(ValidationError, match="hex colour"):
            WidgetSettings(accent=bad)


def test_widget_allows_at_most_four_suggestions():
    from repkit.pack.schema import WidgetSettings

    with pytest.raises(ValidationError):
        WidgetSettings(suggestions=["a", "b", "c", "d", "e"])
