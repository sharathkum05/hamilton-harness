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
