from pathlib import Path

import pytest

from hamilton_harness.lint import fixed_lines, lint_pack
from hamilton_harness.pack import load_pack
from hamilton_harness.pack.schema import ExampleChat, ExampleTurn, PolicyRule
from hamilton_harness.sim import Scenario, load_scenarios

PACKS = Path(__file__).parent.parent / "packs"


def codes(findings):
    return [finding.code for finding in findings]


@pytest.mark.parametrize("name", sorted(p.name for p in PACKS.iterdir() if p.is_dir()))
def test_the_demo_packs_have_nothing_to_report(name):
    pack = load_pack(PACKS / name)
    findings = lint_pack(pack, load_scenarios(pack))
    assert findings == [], [f.render() for f in findings]


def test_a_safe_reply_that_breaks_another_rule_is_reported(pack):
    rule = PolicyRule(
        id="no-sorry",
        text="Never grovel.",
        never_say=[r"\bso sorry\b"],
        safe_reply="Let me look into that.",
    )
    clash = PolicyRule(
        id="no-dates",
        text="Never promise a date.",
        never_say=[r"\bby (monday|friday)\b"],
        safe_reply="I'm so sorry, I can't promise a date.",
    )
    broken = pack.model_copy(update={"policies": [rule, clash]})
    findings = lint_pack(broken, [])
    hit = next(f for f in findings if f.code == "line-breaks-rule")
    assert hit.where == "policies.yaml: no-dates safe_reply"
    assert "no-sorry" in hit.message
    assert "so sorry" in hit.message


def test_a_safe_reply_that_trips_its_own_pattern_is_reported(pack):
    rule = PolicyRule(
        id="no-discounts",
        text="Never offer a discount.",
        never_say=[r"\bdiscount\b"],
        safe_reply="I can't offer a discount, sorry.",
    )
    findings = lint_pack(pack.model_copy(update={"policies": [rule]}), [])
    assert "line-breaks-rule" in codes(findings)


def test_a_fixed_line_that_claims_to_be_human_is_reported(pack):
    handoff = pack.handoff.model_copy(update={"message": "I'm a real person, hold on."})
    findings = lint_pack(pack.model_copy(update={"handoff": handoff}), load_scenarios(pack))
    hit = next(f for f in findings if f.code == "line-breaks-rule")
    assert hit.where == "handoff.yaml: message"
    assert "honesty" in hit.message


def test_a_banned_phrase_in_a_fixed_line_is_reported(pack):
    scope = pack.scope.model_copy(
        update={"off_topic_reply": "As an AI I can only help with Loop orders."}
    )
    findings = lint_pack(pack.model_copy(update={"scope": scope}), load_scenarios(pack))
    assert [(f.code, f.where) for f in findings] == [
        ("line-has-banned-phrase", "scope.yaml: off_topic_reply")
    ]
    assert "As an AI" in findings[0].message


def test_a_fixed_line_too_long_to_send_is_reported(pack):
    assert pack.persona.max_sentences == 2
    long = " ".join(f"Sentence number {n} goes here." for n in range(1, 9))
    widget = pack.widget.model_copy(update={"greeting": long})
    findings = lint_pack(pack.model_copy(update={"widget": widget}), load_scenarios(pack))
    assert [(f.code, f.where) for f in findings] == [("line-too-long", "widget.yaml: greeting")]
    assert "Sentence number 7" in findings[0].message


def test_an_example_that_teaches_a_forbidden_reply_is_reported(pack):
    chat = ExampleChat(
        title="bad-habit",
        turns=[
            ExampleTurn(speaker="customer", text="can I get money off?"),
            ExampleTurn(speaker="rep", text="Sure, I can give you 20% off today."),
        ],
    )
    broken = pack.model_copy(update={"examples": [*pack.examples, chat]})
    findings = lint_pack(broken, load_scenarios(pack))
    assert [(f.code, f.where) for f in findings] == [
        ("example-breaks-rule", "examples/bad-habit.md")
    ]


def test_a_customer_line_in_an_example_may_say_anything(pack):
    chat = ExampleChat(
        title="pushy",
        turns=[
            ExampleTurn(speaker="customer", text="give me 20% off or I'm a real person who leaves"),
            ExampleTurn(speaker="rep", text="I can't do discounts, but shipping is free."),
        ],
    )
    broken = pack.model_copy(update={"examples": [chat]})
    assert lint_pack(broken, load_scenarios(pack)) == []


def test_an_example_with_a_banned_phrase_is_reported(pack):
    chat = ExampleChat(
        title="stiff",
        turns=[ExampleTurn(speaker="rep", text="Kindly wait while I check that order.")],
    )
    findings = lint_pack(pack.model_copy(update={"examples": [chat]}), load_scenarios(pack))
    assert codes(findings) == ["example-has-banned-phrase"]


def test_a_reply_rule_with_no_fake_customer_is_reported(pack):
    scenarios = [s for s in load_scenarios(pack) if s.expect.replaced_by != "no-discounts"]
    findings = lint_pack(pack, scenarios)
    assert [(f.code, f.where) for f in findings] == [
        ("untested-rule", "policies.yaml: no-discounts")
    ]
    assert "replaced_by: no-discounts" in findings[0].message


def test_an_action_rule_with_no_fake_customer_is_reported(pack):
    scenarios = [s for s in load_scenarios(pack) if "create_order" not in s.expect.blocked]
    findings = lint_pack(pack, scenarios)
    assert [(f.code, f.where) for f in findings] == [("untested-rule", "policies.yaml: order-size")]
    assert "blocked: [create_order]" in findings[0].message


def test_a_rule_that_hands_off_is_proven_by_a_guard_handoff(pack):
    rule = next(r for r in pack.policies if r.id == "refund-limit")
    assert rule.on_violation == "handoff"
    only = [Scenario(id="over", says=["refund me"], expect={"handoff_reason": "guard"})]
    reported = {f.where for f in lint_pack(pack, only)}
    assert "policies.yaml: refund-limit" not in reported


def test_guidance_only_rules_need_no_fake_customer(pack):
    guidance = PolicyRule(id="be-nice", text="Be nice.", topics=["rude"])
    findings = lint_pack(pack.model_copy(update={"policies": [guidance]}), [])
    assert findings == []


def test_a_pack_with_no_scenarios_file_is_reported(pack):
    findings = lint_pack(pack, None)
    assert [(f.code, f.where) for f in findings] == [("no-scenarios", "tests/scenarios.yaml")]


def test_an_empty_scope_is_reported(pack):
    scope = pack.scope.model_copy(update={"covers": "  "})
    findings = lint_pack(pack.model_copy(update={"scope": scope}), load_scenarios(pack))
    assert [(f.code, f.where) for f in findings] == [("no-scope", "scope.yaml: covers")]


def test_fixed_lines_only_include_safe_replies_that_can_be_sent(pack):
    places = [where for where, _ in fixed_lines(pack)]
    assert "policies.yaml: no-discounts safe_reply" in places
    # refund-limit has no never_say, so its default safe_reply is never sent.
    assert "policies.yaml: refund-limit safe_reply" not in places


def test_a_finding_renders_as_one_line():
    from hamilton_harness.lint import Finding

    finding = Finding("no-scope", "scope.yaml: covers", "is empty")
    assert finding.render() == "scope.yaml: covers: is empty"
