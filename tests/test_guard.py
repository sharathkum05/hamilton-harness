from repkit.guard import PolicyGuard
from repkit.pack.schema import Limit, PolicyRule


def rule(**kwargs):
    return PolicyRule(id=kwargs.pop("id", "r"), text="t", tool="issue_refund", **kwargs)


def test_tool_without_rules_is_allowed(pack):
    assert PolicyGuard(pack.policies).check_action("lookup_order", {"order_id": "X"}).allowed


def test_refund_under_the_limit_is_allowed(pack):
    args = {"order_id": "LS-4471", "amount_inr": 2499, "reason": "duplicate_charge"}
    assert PolicyGuard(pack.policies).check_action("issue_refund", args).allowed


def test_refund_over_the_limit_hands_off(pack):
    args = {"order_id": "LS-6033", "amount_inr": 4199, "reason": "damaged"}
    verdict = PolicyGuard(pack.policies).check_action("issue_refund", args)
    assert verdict.action == "handoff"
    assert verdict.rule_ids == ["refund-limit"]
    assert "above the limit of 3000" in verdict.explain()


def test_disallowed_reason_is_blocked(pack):
    args = {"order_id": "LS-5120", "amount_inr": 2499, "reason": "changed_mind"}
    verdict = PolicyGuard(pack.policies).check_action("issue_refund", args)
    assert verdict.action == "block"
    assert verdict.rule_ids == ["refund-reasons"]


def test_handoff_outranks_block_when_both_break(pack):
    args = {"order_id": "LS-6033", "amount_inr": 4199, "reason": "changed_mind"}
    verdict = PolicyGuard(pack.policies).check_action("issue_refund", args)
    assert verdict.action == "handoff"
    assert set(verdict.rule_ids) == {"refund-limit", "refund-reasons"}


def test_limit_boundary_is_inclusive():
    guard = PolicyGuard([rule(limits=[Limit(field="amount", max=3000)])])
    assert guard.check_action("issue_refund", {"amount": 3000}).allowed
    assert not guard.check_action("issue_refund", {"amount": 3000.01}).allowed


def test_missing_or_non_numeric_values_fail_closed():
    guard = PolicyGuard([rule(limits=[Limit(field="amount", max=3000)])])
    assert not guard.check_action("issue_refund", {}).allowed
    assert not guard.check_action("issue_refund", {"amount": "2000"}).allowed
    assert not guard.check_action("issue_refund", {"amount": True}).allowed


def test_minimum_is_enforced():
    guard = PolicyGuard([rule(limits=[Limit(field="amount", min=1)])])
    assert not guard.check_action("issue_refund", {"amount": 0}).allowed


def test_forbidden_tool_is_blocked_whatever_the_arguments():
    guard = PolicyGuard([rule(forbid=True, on_violation="handoff")])
    verdict = guard.check_action("issue_refund", {"amount": 1})
    assert verdict.action == "handoff"
    assert "may not use issue_refund" in verdict.explain()


def test_reply_claiming_to_be_human_is_replaced_with_the_disclosure(pack):
    guard = PolicyGuard(pack.policies, pack.persona)
    for draft in ("Yes, I'm a real person!", "I am human, promise.", "I'm not a bot."):
        verdict = guard.check_reply(draft)
        assert not verdict.ok, draft
        assert verdict.rule_id == "honesty"
        assert verdict.replacement == pack.persona.disclosure


def test_honest_replies_pass(pack):
    guard = PolicyGuard(pack.policies, pack.persona)
    assert guard.check_reply("I'm not a human, I'm Loop's AI assistant.").ok
    assert guard.check_reply("I'm the person who looked into your order.").ok
    assert guard.check_reply("Found it, Priya. It's due Thursday.").ok


def test_forbidden_promise_is_replaced_with_the_safe_reply(pack):
    guard = PolicyGuard(pack.policies, pack.persona)
    verdict = guard.check_reply("Sure! I can give you 20% off your next pair.")
    assert not verdict.ok
    assert verdict.rule_id == "no-discounts"
    assert verdict.matched == "20% off"
    assert "can't change prices" in verdict.replacement


def test_price_match_promise_is_caught(pack):
    assert not PolicyGuard(pack.policies).check_reply("No problem, I'll match that price.").ok


def test_mentioning_the_offers_page_is_fine(pack):
    assert PolicyGuard(pack.policies).check_reply("Current offers are on the offers page.").ok
