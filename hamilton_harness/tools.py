"""Run the actions a pack allows.

The registry turns `tools.yaml` into the tool list the model sees and executes
calls against the pack's own handler code. It validates arguments itself, so a
malformed call never reaches a company system.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from jsonschema import Draft202012Validator

from hamilton_harness.pack.schema import Pack, RecordType, ToolSpec
from hamilton_harness.records import MemoryRecordStore, RecordStore, input_schema, tool_description

log = logging.getLogger(__name__)


class ToolError(Exception):
    """A tool is misconfigured in the pack."""


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str
    data: Any = None


def _fail(message: str) -> ToolResult:
    return ToolResult(ok=False, content=message)


class ToolRegistry:
    def __init__(self, pack: Pack, records: RecordStore | None = None) -> None:
        self.records = records or MemoryRecordStore()
        self._record_types: dict[str, RecordType] = {}
        self._root = Path(pack.root) if pack.root else None
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._validators: dict[str, Draft202012Validator] = {}
        self._modules: dict[str, ModuleType] = {}
        for spec in pack.tools:
            if spec.name in self._specs:
                raise ToolError(f"tool '{spec.name}' is defined twice")
            Draft202012Validator.check_schema(spec.input_schema)
            self._specs[spec.name] = spec
            self._validators[spec.name] = Draft202012Validator(spec.input_schema)
            self._handlers[spec.name] = self._resolve(spec)
        for record_type in pack.records:
            # Each record type is an action the harness provides itself.
            spec = ToolSpec(
                name=record_type.tool_name,
                description=tool_description(record_type),
                input_schema=input_schema(record_type),
                handler="hamilton:records",
                remember={f"last_{record_type.name}": "reference"},
            )
            self._specs[spec.name] = spec
            self._validators[spec.name] = Draft202012Validator(spec.input_schema)
            self._record_types[spec.name] = record_type

    def _module(self, name: str) -> ModuleType:
        if name in self._modules:
            return self._modules[name]
        if self._root is None:
            raise ToolError("pack has no directory to load handlers from")
        path = self._root / f"{name}.py"
        if not path.exists():
            raise ToolError(f"handler module {path} does not exist")
        # Two packs may both ship a handlers.py, so key the module on its path.
        digest = hashlib.sha1(str(path).encode()).hexdigest()[:10]
        spec = importlib.util.spec_from_file_location(f"hamilton_pack_{digest}_{name}", path)
        if spec is None or spec.loader is None:
            raise ToolError(f"cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._modules[name] = module
        return module

    def _resolve(self, spec: ToolSpec) -> Callable[..., Any]:
        module_name, _, function_name = spec.handler.partition(":")
        if not module_name or not function_name:
            raise ToolError(f"tool '{spec.name}' handler must look like 'module:function'")
        handler = getattr(self._module(module_name), function_name, None)
        if not callable(handler):
            raise ToolError(f"tool '{spec.name}' handler {spec.handler} is not a function")
        return handler

    def names(self) -> list[str]:
        return sorted(self._specs)

    def spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def module(self, name: str) -> ModuleType:
        return self._module(name)

    def definitions(self) -> list[dict[str, Any]]:
        """Tool list for the model, in a fixed order so the prompt prefix stays cacheable."""
        return [
            {
                "name": spec.name,
                "description": " ".join(spec.description.split()),
                "input_schema": spec.input_schema,
            }
            for spec in sorted(self._specs.values(), key=lambda s: s.name)
        ]

    def validate(self, name: str, arguments: Any) -> str | None:
        """Why these arguments are unusable, or None if they are fine."""
        if name not in self._specs:
            return f"There is no tool called {name}."
        if not isinstance(arguments, dict):
            return "Tool arguments must be an object."
        errors = sorted(self._validators[name].iter_errors(arguments), key=lambda e: list(e.path))
        if not errors:
            return None
        first = errors[0]
        where = ".".join(str(p) for p in first.path)
        return f"Invalid arguments{f' at {where}' if where else ''}: {first.message}"

    def call(self, name: str, arguments: Any, *, conversation_id: str = "") -> ToolResult:
        problem = self.validate(name, arguments)
        if problem:
            return _fail(problem)
        if name in self._record_types:
            record = self.records.add(self._record_types[name].name, arguments, conversation_id)
            data = {"reference": record.id, "status": "received", **arguments}
            return ToolResult(ok=True, content=json.dumps(data, ensure_ascii=False), data=data)
        try:
            data = self._handlers[name](**arguments)
        except (LookupError, ValueError) as exc:
            # Handlers raise these for things the rep can explain to the customer.
            return _fail(str(exc))
        except Exception:
            log.exception("tool %s crashed", name)
            return _fail("That system is not responding right now.")
        return ToolResult(
            ok=True, content=json.dumps(data, ensure_ascii=False, default=str), data=data
        )
