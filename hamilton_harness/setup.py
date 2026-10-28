"""Build a rep from a few answers: the setup the dashboard walks a business through.

The answers go into a fresh starter pack, written in a folder beside the real
one. Only once that pack loads is it moved into place, so a bad answer never
leaves a half-written rep. An uploaded logo is kept.

A pack made by `hamilton-harness studio` carries a marker file until setup has
run once, so the dashboard knows to open the setup first.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hamilton_harness.editor import MAX_KNOWLEDGE_CHARS, dump_yaml
from hamilton_harness.pack import Pack, PackError, load_pack
from hamilton_harness.pack.schema import WidgetSettings
from hamilton_harness.scaffold import write_starter_pack

PENDING = ".setup-pending"

# Each tone becomes one line of the persona's voice, which the model is shown.
TONES = {
    "friendly": "friendly and warm, like a colleague who is glad to help",
    "professional": "polite and precise, never casual",
    "playful": "light and playful, without being silly",
    "direct": "short and direct: the answer first, then one question",
}

# The starter's example and its opening-hours customer both quote the starter's
# made-up hours. Once a business writes its own notes they would be wrong.
NEUTRAL_EXAMPLE = """\
# A short enquiry, handled the way the team would.
customer: hi, can someone get back to me about this?
rep: Of course. What name and email should the team use?
customer: Priya Menon, priya@example.com
rep: Thanks, Priya. I've passed it to the team and they'll email you.
"""


class SetupAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = Field(min_length=1, max_length=80)
    rep: str = Field(min_length=1, max_length=40)
    role: str = Field(default="customer support", min_length=1, max_length=60)
    covers: str = Field(default="", max_length=1000)
    knowledge: str = Field(default="", max_length=MAX_KNOWLEDGE_CHARS)
    tone: list[Literal["friendly", "professional", "playful", "direct"]] = Field(
        default_factory=list, max_length=4
    )
    emoji: bool = False
    greeting: str = Field(default="", max_length=300)
    suggestions: list[str] = Field(default_factory=list, max_length=4)
    accent: str = "auto"


def read_answers(values: dict[str, Any]) -> SetupAnswers:
    """Check the answers, with a message a person can act on."""
    try:
        return SetupAnswers.model_validate(values)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or 'value'}: {item['msg']}"
            for item in error.errors()
        )
        raise PackError(problems) from error


def needs_setup(root: str | Path) -> bool:
    return (Path(root) / PENDING).exists()


def mark_pending(root: str | Path) -> None:
    (Path(root) / PENDING).write_text(
        "Setup has not run yet. The dashboard opens it first.\n", encoding="utf-8"
    )


def _edit_yaml(path: Path, changes: dict[str, Any]) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    path.write_text(dump_yaml({**data, **changes}), encoding="utf-8")


def _customise(draft: Path, answers: SetupAnswers, logo: str) -> None:
    persona: dict[str, Any] = {"role": answers.role.strip(), "emoji": answers.emoji}
    if answers.tone:
        persona["voice"] = [TONES[tone] for tone in answers.tone]
    _edit_yaml(draft / "persona.yaml", persona)

    if answers.covers.strip():
        _edit_yaml(draft / "scope.yaml", {"covers": answers.covers.strip()})

    widget: dict[str, Any] = {"accent": answers.accent, "logo": logo}
    if answers.greeting.strip():
        widget["greeting"] = answers.greeting.strip()
    suggestions = [line.strip() for line in answers.suggestions if line.strip()]
    if suggestions:
        widget["suggestions"] = suggestions
    elif answers.knowledge.strip():
        # The starter's openers ask about its made-up opening hours.
        widget["suggestions"] = ["Can someone contact me?"]
    # Checked here, so a bad colour is reported as the answer it is.
    WidgetSettings.model_validate(
        {**yaml.safe_load((draft / "widget.yaml").read_text(encoding="utf-8")), **widget}
    )
    _edit_yaml(draft / "widget.yaml", widget)

    text = answers.knowledge.strip()
    if text:
        if not text.startswith("#"):
            text = f"# About {answers.company.strip()}\n\n{text}"
        (draft / "knowledge" / "about.md").write_text(text + "\n", encoding="utf-8")
        (draft / "examples" / "enquiry.md").write_text(NEUTRAL_EXAMPLE, encoding="utf-8")
        scenarios = draft / "tests" / "scenarios.yaml"
        data = yaml.safe_load(scenarios.read_text(encoding="utf-8"))
        data["scenarios"] = [s for s in data["scenarios"] if s["id"] != "opening-hours"]
        scenarios.write_text(dump_yaml(data), encoding="utf-8")


def apply_setup(root: str | Path, answers: SetupAnswers) -> Pack:
    """Rebuild the pack at `root` from the answers and return it, loaded."""
    root = Path(root)
    draft = root.parent / f".{root.name}.setup"
    shutil.rmtree(draft, ignore_errors=True)
    try:
        write_starter_pack(draft, company=answers.company, rep=answers.rep)
        logo = ""
        if (root / "brand").is_dir():
            shutil.copytree(root / "brand", draft / "brand")
            logos = sorted((draft / "brand").glob("logo.*"))
            logo = f"brand/{logos[0].name}" if logos else ""
        _customise(draft, answers, logo)
        load_pack(draft)
    except (PackError, ValueError) as error:
        shutil.rmtree(draft, ignore_errors=True)
        raise PackError(str(error)) from error

    before = root.parent / f".{root.name}.before-setup"
    shutil.rmtree(before, ignore_errors=True)
    root.rename(before)
    draft.rename(root)
    shutil.rmtree(before)
    return load_pack(root)
