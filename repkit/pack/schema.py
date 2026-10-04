"""The shape of a company pack.

A pack is the only thing that changes between companies. Everything in here is
plain data so a non-engineer can edit the YAML and Markdown files it is loaded
from.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Strict(BaseModel):
    # Unknown keys are almost always typos in a hand-edited YAML file.
    model_config = ConfigDict(extra="forbid")


class Persona(_Strict):
    """Who the rep is and how they talk."""

    name: str
    company: str
    role: str = "customer support"
    voice: list[str] = Field(default_factory=list)
    language: str = "English"
    max_sentences: int = Field(default=3, ge=1)
    emoji: bool = False
    banned_phrases: list[str] = Field(default_factory=list)
    # What the rep says when a customer asks whether they are talking to an AI.
    disclosure: str = "I'm an AI assistant."
    notes: str = ""


class ExampleTurn(_Strict):
    speaker: Literal["customer", "rep"]
    text: str


class ExampleChat(_Strict):
    """A real conversation by one of the company's human reps."""

    title: str
    turns: list[ExampleTurn]


class KnowledgeDoc(_Strict):
    source: str
    text: str


class Limit(_Strict):
    """A bound on one argument of a tool call."""

    field: str
    max: float | None = None
    min: float | None = None
    allowed: list[Any] | None = None

    @model_validator(mode="after")
    def _has_a_bound(self) -> Limit:
        if self.max is None and self.min is None and self.allowed is None:
            raise ValueError(f"limit on '{self.field}' needs max, min or allowed")
        return self


class PolicyRule(_Strict):
    """One rule about what the rep may promise or do."""

    id: str
    # Shown to the model, so write it the way you would brief a new hire.
    text: str
    # Tool this rule constrains. Rules without a tool are guidance only.
    tool: str | None = None
    limits: list[Limit] = Field(default_factory=list)
    # Forbid the tool outright, whatever the arguments.
    forbid: bool = False
    on_violation: Literal["block", "handoff"] = "block"
    # Words that make this rule relevant to a customer message.
    topics: list[str] = Field(default_factory=list)
    # Regular expressions a reply must never match, checked case-insensitively.
    never_say: list[str] = Field(default_factory=list)
    # Sent instead of a reply that matched `never_say`.
    safe_reply: str = "I can't do that one, sorry."

    @model_validator(mode="after")
    def _enforceable_rules_name_a_tool(self) -> PolicyRule:
        if (self.limits or self.forbid) and not self.tool:
            raise ValueError(f"rule '{self.id}' has limits or forbid but no tool")
        return self

    @field_validator("never_say")
    @classmethod
    def _patterns_compile(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"never_say pattern {pattern!r} is not valid: {exc}") from exc
        return patterns


class ToolSpec(_Strict):
    """Something the rep can do in the company's systems."""

    name: str
    description: str
    input_schema: dict[str, Any]
    # "module:function", resolved relative to the pack directory.
    handler: str
    # Facts to keep about the customer after a successful call, as
    # {fact name: field in the tool result}.
    remember: dict[str, str] = Field(default_factory=dict)


class HandoffRules(_Strict):
    """When a human takes over."""

    # Phrases in a customer message that hand off immediately.
    phrases: list[str] = Field(default_factory=list)
    on_request: bool = True
    # Hand off after the guard has blocked this many actions in one conversation.
    max_guard_blocks: int = Field(default=2, ge=1)
    message: str = "I'm passing this to a colleague who can help. They'll have the full notes."


class ModelSettings(_Strict):
    name: str = "claude-opus-5-5"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    max_tokens: int = Field(default=16000, ge=256)


class WidgetSettings(_Strict):
    """How the web chat widget looks and opens for this company."""

    greeting: str = "Hi! How can I help?"
    launcher_label: str = "Chat with us"
    # Brand colour for the launcher, header and the customer's bubbles.
    accent: str = "#0b6e6e"
    # One-tap openers shown before the customer has typed anything.
    suggestions: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("accent")
    @classmethod
    def _accent_is_a_hex_colour(cls, value: str) -> str:
        # The value is written into a stylesheet, so nothing but a colour may pass.
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("accent must be a six-digit hex colour such as #0b6e6e")
        return value.lower()


class Pack(_Strict):
    persona: Persona
    examples: list[ExampleChat] = Field(default_factory=list)
    knowledge: list[KnowledgeDoc] = Field(default_factory=list)
    policies: list[PolicyRule] = Field(default_factory=list)
    tools: list[ToolSpec] = Field(default_factory=list)
    handoff: HandoffRules = Field(default_factory=HandoffRules)
    model: ModelSettings = Field(default_factory=ModelSettings)
    widget: WidgetSettings = Field(default_factory=WidgetSettings)
    root: str = ""

    @model_validator(mode="after")
    def _rules_point_at_real_tools(self) -> Pack:
        names = {t.name for t in self.tools}
        for rule in self.policies:
            if rule.tool and rule.tool not in names:
                raise ValueError(f"rule '{rule.id}' refers to unknown tool '{rule.tool}'")
        ids = [r.id for r in self.policies]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate policy ids: {sorted(dupes)}")
        return self
