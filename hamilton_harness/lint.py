"""Warnings about a pack that loads but will not behave the way its author meant.

A pack can be valid and still work against itself: a rule whose safe reply
trips another rule, a handoff message that contains a phrase the persona bans,
an example chat that teaches the rep to say what a rule forbids. None of these
stop the pack loading. All of them are found by running the pack's own lines
through the pack's own checks, which is what this does.
"""

from __future__ import annotations

from dataclasses import dataclass

from hamilton_harness.guard import PolicyGuard
from hamilton_harness.pack.schema import Pack
from hamilton_harness.shaper import ReplyShaper
from hamilton_harness.sim import Scenario


@dataclass(frozen=True)
class Finding:
    # A short, stable name for the kind of problem, such as "untested-rule".
    code: str
    # The file and entry it is about, such as "policies.yaml: refund-limit".
    where: str
    message: str

    def render(self) -> str:
        return f"{self.where}: {self.message}"


def fixed_lines(pack: Pack) -> list[tuple[str, str]]:
    """Every line the rep can send that the pack's author wrote, with where it is from."""
    lines = [
        ("persona.yaml: disclosure", pack.persona.disclosure),
        ("widget.yaml: greeting", pack.widget.greeting),
        ("handoff.yaml: message", pack.handoff.message),
        ("scope.yaml: off_topic_reply", pack.scope.off_topic_reply),
        ("scope.yaml: unsure_reply", pack.scope.unsure_reply),
    ]
    lines += [
        (f"policies.yaml: {rule.id} safe_reply", rule.safe_reply)
        for rule in pack.policies
        if rule.never_say
    ]
    return lines


# The greeting is shown by the chat panel exactly as written. Every other fixed
# line is sent as a reply, so it goes through the shaper like one.
_SHOWN_AS_WRITTEN = {"widget.yaml: greeting"}


def _check_lines(pack: Pack) -> list[Finding]:
    guard = PolicyGuard(pack.policies, pack.persona)
    shaper = ReplyShaper(pack.persona)
    findings = []
    for where, line in fixed_lines(pack):
        as_written = where in _SHOWN_AS_WRITTEN
        verdict = guard.check_reply(line)
        if not verdict.ok:
            findings.append(
                Finding(
                    "line-breaks-rule",
                    where,
                    f"this line breaks the rule '{verdict.rule_id}' "
                    f'(it matched "{verdict.matched}")',
                )
            )
        shaped = shaper.shape(line)
        for phrase in shaped.removed_phrases:
            consequence = (
                "which the rep itself is told never to say"
                if as_written
                else "which is cut before sending"
            )
            findings.append(
                Finding(
                    "line-has-banned-phrase",
                    where,
                    f'contains the banned phrase "{phrase}", {consequence}',
                )
            )
        if shaped.dropped and not as_written:
            findings.append(
                Finding(
                    "line-too-long",
                    where,
                    f"is too long for max_sentences {pack.persona.max_sentences}: "
                    f'the customer never sees "{shaped.dropped[0]}"',
                )
            )
    return findings


def _check_examples(pack: Pack) -> list[Finding]:
    guard = PolicyGuard(pack.policies, pack.persona)
    shaper = ReplyShaper(pack.persona)
    findings = []
    for chat in pack.examples:
        where = f"examples/{chat.title}.md"
        for turn in chat.turns:
            if turn.speaker != "rep":
                continue
            verdict = guard.check_reply(turn.text)
            if not verdict.ok:
                findings.append(
                    Finding(
                        "example-breaks-rule",
                        where,
                        f"the rep breaks the rule '{verdict.rule_id}' "
                        f'(it says "{verdict.matched}"), and the model copies its examples',
                    )
                )
            for phrase in shaper.shape(turn.text).removed_phrases:
                findings.append(
                    Finding(
                        "example-has-banned-phrase",
                        where,
                        f'the rep says the banned phrase "{phrase}"',
                    )
                )
    return findings


def _check_coverage(pack: Pack, scenarios: list[Scenario]) -> list[Finding]:
    """Rules enforced in code that no fake customer proves are enforced."""
    replaced = {s.expect.replaced_by for s in scenarios if s.expect.replaced_by}
    blocked = {tool for s in scenarios for tool in s.expect.blocked}
    # A rule that hands off is proven by a scenario that expects that handoff.
    escalated = any(s.expect.handoff_reason == "guard" for s in scenarios)
    findings = []
    for rule in pack.policies:
        where = f"policies.yaml: {rule.id}"
        if rule.never_say and rule.id not in replaced:
            findings.append(
                Finding(
                    "untested-rule",
                    where,
                    f"has never_say patterns but no fake customer expects replaced_by: {rule.id}",
                )
            )
        enforced_on_tool = bool(rule.tool and (rule.limits or rule.forbid))
        proven = rule.tool in blocked or (rule.on_violation == "handoff" and escalated)
        if enforced_on_tool and not proven:
            findings.append(
                Finding(
                    "untested-rule",
                    where,
                    f"limits {rule.tool} but no fake customer expects blocked: [{rule.tool}]",
                )
            )
    return findings


def lint_pack(pack: Pack, scenarios: list[Scenario] | None = None) -> list[Finding]:
    """Everything worth a second look, in the order the files are usually read.

    `scenarios` is the pack's fake customers, or None when it has no scenarios
    file, which is itself worth a warning.
    """
    findings = []
    if not pack.scope.covers.strip():
        findings.append(
            Finding(
                "no-scope",
                "scope.yaml: covers",
                "is empty, so the rep is never told what it is for",
            )
        )
    findings += _check_lines(pack)
    findings += _check_examples(pack)
    if scenarios is None:
        findings.append(
            Finding(
                "no-scenarios",
                "tests/scenarios.yaml",
                "is missing, so nothing proves the rules hold",
            )
        )
    else:
        findings += _check_coverage(pack, scenarios)
    return findings
