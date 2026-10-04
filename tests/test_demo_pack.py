def test_demo_pack_loads(pack):
    assert pack.persona.name == "Maya"
    assert {t.name for t in pack.tools} == {
        "lookup_order",
        "issue_refund",
        "create_exchange",
        "send_tracking_link",
    }
    assert [r.tool_name for r in pack.records] == ["create_order", "create_quote"]
    assert len(pack.examples) == 3
    assert len(pack.knowledge) == 4


def test_demo_refund_limit_is_enforceable(pack):
    rule = next(r for r in pack.policies if r.id == "refund-limit")
    assert rule.tool == "issue_refund"
    assert rule.limits[0].max == 3000
    assert rule.on_violation == "handoff"
