"""Read a pack directory into a validated Pack.

Layout:

    persona.yaml     who the rep is
    examples/*.md    real chats, one per file
    knowledge/*.md   products, prices, FAQs
    policies.yaml    what the rep may promise
    tools.yaml       what the rep may do
    handoff.yaml     when a human takes over
    model.yaml       optional model settings
    widget.yaml      optional web chat widget settings
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from repkit.pack.schema import ExampleChat, ExampleTurn, KnowledgeDoc, Pack


class PackError(Exception):
    """The pack on disk is missing something or does not validate."""


_SPEAKER = re.compile(r"^(customer|rep)\s*:\s*(.*)$", re.IGNORECASE)


def _read_yaml(path: Path, *, required: bool = False) -> Any:
    if not path.exists():
        if required:
            raise PackError(f"{path.name} is missing from {path.parent}")
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PackError(f"{path.name} is not valid YAML: {exc}") from exc


def parse_example(title: str, text: str) -> ExampleChat:
    """Parse a transcript of `customer:` / `rep:` lines.

    A line without a speaker continues the previous turn, so long replies can
    wrap.
    """
    turns: list[ExampleTurn] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _SPEAKER.match(line)
        if match:
            turns.append(ExampleTurn(speaker=match.group(1).lower(), text=match.group(2).strip()))
        elif turns:
            turns[-1].text = f"{turns[-1].text} {line}".strip()
        else:
            raise PackError(f"example '{title}' must start with 'customer:' or 'rep:'")
    if not turns:
        raise PackError(f"example '{title}' has no turns")
    return ExampleChat(title=title, turns=turns)


def _load_examples(root: Path) -> list[ExampleChat]:
    folder = root / "examples"
    if not folder.is_dir():
        return []
    return [
        parse_example(path.stem, path.read_text(encoding="utf-8"))
        for path in sorted(folder.glob("*.md"))
    ]


def _load_knowledge(root: Path) -> list[KnowledgeDoc]:
    folder = root / "knowledge"
    if not folder.is_dir():
        return []
    return [
        KnowledgeDoc(source=path.name, text=path.read_text(encoding="utf-8"))
        for path in sorted(folder.glob("*.md"))
    ]


def _listing(data: Any, key: str, filename: str) -> list[Any]:
    """Accept either a bare list or a mapping with one top-level key."""
    if data is None:
        return []
    if isinstance(data, dict) and key in data:
        data = data[key]
    if not isinstance(data, list):
        raise PackError(f"{filename} should be a list of {key}")
    return data


def load_pack(path: str | Path) -> Pack:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise PackError(f"no pack directory at {root}")

    persona = _read_yaml(root / "persona.yaml", required=True)
    policies = _listing(_read_yaml(root / "policies.yaml"), "policies", "policies.yaml")
    tools = _listing(_read_yaml(root / "tools.yaml"), "tools", "tools.yaml")

    data: dict[str, Any] = {
        "persona": persona,
        "examples": _load_examples(root),
        "knowledge": _load_knowledge(root),
        "policies": policies,
        "tools": tools,
        "root": str(root),
    }
    for optional in ("handoff", "model", "widget"):
        loaded = _read_yaml(root / f"{optional}.yaml")
        if loaded is not None:
            data[optional] = loaded

    try:
        return Pack.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise PackError(f"pack at {root} is invalid: {problems}") from exc
