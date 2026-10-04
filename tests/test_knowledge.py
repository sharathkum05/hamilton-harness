from repkit.knowledge import KnowledgeBase, split_markdown, tokenize
from repkit.pack.schema import KnowledgeDoc


def test_tokenize_drops_stopwords_and_punctuation():
    assert tokenize("Where is my ORDER?!") == ["order"]


def test_split_keeps_the_heading_trail():
    text = "# Shipping\n\n## Times\nThree days.\n\n## Cost\nFree.\n"
    doc = KnowledgeDoc(source="s.md", text=text)
    chunks = split_markdown(doc)
    assert [c.heading for c in chunks] == ["Shipping > Times", "Shipping > Cost"]
    assert chunks[0].text == "Three days."


def test_text_before_any_heading_uses_the_file_name():
    chunks = split_markdown(KnowledgeDoc(source="notes.md", text="Open nine to five."))
    assert chunks[0].heading == "notes.md"


def test_search_finds_the_relevant_section(pack):
    kb = KnowledgeBase(pack.knowledge)
    top = kb.search("how long does a refund take to show up")[0]
    assert top.source == "returns.md"
    assert "Refund timing" in top.heading


def test_search_matches_on_headings(pack):
    kb = KnowledgeBase(pack.knowledge)
    assert kb.search("sizing for the drift runner")[0].source == "sizing.md"


def test_search_returns_nothing_for_unrelated_text(pack):
    assert KnowledgeBase(pack.knowledge).search("zebra quantum xylophone") == []


def test_search_respects_top_k(pack):
    assert len(KnowledgeBase(pack.knowledge).search("delivery order refund size", top_k=2)) == 2


def test_empty_knowledge_base_is_safe():
    assert KnowledgeBase([]).search("anything") == []
