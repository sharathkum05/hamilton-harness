import json

import pytest

from hamilton_harness.pack.schema import Pack, Persona, ToolSpec
from hamilton_harness.tools import ToolError, ToolRegistry

SCHEMA = {
    "type": "object",
    "properties": {"n": {"type": "integer"}},
    "required": ["n"],
    "additionalProperties": False,
}


def make_pack(
    tmp_path, handler="handlers:double", source="def double(n):\n    return {'n': n * 2}\n"
):
    (tmp_path / "handlers.py").write_text(source, encoding="utf-8")
    tool = ToolSpec(
        name="double", description="Double  a\nnumber.", input_schema=SCHEMA, handler=handler
    )
    return Pack(persona=Persona(name="M", company="C"), tools=[tool], root=str(tmp_path))


def test_definitions_are_sorted_and_single_line(pack):
    definitions = ToolRegistry(pack).definitions()
    assert [d["name"] for d in definitions] == sorted(d["name"] for d in definitions)
    assert all("\n" not in d["description"] for d in definitions)


def test_call_runs_the_handler(tmp_path):
    result = ToolRegistry(make_pack(tmp_path)).call("double", {"n": 4})
    assert result.ok
    assert json.loads(result.content) == {"n": 8}
    assert result.data == {"n": 8}


def test_bad_arguments_never_reach_the_handler(tmp_path):
    registry = ToolRegistry(make_pack(tmp_path))
    assert "Invalid arguments" in registry.call("double", {"n": "four"}).content
    assert "Invalid arguments" in registry.call("double", {"n": 1, "extra": 2}).content
    assert not registry.call("double", "nope").ok


def test_unknown_tool(tmp_path):
    result = ToolRegistry(make_pack(tmp_path)).call("triple", {})
    assert not result.ok
    assert "no tool called triple" in result.content


def test_expected_handler_errors_are_passed_on(pack):
    result = ToolRegistry(pack).call("lookup_order", {"order_id": "LS-0000"})
    assert not result.ok
    assert "No order LS-0000" in result.content


def test_crashes_are_hidden_from_the_model(tmp_path):
    source = "def double(n):\n    raise RuntimeError('db password is hunter2')\n"
    result = ToolRegistry(make_pack(tmp_path, source=source)).call("double", {"n": 1})
    assert not result.ok
    assert "hunter2" not in result.content


def test_missing_handler_function(tmp_path):
    with pytest.raises(ToolError, match="is not a function"):
        ToolRegistry(make_pack(tmp_path, handler="handlers:missing"))


def test_handler_must_name_module_and_function(tmp_path):
    with pytest.raises(ToolError, match="module:function"):
        ToolRegistry(make_pack(tmp_path, handler="double"))


def test_demo_refund_cannot_exceed_what_was_paid(pack):
    registry = ToolRegistry(pack)
    registry.module("handlers").reset()
    args = {"order_id": "LS-5120", "amount_inr": 9999, "reason": "damaged"}
    assert "Only ₹2499 has been paid" in registry.call("issue_refund", args).content
