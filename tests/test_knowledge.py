from hamilton_harness.knowledge import KnowledgeBase, split_markdown, tokenize
from hamilton_harness.pack.schema import KnowledgeDoc


def test_tokenize_drops_stopwords_and_punctuation():
    assert tokenize("Where is my ORDER?!") == ["order"]


def test_tokenize_folds_plurals():
    assert tokenize("bedrooms flats treatments dogs") == ["bedroom", "flat", "treatment", "dog"]
    assert tokenize("deliveries boxes watches addresses") == ["delivery", "box", "watch", "address"]


def test_tokenize_leaves_words_that_only_look_plural():
    assert tokenize("address glass status basis gas") == [
        "address",
        "glass",
        "status",
        "basis",
        "gas",
    ]


def test_tokenize_folds_a_word_and_its_plural_to_the_same_thing():
    for single, plural in [("size", "sizes"), ("shoe", "shoes"), ("brace", "braces")]:
        assert tokenize(single) == tokenize(plural)


def test_tokenize_reads_spelled_out_numbers():
    assert tokenize("two bedrooms") == tokenize("2 bedroom") == ["2", "bedroom"]
    assert tokenize("twelve") == ["12"]


def test_search_finds_a_note_written_in_the_singular():
    notes = "## Flat 4\nA 2 bedroom flat. Dogs are not allowed.\n\n## Viewings\nBring photo ID.\n"
    base = KnowledgeBase([KnowledgeDoc(source="homes.md", text=notes)])
    assert base.search("two bedrooms")[0].heading == "Flat 4"
    assert [c.heading for c in base.search("what about my dog")] == ["Flat 4"]


def test_split_keeps_the_heading_trail():
    text = "# Shipping\n\n## Times\nThree days.\n\n## Cost\nFree.\n"
    doc = KnowledgeDoc(source="s.md", text=text)
    chunks = split_markdown(doc)
    assert [c.heading for c in chunks] == ["Shipping > Times", "Shipping > Cost"]
    assert chunks[0].text == "Three days."


def test_sibling_headings_are_not_nested_when_a_file_has_no_title():
    text = "## Times\nThree days.\n\n## Cost\nFree.\n\n### Abroad\nNot free.\n\n## Returns\nYes.\n"
    chunks = split_markdown(KnowledgeDoc(source="s.md", text=text))
    assert [c.heading for c in chunks] == ["Times", "Cost", "Cost > Abroad", "Returns"]


def test_a_skipped_heading_level_does_not_confuse_the_trail():
    text = "# Shop\n\n### Hours\nNine to five.\n\n## Parking\nFree.\n"
    chunks = split_markdown(KnowledgeDoc(source="s.md", text=text))
    assert [c.heading for c in chunks] == ["Shop > Hours", "Shop > Parking"]


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
