"""The one place that talks to a model.

The runtime only needs `Model.complete`. `AnthropicModel` calls Claude;
`ScriptedModel` replays a fixed script so the harness can be tested, and
simulated, with no network and no API key.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from hamilton_harness.pack.schema import ModelSettings


class ModelError(Exception):
    """The model call failed. `retryable` says whether trying again might help."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: Any


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_read_tokens + other.cache_read_tokens,
            self.cache_write_tokens + other.cache_write_tokens,
        )


@dataclass
class ModelResponse:
    # Appended to the history unchanged, so the model gets its own turn back intact.
    content: Any
    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
    usage: Usage = field(default_factory=Usage)
    latency_ms: float = 0.0
    model: str = ""


class Model(Protocol):
    name: str
    # Whether `{"role": "system"}` may appear inside `messages`.
    supports_system_turns: bool

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelResponse: ...


# Models that accept an operator message in the middle of a conversation.
_SYSTEM_TURN_PREFIXES = (
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-fable-5",
    "claude-mythos-5",
    "claude-sonnet-5-5",
)
# Models whose safety classifiers can decline a request, where a server-side
# fallback keeps the conversation going on another model.
_FALLBACK_PREFIXES = ("claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5")
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicModel:
    def __init__(self, settings: ModelSettings | None = None, *, client: Any = None) -> None:
        import anthropic

        self._anthropic = anthropic
        self._settings = settings or ModelSettings()
        self._client = client or anthropic.Anthropic()
        self.name = self._settings.name
        self.supports_system_turns = self.name.startswith(_SYSTEM_TURN_PREFIXES)
        self._fallbacks = self.name.startswith(_FALLBACK_PREFIXES)

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelResponse:
        request: dict[str, Any] = {
            "model": self.name,
            "max_tokens": self._settings.max_tokens,
            # The persona and examples never change within a pack, so cache them.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
            "output_config": {"effort": self._settings.effort},
        }
        if tools:
            request["tools"] = tools

        anthropic = self._anthropic
        started = time.perf_counter()
        try:
            if self._fallbacks:
                response = self._client.beta.messages.create(
                    betas=[_FALLBACK_BETA], fallbacks="default", **request
                )
            else:
                response = self._client.messages.create(**request)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise ModelError(f"model credentials were rejected: {exc.message}") from exc
        except anthropic.NotFoundError as exc:
            raise ModelError(f"model '{self.name}' was not found: {exc.message}") from exc
        except anthropic.BadRequestError as exc:
            raise ModelError(f"model rejected the request: {exc.message}") from exc
        except anthropic.RateLimitError as exc:
            raise ModelError("model is rate limited", retryable=True) from exc
        except anthropic.APIStatusError as exc:
            raise ModelError(
                f"model returned {exc.status_code}", retryable=exc.status_code >= 500
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise ModelError("could not reach the model", retryable=True) from exc
        except anthropic.AnthropicError as exc:
            raise ModelError(f"model call failed: {exc}") from exc
        except TypeError as exc:
            # The SDK raises a bare TypeError when it finds no credential to send.
            if "authentication" not in str(exc):
                raise
            raise ModelError("no model credentials found; set ANTHROPIC_API_KEY") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        text = "".join(b.text for b in response.content if b.type == "text")
        calls = [ToolCall(b.id, b.name, b.input) for b in response.content if b.type == "tool_use"]
        usage = response.usage
        return ModelResponse(
            content=response.content,
            text=text.strip(),
            tool_calls=calls,
            stop_reason=response.stop_reason or "",
            usage=Usage(
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            ),
            latency_ms=latency_ms,
            model=response.model,
        )


Step = str | dict[str, Any] | Sequence[Any] | Callable[[list[dict[str, Any]]], Any]


class ScriptedModel:
    """Replays a list of steps, one per model call.

    A step is a string (the reply), a `{"tool": name, "args": {...}}` mapping
    (a tool call), a list mixing both, or a function of the message history
    that returns any of those.
    """

    name = "scripted"

    def __init__(self, steps: Sequence[Step], *, supports_system_turns: bool = True) -> None:
        self._steps = list(steps)
        self.supports_system_turns = supports_system_turns
        self.calls: list[dict[str, Any]] = []

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelResponse:
        # Copy the list: the caller keeps appending to the same history object.
        self.calls.append({"system": system, "messages": list(messages), "tools": tools})
        if not self._steps:
            raise ModelError("scripted model ran out of steps")
        step = self._steps.pop(0)
        if callable(step):
            step = step(messages)
        parts = [step] if isinstance(step, (str, dict)) else list(step)

        content: list[dict[str, Any]] = []
        calls: list[ToolCall] = []
        for part in parts:
            if isinstance(part, str):
                content.append({"type": "text", "text": part})
            else:
                call = ToolCall(
                    f"toolu_{uuid.uuid4().hex[:12]}", part["tool"], part.get("args", {})
                )
                calls.append(call)
                content.append(
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                )
        text = " ".join(p for p in parts if isinstance(p, str)).strip()
        return ModelResponse(
            content=content,
            text=text,
            tool_calls=calls,
            stop_reason="tool_use" if calls else "end_turn",
            usage=Usage(input_tokens=0, output_tokens=len(text.split())),
            model=self.name,
        )


def load_offline_model(pack_root: str) -> Model:
    """Load the stand-in model a pack ships in `offline_model.py`, for demos with no API key."""
    import importlib.util
    from pathlib import Path

    path = Path(pack_root) / "offline_model.py"
    if not path.exists():
        raise ModelError(f"this pack has no offline model ({path} is missing)")
    spec = importlib.util.spec_from_file_location(f"hamilton_offline_{abs(hash(str(path)))}", path)
    if spec is None or spec.loader is None:
        raise ModelError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()
