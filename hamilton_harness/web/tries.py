"""What the demo page suggests trying, written from the rep's own pack.

With the inspector on, the suggestions are the pack's fake customers: the
first thing each one says, and in a sentence what the harness should do about
it. Otherwise they are the widget's openers and a few checks every rep has.
"""

from __future__ import annotations

from hamilton_harness.pack import Pack, PackError
from hamilton_harness.sim import Expect, load_scenarios

MAX_TRIES = 8
# One of each kind first, so the list shows the guard at work and not eight lookups.
KINDS = ("refused", "handoff", "blocked", "replaced", "record", "tool", "answer")


def _readable(name: str) -> str:
    return name.replace("_", " ")


def _a(noun: str) -> str:
    return f"{'an' if noun[:1].lower() in 'aeiou' else 'a'} {noun}"


def _explain(expect: Expect, labels: dict[str, str]) -> tuple[str, str]:
    """The kind of check a fake customer shows, and a sentence about it."""
    if expect.refused:
        if expect.refused == "strict":
            return "refused", "Outside what it covers: turned away in code."
        return "refused", (
            f"Off topic ({expect.refused}): turned away in code, before the model is called."
        )
    if expect.handoff:
        if expect.handoff_reason == "requested":
            return "handoff", "Asks for a person: handed over without calling the model."
        return "handoff", "Handed over to a person."
    if expect.blocked:
        return (
            "blocked",
            f"Goes past a limit on {_readable(expect.blocked[0])}: the guard blocks it.",
        )
    if expect.replaced_by:
        return "replaced", (
            f"A reply that breaks the {expect.replaced_by} rule is replaced before it is sent."
        )
    for tool in expect.called:
        if tool in labels:
            return "record", f"Takes down {labels[tool]} for the team."
    if expect.called:
        return "tool", f"Uses {_readable(expect.called[0])} before answering."
    return "answer", "Answers from its notes."


def _from_tests(pack: Pack) -> list[tuple[str, dict[str, str]]]:
    try:
        scenarios = load_scenarios(pack)
    except PackError:
        return []
    labels = {f"create_{r.name}": _a(r.label.lower()) for r in pack.records}
    found: list[tuple[str, dict[str, str]]] = []
    seen: set[str] = set()
    for scenario in scenarios:
        say = scenario.says[0].strip()
        if say.lower() in seen:
            continue
        seen.add(say.lower())
        kind, why = _explain(scenario.expect, labels)
        found.append((kind, {"say": say, "why": why}))

    chosen: list[int] = []
    for kind in KINDS:
        first = next((i for i, (k, _) in enumerate(found) if k == kind), None)
        if first is not None:
            chosen.append(first)
    for index in range(len(found)):
        if len(chosen) >= MAX_TRIES:
            break
        if index not in chosen:
            chosen.append(index)
    # Shown in the order the pack's author wrote them.
    return [found[index] for index in sorted(chosen[:MAX_TRIES])]


def _general(pack: Pack) -> list[tuple[str, dict[str, str]]]:
    tries = [
        ("opener", {"say": line, "why": "One of the openers customers can tap."})
        for line in pack.widget.suggestions
    ]
    tries.append(("bot", {"say": "Are you a real person?", "why": "It always says it is an AI."}))
    if "math" in pack.scope.refuse:
        tries.append(
            (
                "refused",
                {
                    "say": "What is 348 * 12?",
                    "why": "Off topic: turned away in code, before the model is called.",
                },
            )
        )
    if pack.handoff.on_request:
        tries.append(
            (
                "handoff",
                {
                    "say": "Can I talk to a person?",
                    "why": "Asks for a person: handed over without calling the model.",
                },
            )
        )
    return tries


def demo_tries(pack: Pack, *, from_tests: bool) -> list[dict[str, str]]:
    """Messages to try on the demo page, each with what should happen."""
    tries = _from_tests(pack) if from_tests else []
    # Topped up with the rep's openers and the checks every rep has, where the tests leave room.
    shown = {kind for kind, _ in tries}
    said = {item["say"].lower() for _, item in tries}
    for kind, item in _general(pack):
        if len(tries) >= MAX_TRIES:
            break
        if kind in shown or item["say"].lower() in said:
            continue
        if kind != "opener":
            shown.add(kind)
        tries.append((kind, item))
    return [item for _, item in tries]
