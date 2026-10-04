import pytest

from repkit.llm import ScriptedModel
from repkit.pack import PackError
from repkit.sim import Expect, Scenario, Scorecard, load_scenarios, run_scenario, run_scenarios


def scripted(steps):
    return lambda scenario: ScriptedModel(steps)


def test_demo_scenarios_all_pass_in_replay(pack):
    scorecard = run_scenarios(pack, load_scenarios(pack))
    assert scorecard.ok, scorecard.render()
    summary = scorecard.summary()
    assert summary["scenarios"] == 13
    assert summary["actions_blocked"] == 3
    assert summary["replies_replaced"] == 3
    assert summary["off_topic_refused"] == 2
    assert summary["handoffs"] == 4


def test_scenarios_do_not_share_state(pack):
    scenario = next(s for s in load_scenarios(pack) if s.id == "double-charge")
    # The same refund twice would exceed what was paid if state leaked.
    assert run_scenario(pack, scenario, scripted(list(scenario.replay))).passed
    assert run_scenario(pack, scenario, scripted(list(scenario.replay))).passed


def test_failed_checks_are_reported(pack):
    scenario = Scenario(
        id="wrong",
        says=["where is LS-4471"],
        expect=Expect(called=["issue_refund"], says=["Friday"], handoff=True),
    )
    result = run_scenario(pack, scenario, scripted(["It's due Thursday."]))
    assert not result.passed
    assert [c.name for c in result.failures] == [
        "called issue_refund",
        "handoff is True",
        "says /Friday/",
    ]


def test_never_says_catches_a_bad_reply(pack):
    scenario = Scenario(id="s", says=["hi"], expect=Expect(never_says=["guarantee"]))
    result = run_scenario(pack, scenario, scripted(["I guarantee it arrives Monday."]))
    assert result.failures[0].detail == "I guarantee it arrives Monday."


def test_a_crash_fails_the_scenario_not_the_run(pack):
    def explode(scenario):
        raise RuntimeError("no model")

    scenario = Scenario(id="s", says=["hi"])
    scorecard = Scorecard([run_scenario(pack, scenario, explode)])
    assert not scorecard.ok
    assert "crashed: RuntimeError: no model" in scorecard.render()


def test_customer_stops_talking_after_a_handoff(pack):
    scenario = Scenario(id="s", says=["get me a manager", "hello?", "anyone?"])
    assert len(run_scenario(pack, scenario, scripted([])).turns) == 1


def test_cost_is_only_reported_for_known_models(pack):
    scenario = Scenario(id="s", says=["hi"])
    results = [run_scenario(pack, scenario, scripted(["Hi there, how can I help?"]))]
    assert Scorecard(results, model="scripted").cost_usd() is None
    priced = Scorecard(results, model="claude-opus-5-5")
    assert priced.cost_usd() == pytest.approx(6 * 20.00 / 1_000_000)


def test_render_lists_failures(pack):
    scenario = Scenario(id="late", customer="polite", says=["hi"], expect=Expect(handoff=True))
    text = Scorecard([run_scenario(pack, scenario, scripted(["Hello!"]))]).render()
    assert "FAIL  late  (polite)" in text
    assert "failed: handoff is True  [got False]" in text
    assert "0/1 scenarios passed" in text


def test_missing_scenarios_file(pack, tmp_path):
    with pytest.raises(PackError, match="no scenarios file"):
        load_scenarios(pack, tmp_path / "nope.yaml")


def test_duplicate_scenario_ids_are_rejected(pack, tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text("- {id: a, says: [hi]}\n- {id: a, says: [yo]}\n", encoding="utf-8")
    with pytest.raises(PackError, match="duplicate scenario ids"):
        load_scenarios(pack, path)
