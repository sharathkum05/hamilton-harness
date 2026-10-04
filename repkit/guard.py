"""Enforce the pack's rules in code.

The model is told the rules, but telling is not enforcing. Every action the
model proposes passes through `PolicyGuard.check_action` before it runs, and
the answer does not depend on how the conversation went.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from repkit.pack.schema import Limit, PolicyRule

Action = Literal["allow", "block", "handoff"]


@dataclass(frozen=True)
class Violation:
    rule_id: str
    reason: str
    on_violation: Literal["block", "handoff"]


@dataclass(frozen=True)
class Verdict:
    action: Action
    violations: list[Violation] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.action == "allow"

    @property
    def rule_ids(self) -> list[str]:
        return [v.rule_id for v in self.violations]

    def explain(self) -> str:
        return " ".join(f"[{v.rule_id}] {v.reason}" for v in self.violations)


ALLOW = Verdict("allow")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_limit(limit: Limit, arguments: dict[str, Any]) -> str | None:
    """Why this limit is broken, or None. Anything it cannot evaluate counts as broken."""
    if limit.field not in arguments:
        return f"'{limit.field}' is missing, so the limit cannot be checked."
    value = arguments[limit.field]
    if limit.allowed is not None and value not in limit.allowed:
        return f"'{limit.field}' is {value!r}; allowed values are {limit.allowed}."
    if limit.max is not None or limit.min is not None:
        if not _is_number(value):
            return f"'{limit.field}' must be a number to be checked."
        if limit.max is not None and value > limit.max:
            return f"'{limit.field}' is {value:g}, above the limit of {limit.max:g}."
        if limit.min is not None and value < limit.min:
            return f"'{limit.field}' is {value:g}, below the minimum of {limit.min:g}."
    return None


class PolicyGuard:
    def __init__(self, policies: list[PolicyRule]) -> None:
        self._by_tool: dict[str, list[PolicyRule]] = {}
        for rule in policies:
            if rule.tool:
                self._by_tool.setdefault(rule.tool, []).append(rule)

    def rules_for(self, tool: str) -> list[PolicyRule]:
        return list(self._by_tool.get(tool, []))

    def check_action(self, tool: str, arguments: dict[str, Any]) -> Verdict:
        violations: list[Violation] = []
        for rule in self._by_tool.get(tool, []):
            if rule.forbid:
                violations.append(
                    Violation(rule.id, f"The rep may not use {tool}.", rule.on_violation)
                )
                continue
            for limit in rule.limits:
                reason = _check_limit(limit, arguments)
                if reason:
                    violations.append(Violation(rule.id, reason, rule.on_violation))
        if not violations:
            return ALLOW
        # One rule asking for a human outranks any number asking for a plain block.
        escalate = any(v.on_violation == "handoff" for v in violations)
        return Verdict("handoff" if escalate else "block", violations)
