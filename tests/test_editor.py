import shutil

import pytest
from conftest import DEMO_PACK

from hamilton_harness.editor import EditError, PackEditor, list_conversations, read_conversation


@pytest.fixture
def editor(tmp_path):
    return PackEditor(shutil.copytree(DEMO_PACK, tmp_path / "pack"))


def test_update_section_keeps_untouched_fields(editor):
    editor.update_section("widget", {"accent": "#2563EB"})
    widget = editor.load().widget
    assert widget.accent == "#2563eb"
    assert widget.launcher_label == "Chat with Loop"


def test_invalid_edit_is_refused_and_leaves_the_file_alone(editor):
    before = (editor.root / "scope.yaml").read_text()
    with pytest.raises(EditError, match="refuse"):
        editor.update_section("scope", {"refuse": ["everything"]})
    assert (editor.root / "scope.yaml").read_text() == before


def test_unknown_section_is_reported_as_missing(editor):
    with pytest.raises(EditError) as caught:
        editor.update_section("tools", {})
    assert caught.value.missing


def test_a_rule_that_breaks_the_pack_is_rolled_back(editor):
    before = (editor.root / "policies.yaml").read_text()
    rules = [rule.model_dump(mode="json") for rule in editor.load().policies]
    rules[0]["tool"] = "no_such_tool"
    with pytest.raises(EditError, match="unknown tool"):
        editor.save_policies(rules)
    assert (editor.root / "policies.yaml").read_text() == before


def test_knowledge_round_trip(editor):
    editor.save_knowledge("gift-cards.md", "# Gift cards\nThey never expire.\n")
    assert "never expire" in editor.read_knowledge("gift-cards.md")
    editor.delete_knowledge("gift-cards.md")
    with pytest.raises(EditError) as caught:
        editor.read_knowledge("gift-cards.md")
    assert caught.value.missing


def test_knowledge_names_are_checked(editor):
    for name in ("../persona.yaml", "notes.txt", "a/b.md"):
        with pytest.raises(EditError, match="file name"):
            editor.save_knowledge(name, "x")


def test_on_change_runs_only_after_a_successful_edit(tmp_path):
    calls = []
    editor = PackEditor(
        shutil.copytree(DEMO_PACK, tmp_path / "pack"), on_change=lambda: calls.append(1)
    )
    editor.update_section("handoff", {"max_guard_blocks": 3})
    with pytest.raises(EditError):
        editor.update_section("handoff", {"max_guard_blocks": 0})
    assert calls == [1]


def test_fake_customers_run_against_the_pack_on_disk(editor):
    assert editor.run_fake_customers()["summary"]["passed"] == 16
    # Raising the refund limit lets a refund through that a scenario expects to be blocked.
    rules = [rule.model_dump(mode="json") for rule in editor.load().policies]
    next(r for r in rules if r["id"] == "refund-limit")["limits"][0]["max"] = 99999
    editor.save_policies(rules)
    report = editor.run_fake_customers()
    failed = [r["id"] for r in report["results"] if not r["passed"]]
    assert "refund-over-limit" in failed and "prompt-injection" in failed


def test_conversations_without_a_trace_folder():
    assert list_conversations(None) == []
    with pytest.raises(EditError):
        read_conversation(None, "0123456789ab")
