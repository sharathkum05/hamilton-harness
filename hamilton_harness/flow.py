"""The harness as the path a message takes, and what each stage did to one.

The dashboard's Flow screen draws these stages in order. Sending a test message
runs one real turn and marks every stage: passed, stopped the message, or
never reached because something earlier stopped it.
"""

from __future__ import annotations

from typing import Any

from hamilton_harness.pack import Pack

# (key, name, what it does). The order is the order of a turn and cannot change:
# every action and every reply passes the checks after the model, whatever is set up.
STAGES: list[tuple[str, str, str]] = [
    ("message", "Customer message", "What the customer typed."),
    ("handoff", "Handoff check", "Hands the chat to a person on set phrases or when asked."),
    ("context", "Context", "Looks up the rules, knowledge and memory this message needs."),
    ("scope", "Scope gate", "Turns away what the rep is not for, before the model."),
    ("model", "Model", "Drafts a reply or asks to use a tool."),
    ("tools", "Tools", "Checks each action against its inputs and limits, then runs it."),
    ("guard", "Reply guard", "Replaces a reply that breaks a rule or claims to be human."),
    ("grounding", "Grounding", "Replaces a reply that states a figure from nowhere."),
    ("reply", "Reply", "Shapes the reply into chat bubbles and sends it."),
]


def _stage(key: str, status: str, note: str) -> dict[str, str]:
    return {"key": key, "status": status, "note": note}


def stages_from_events(events: list[dict[str, Any]], pack: Pack) -> list[dict[str, str]]:
    """Each stage's part in one turn: "passed", "stopped", "unused" or "skipped"."""
    kinds = [e["kind"] for e in events]
    first = {kind: next(e for e in events if e["kind"] == kind) for kind in set(kinds)}
    early_handoff = "handoff" in kinds and (
        "context" not in kinds or kinds.index("handoff") < kinds.index("context")
    )
    actions = [e for e in events if e["kind"] == "action"]
    replaced = first.get("reply_blocked")
    model_calls = kinds.count("model")
    out = [_stage("message", "passed", first.get("customer", {}).get("text", ""))]

    if early_handoff:
        out.append(
            _stage("handoff", "stopped", f"Handed to a person: {first['handoff']['reason']}.")
        )
        out += [_stage(k, "skipped", "") for k, *_ in STAGES[2:-1]]
        out.append(_stage("reply", "passed", pack.handoff.message))
        return out
    out.append(_stage("handoff", "passed", "No reason to hand over."))

    context = first.get("context", {})
    rules, notes = context.get("rules", []), context.get("notes", [])
    out.append(
        _stage(
            "context",
            "passed",
            f"{len(rules)} rule{'s' * (len(rules) != 1)}, {len(notes)} "
            f"note{'s' * (len(notes) != 1)}" + (f": {', '.join(rules)}" if rules else ""),
        )
    )

    if "scope_refused" in kinds:
        reason = first["scope_refused"]["reason"]
        out.append(_stage("scope", "stopped", f"Turned away as off topic ({reason})."))
        out += [_stage(k, "skipped", "") for k, *_ in STAGES[4:-1]]
        out.append(_stage("reply", "passed", pack.scope.off_topic_reply))
        return out
    out.append(_stage("scope", "passed", "On topic."))

    if "model_error" in kinds and not model_calls:
        out.append(_stage("model", "stopped", first["model_error"]["error"]))
        out += [_stage(k, "skipped", "") for k, *_ in STAGES[5:]]
        return out
    out.append(_stage("model", "passed", f"{model_calls} call{'s' * (model_calls != 1)}."))

    blocked = [a for a in actions if a.get("outcome") == "blocked"]
    if blocked:
        names = ", ".join(sorted({a["tool"] for a in blocked}))
        out.append(_stage("tools", "stopped", f"Blocked {names}: {blocked[0].get('detail', '')}"))
    elif actions:
        ran = ", ".join(f"{a['tool']} ({a.get('outcome')})" for a in actions)
        out.append(_stage("tools", "passed", f"Ran {ran}."))
    else:
        out.append(_stage("tools", "unused", "No action needed."))

    shaped = first.get("shaped")
    late_handoff = "handoff" in kinds
    if replaced and replaced.get("rule") != "grounding":
        out.append(_stage("guard", "stopped", f"Draft replaced by the {replaced['rule']} rule."))
    elif shaped:
        out.append(_stage("guard", "passed", "Broke no rule."))
    else:
        out.append(_stage("guard", "skipped", ""))

    if replaced and replaced.get("rule") == "grounding":
        figures = replaced.get("matched", "")
        out.append(_stage("grounding", "stopped", f"Invented figure ({figures}): draft replaced."))
    elif shaped and not pack.scope.ground_numbers:
        out.append(_stage("grounding", "unused", "Switched off for this rep."))
    elif shaped:
        out.append(_stage("grounding", "passed", "Every figure has a source."))
    else:
        out.append(_stage("grounding", "skipped", ""))

    if late_handoff:
        out.append(_stage("reply", "passed", f"Handed to a person: {pack.handoff.message}"))
    elif shaped:
        bubbles = shaped.get("bubbles", [])
        out.append(_stage("reply", "passed", " / ".join(bubbles)))
    else:
        out.append(_stage("reply", "skipped", ""))
    return out
