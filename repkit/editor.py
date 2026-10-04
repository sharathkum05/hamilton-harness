"""Edit a pack on disk, safely.

The dashboard and the MCP server both change packs through this class, so the
rules are in one place: every edit is validated, written to the pack's own
file, and checked by loading the whole pack again. An edit that leaves the
pack unloadable is rolled back and refused.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from repkit.pack import Pack, PackError, load_pack
from repkit.pack.schema import HandoffRules, Persona, PolicyRule, ScopeSettings, WidgetSettings
from repkit.sim import load_scenarios, run_scenarios
from repkit.trace import read_trace

# Parts of the pack stored as one YAML mapping each.
SECTIONS: dict[str, type[BaseModel]] = {
    "persona": Persona,
    "scope": ScopeSettings,
    "widget": WidgetSettings,
    "handoff": HandoffRules,
}
MAX_KNOWLEDGE_CHARS = 200_000
_KNOWLEDGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,60}\.md")
_TRACE_ID = re.compile(r"[0-9a-f]{12}")


class EditError(Exception):
    """An edit was refused. `missing` is true when the thing to edit does not exist."""

    def __init__(self, message: str, *, missing: bool = False) -> None:
        super().__init__(message)
        self.missing = missing


def _problems(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'value'}: {item['msg']}"
        for item in error.errors()
    )


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88)


class PackEditor:
    def __init__(self, root: str | Path, *, on_change: Callable[[], Any] | None = None) -> None:
        self.root = Path(root)
        # Called after every successful edit, for example to reload a running server.
        self._on_change = on_change

    def load(self) -> Pack:
        return load_pack(self.root)

    def write(self, path: Path, content: str | bytes | None) -> None:
        """Write one pack file, or delete it when content is None, and check the pack loads."""
        previous = path.read_bytes() if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            path.unlink(missing_ok=True)
        elif isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        try:
            self.load()
        except PackError as error:
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
            raise EditError(str(error)) from error
        if self._on_change:
            self._on_change()

    # -- reading ------------------------------------------------------------

    def overview(self) -> dict[str, Any]:
        pack = self.load()
        try:
            scenarios = len(load_scenarios(pack))
        except PackError:
            scenarios = 0
        return {
            "persona": pack.persona.model_dump(mode="json"),
            "scope": pack.scope.model_dump(mode="json"),
            "widget": pack.widget.model_dump(mode="json"),
            "handoff": pack.handoff.model_dump(mode="json"),
            "model": pack.model.model_dump(mode="json"),
            "policies": [rule.model_dump(mode="json") for rule in pack.policies],
            "tools": [
                {
                    "name": t.name,
                    "description": " ".join(t.description.split()),
                    "handler": t.handler,
                }
                for t in pack.tools
            ],
            "knowledge": [doc.model_dump() for doc in pack.knowledge],
            "examples": [chat.model_dump() for chat in pack.examples],
            "scenarios": scenarios,
        }

    # -- settings -----------------------------------------------------------

    def save_section(self, section: str, values: dict[str, Any]) -> BaseModel:
        """Replace one of persona, scope, widget or handoff."""
        model = SECTIONS.get(section)
        if model is None:
            raise EditError(f"no editable section '{section}'", missing=True)
        try:
            validated = model.model_validate(values)
        except ValidationError as error:
            raise EditError(_problems(error)) from error
        self.write(self.root / f"{section}.yaml", dump_yaml(validated.model_dump(mode="json")))
        return validated

    def update_section(self, section: str, changes: dict[str, Any]) -> BaseModel:
        """Change some fields of a section and keep the rest."""
        if section not in SECTIONS:
            raise EditError(f"no editable section '{section}'", missing=True)
        current = getattr(self.load(), section).model_dump(mode="json")
        return self.save_section(section, {**current, **changes})

    def save_policies(self, rules: list[dict[str, Any]]) -> list[PolicyRule]:
        try:
            validated = [PolicyRule.model_validate(rule) for rule in rules]
        except ValidationError as error:
            raise EditError(_problems(error)) from error
        data = {"policies": [r.model_dump(mode="json", exclude_defaults=True) for r in validated]}
        self.write(self.root / "policies.yaml", dump_yaml(data))
        return validated

    # -- knowledge ----------------------------------------------------------

    def _knowledge_path(self, name: str) -> Path:
        if not _KNOWLEDGE_NAME.fullmatch(name):
            raise EditError("file name must look like shipping.md")
        return self.root / "knowledge" / name

    def read_knowledge(self, name: str) -> str:
        path = self._knowledge_path(name)
        if not path.exists():
            raise EditError(f"no knowledge file {name}", missing=True)
        return path.read_text(encoding="utf-8")

    def save_knowledge(self, name: str, text: str) -> None:
        if len(text) > MAX_KNOWLEDGE_CHARS:
            raise EditError("that file is too long")
        self.write(self._knowledge_path(name), text)

    def delete_knowledge(self, name: str) -> None:
        path = self._knowledge_path(name)
        if not path.exists():
            raise EditError(f"no knowledge file {name}", missing=True)
        self.write(path, None)

    # -- testing and history ------------------------------------------------

    def run_fake_customers(self) -> dict[str, Any]:
        pack = self.load()
        try:
            scenarios = load_scenarios(pack)
        except PackError as error:
            raise EditError(str(error), missing=True) from error
        scorecard = run_scenarios(pack, scenarios, model_name="replay")
        return {
            "summary": scorecard.summary(),
            "results": [
                {
                    "id": result.scenario.id,
                    "customer": result.scenario.customer,
                    "says": result.scenario.says,
                    "passed": result.passed,
                    "replies": [turn.text for turn in result.turns],
                    "failures": [{"name": c.name, "detail": c.detail} for c in result.failures],
                    "error": result.error,
                }
                for result in scorecard.results
            ],
        }


def list_conversations(trace_dir: Path | None, *, limit: int = 50) -> list[dict[str, Any]]:
    """Recorded conversations, newest first, with what stood out in each."""
    if trace_dir is None or not trace_dir.is_dir():
        return []
    files = sorted(trace_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    summaries = []
    for path in files[:limit]:
        records = read_trace(path)
        first = next((r.get("text", "") for r in records if r["kind"] == "customer"), "")
        summaries.append(
            {
                "id": path.stem,
                "turns": max((r.get("turn", 0) for r in records), default=0),
                "updated_at": path.stat().st_mtime,
                "opening": first[:140],
                "handed_off": any(r["kind"] == "handoff" for r in records),
                "blocked": any(
                    r["kind"] == "reply_blocked"
                    or (r["kind"] == "action" and r.get("outcome") == "blocked")
                    for r in records
                ),
                "refused": any(r["kind"] == "scope_refused" for r in records),
            }
        )
    return summaries


def read_conversation(trace_dir: Path | None, conversation_id: str) -> list[dict[str, Any]]:
    if trace_dir is None or not _TRACE_ID.fullmatch(conversation_id):
        raise EditError("conversation not found", missing=True)
    path = trace_dir / f"{conversation_id}.jsonl"
    if not path.is_file():
        raise EditError("conversation not found", missing=True)
    return read_trace(path)
