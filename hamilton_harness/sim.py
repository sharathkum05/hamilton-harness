"""Fake customers and a scorecard.

A scenario is a customer with something to say and a list of things that must
be true afterwards: which actions ran, which were blocked, whether a human
took over, what the rep must and must never say.

Scenarios run in two modes. Live mode talks to the real model and measures the
whole system. Replay mode feeds the harness a recorded model script, including
scripts where the model misbehaves, so the guard, handoff and shaper can be
regression-tested with no network.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hamilton_harness.llm import Model, ScriptedModel, Usage
from hamilton_harness.pack.loader import PackError
from hamilton_harness.pack.schema import Pack
from hamilton_harness.runtime import Agent, TurnResult

# US dollars per million tokens: (input, output, cache read).
PRICES: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Tools that must have run successfully.
    called: list[str] = Field(default_factory=list)
    # Tools that must not have run successfully.
    not_called: list[str] = Field(default_factory=list)
    # Tools the guard must have blocked.
    blocked: list[str] = Field(default_factory=list)
    handoff: bool | None = None
    handoff_reason: str | None = None
    # Rule that must have replaced a draft reply.
    replaced_by: str | None = None
    # Scope check that must have turned the message away, such as "math" or "strict".
    refused: str | None = None
    # Patterns that must appear in some reply, and ones that must appear in none.
    says: list[str] = Field(default_factory=list)
    never_says: list[str] = Field(default_factory=list)
    max_model_calls: int | None = None


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer: str = "customer"
    says: list[str] = Field(min_length=1)
    expect: Expect = Field(default_factory=Expect)
    # Recorded model steps for replay mode, in the format ScriptedModel takes.
    replay: list[Any] | None = None


def load_scenarios(pack: Pack, path: str | Path | None = None) -> list[Scenario]:
    source = Path(path) if path else Path(pack.root) / "tests" / "scenarios.yaml"
    if not source.exists():
        raise PackError(f"no scenarios file at {source}")
    data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    items = data.get("scenarios", data) if isinstance(data, dict) else data
    try:
        scenarios = [Scenario.model_validate(item) for item in items]
    except ValidationError as exc:
        raise PackError(f"{source.name} is invalid: {exc.errors()[0]['msg']}") from exc
    ids = [s.id for s in scenarios]
    if len(set(ids)) != len(ids):
        raise PackError(f"{source.name} has duplicate scenario ids")
    return scenarios


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ScenarioResult:
    scenario: Scenario
    turns: list[TurnResult] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    error: str = ""

    @property
    def passed(self) -> bool:
        return not self.error and all(check.passed for check in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.passed]


def _grade(scenario: Scenario, turns: list[TurnResult]) -> list[Check]:
    expect = scenario.expect
    actions = [action for turn in turns for action in turn.actions]
    ran = {a.tool for a in actions if a.outcome == "ok"}
    blocked = {a.tool for a in actions if a.outcome == "blocked"}
    replies = [turn.text for turn in turns]
    handoff = next((turn.handoff for turn in turns if turn.handoff), None)
    checks: list[Check] = []

    for tool in expect.called:
        checks.append(Check(f"called {tool}", tool in ran, f"ran: {sorted(ran) or 'nothing'}"))
    for tool in expect.not_called:
        checks.append(Check(f"did not call {tool}", tool not in ran))
    for tool in expect.blocked:
        checks.append(
            Check(
                f"guard blocked {tool}", tool in blocked, f"blocked: {sorted(blocked) or 'nothing'}"
            )
        )
    if expect.handoff is not None:
        got = handoff is not None
        checks.append(Check(f"handoff is {expect.handoff}", got == expect.handoff, f"got {got}"))
    if expect.handoff_reason is not None:
        reason = handoff.reason if handoff else None
        checks.append(
            Check(
                f"handoff reason is {expect.handoff_reason}",
                reason == expect.handoff_reason,
                f"got {reason}",
            )
        )
    if expect.replaced_by is not None:
        replaced = [turn.replaced_by for turn in turns if turn.replaced_by]
        checks.append(
            Check(
                f"reply replaced by {expect.replaced_by}",
                expect.replaced_by in replaced,
                f"replaced by: {replaced or 'nothing'}",
            )
        )
    if expect.refused is not None:
        refused = [turn.refused for turn in turns if turn.refused]
        checks.append(
            Check(
                f"refused as {expect.refused}",
                expect.refused in refused,
                f"refused as: {refused or 'nothing'}",
            )
        )
    for pattern in expect.says:
        found = any(re.search(pattern, reply, re.IGNORECASE) for reply in replies)
        checks.append(Check(f"says /{pattern}/", found))
    for pattern in expect.never_says:
        hit = next((r for r in replies if re.search(pattern, r, re.IGNORECASE)), None)
        checks.append(Check(f"never says /{pattern}/", hit is None, hit or ""))
    if expect.max_model_calls is not None:
        calls = sum(turn.model_calls for turn in turns)
        checks.append(
            Check(
                f"at most {expect.max_model_calls} model calls",
                calls <= expect.max_model_calls,
                f"made {calls}",
            )
        )
    return checks


ModelFactory = Callable[[Scenario], Model]


def replay_model(scenario: Scenario) -> Model:
    if scenario.replay is None:
        raise PackError(f"scenario '{scenario.id}' has no replay script")
    return ScriptedModel(scenario.replay)


def run_scenario(pack: Pack, scenario: Scenario, model_factory: ModelFactory) -> ScenarioResult:
    result = ScenarioResult(scenario)
    try:
        # A fresh agent per scenario, so one customer's refund cannot affect the next.
        agent = Agent(pack, model_factory(scenario), retry_wait=0)
        conversation = agent.start(f"sim-{scenario.id}")
        for line in scenario.says:
            turn = agent.respond(conversation, line)
            result.turns.append(turn)
            if turn.handoff:
                break
    except Exception as exc:  # a crash is a failed scenario, not a failed run
        result.error = f"{type(exc).__name__}: {exc}"
    result.checks = _grade(scenario, result.turns)
    return result


@dataclass
class Scorecard:
    results: list[ScenarioResult]
    model: str = ""

    @property
    def passed(self) -> int:
        return sum(r.passed for r in self.results)

    @property
    def ok(self) -> bool:
        return self.passed == len(self.results)

    def _turns(self) -> list[TurnResult]:
        return [turn for result in self.results for turn in result.turns]

    def usage(self) -> Usage:
        total = Usage()
        for turn in self._turns():
            total = total + turn.usage
        return total

    def cost_usd(self) -> float | None:
        price = PRICES.get(self.model)
        if price is None:
            return None
        usage = self.usage()
        return (
            usage.input_tokens * price[0]
            + usage.output_tokens * price[1]
            + usage.cache_read_tokens * price[2]
        ) / 1_000_000

    def summary(self) -> dict[str, Any]:
        turns = self._turns()
        actions = [action for turn in turns for action in turn.actions]
        latencies = sorted(turn.latency_ms for turn in turns)
        usage = self.usage()
        cost = self.cost_usd()
        return {
            "scenarios": len(self.results),
            "passed": self.passed,
            "checks": sum(len(r.checks) for r in self.results),
            "checks_failed": sum(len(r.failures) for r in self.results),
            "turns": len(turns),
            "actions_run": sum(a.outcome == "ok" for a in actions),
            "actions_blocked": sum(a.outcome == "blocked" for a in actions),
            "replies_replaced": sum(bool(turn.replaced_by) for turn in turns),
            "off_topic_refused": sum(bool(turn.refused) for turn in turns),
            "handoffs": sum(turn.handoff is not None for turn in turns),
            "sentences_dropped": sum(len(turn.dropped) for turn in turns),
            "bubbles_per_turn": round(statistics.mean(len(t.bubbles) for t in turns), 2)
            if turns
            else 0.0,
            "latency_ms_p50": round(statistics.median(latencies), 1) if latencies else 0.0,
            "latency_ms_p95": round(latencies[int(0.95 * (len(latencies) - 1))], 1)
            if latencies
            else 0.0,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": round(cost, 4) if cost is not None else None,
            "cost_usd_per_conversation": round(cost / len(self.results), 4)
            if cost is not None and self.results
            else None,
        }

    def render(self) -> str:
        lines = []
        for result in self.results:
            mark = "PASS" if result.passed else "FAIL"
            lines.append(f"{mark}  {result.scenario.id}  ({result.scenario.customer})")
            if result.error:
                lines.append(f"      crashed: {result.error}")
            for check in result.failures:
                detail = f"  [{check.detail}]" if check.detail else ""
                lines.append(f"      failed: {check.name}{detail}")
        s = self.summary()
        cost = "n/a" if s["cost_usd"] is None else f"${s['cost_usd']:.4f}"
        lines += [
            "",
            f"{s['passed']}/{s['scenarios']} scenarios passed, "
            f"{s['checks'] - s['checks_failed']}/{s['checks']} checks",
            f"actions run {s['actions_run']}, blocked by guard {s['actions_blocked']}, "
            f"replies replaced {s['replies_replaced']}, off topic refused "
            f"{s['off_topic_refused']}, handoffs {s['handoffs']}",
            f"bubbles per turn {s['bubbles_per_turn']}, sentences dropped {s['sentences_dropped']}",
            f"turn latency p50 {s['latency_ms_p50']} ms, p95 {s['latency_ms_p95']} ms",
            f"tokens in {s['input_tokens']}, out {s['output_tokens']}, cost {cost}",
        ]
        return "\n".join(lines)


def run_scenarios(
    pack: Pack,
    scenarios: list[Scenario],
    model_factory: ModelFactory = replay_model,
    *,
    model_name: str = "",
) -> Scorecard:
    results = [run_scenario(pack, scenario, model_factory) for scenario in scenarios]
    return Scorecard(results, model=model_name)
