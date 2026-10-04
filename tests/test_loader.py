import pytest

from repkit.pack import PackError, load_pack
from repkit.pack.loader import parse_example


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def minimal(root):
    write(root, "persona.yaml", "name: Maya\ncompany: Loop Sneakers\n")


def test_missing_directory(tmp_path):
    with pytest.raises(PackError, match="no pack directory"):
        load_pack(tmp_path / "nope")


def test_persona_is_required(tmp_path):
    with pytest.raises(PackError, match="persona.yaml is missing"):
        load_pack(tmp_path)


def test_minimal_pack_loads_with_defaults(tmp_path):
    minimal(tmp_path)
    pack = load_pack(tmp_path)
    assert pack.persona.name == "Maya"
    assert pack.tools == []
    assert pack.handoff.on_request is True


def test_bad_yaml_is_reported_by_file(tmp_path):
    write(tmp_path, "persona.yaml", "name: [unclosed\n")
    with pytest.raises(PackError, match="persona.yaml is not valid YAML"):
        load_pack(tmp_path)


def test_validation_errors_name_the_field(tmp_path):
    write(tmp_path, "persona.yaml", "name: Maya\n")
    with pytest.raises(PackError, match="persona.company"):
        load_pack(tmp_path)


def test_policies_accept_list_or_mapping(tmp_path):
    minimal(tmp_path)
    write(tmp_path, "policies.yaml", "policies:\n  - id: kind\n    text: Be kind.\n")
    assert load_pack(tmp_path).policies[0].id == "kind"
    write(tmp_path, "policies.yaml", "- id: kind\n  text: Be kind.\n")
    assert load_pack(tmp_path).policies[0].id == "kind"


def test_examples_and_knowledge_are_read_in_name_order(tmp_path):
    minimal(tmp_path)
    write(tmp_path, "examples/b.md", "customer: hi\nrep: hey!\n")
    write(tmp_path, "examples/a.md", "customer: hello\nrep: hi there\n")
    write(tmp_path, "knowledge/shipping.md", "# Shipping\nThree days.\n")
    pack = load_pack(tmp_path)
    assert [e.title for e in pack.examples] == ["a", "b"]
    assert pack.knowledge[0].source == "shipping.md"


def test_example_lines_without_speaker_continue_the_turn():
    chat = parse_example("t", "customer: where is\nmy order\nrep: let me check")
    assert chat.turns[0].text == "where is my order"
    assert chat.turns[1].speaker == "rep"


def test_example_must_start_with_a_speaker():
    with pytest.raises(PackError, match="must start with"):
        parse_example("t", "hello there")
