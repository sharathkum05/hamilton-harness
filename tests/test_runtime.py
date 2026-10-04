import pytest

from repkit.llm import ModelError, ScriptedModel
from repkit.memory import InMemoryStore
from repkit.runtime import Agent
from repkit.trace import read_trace


def lookup(order_id="LS-4471"):
    return {"tool": "lookup_order", "args": {"order_id": order_id}}


def refund(order_id, amount, reason="duplicate_charge"):
    args = {"order_id": order_id, "amount_inr": amount, "reason": reason}
    return {"tool": "issue_refund", "args": args}


def agent_for(pack, steps, **kwargs):
    model = ScriptedModel(steps, supports_system_turns=kwargs.pop("system_turns", True))
    return Agent(pack, model, retry_wait=0, **kwargs), model


def orders(agent):
    return agent.tools.module("handlers").ORDERS


def assert_history_is_well_formed(messages):
    """Every tool_use is answered in the next message, and roles never repeat badly."""
    for index, message in enumerate(messages):
        content = message["content"]
        if message["role"] != "assistant" or isinstance(content, str):
            continue
        ids = [b["id"] for b in content if b["type"] == "tool_use"]
        if ids:
            answers = messages[index + 1]
            assert answers["role"] == "user"
            assert [b["tool_use_id"] for b in answers["content"]] == ids
    assert messages[0]["role"] == "user"
    assert messages[-1]["role"] == "assistant"


def test_plain_reply(pack):
    agent, model = agent_for(pack, ["Hi! What's the order number?"])
    conversation = agent.start()
    result = agent.respond(conversation, "hello")
    assert result.text == "Hi! What's the order number?"
    assert result.model_calls == 1
    assert result.handoff is None
    assert [m["role"] for m in conversation.messages] == ["user", "assistant"]
    assert model.calls[0]["system"] == agent.context.system_prompt


def test_lookup_then_answer(pack):
    agent, model = agent_for(pack, [lookup(), "Found it, Priya. It's due Thursday 8 October."])
    conversation = agent.start()
    result = agent.respond(conversation, "where is my order LS-4471")
    assert [a.outcome for a in result.actions] == ["ok"]
    assert result.model_calls == 2
    assert "Thursday" in result.text
    # The second call saw the order details the first one fetched.
    tool_result = model.calls[1]["messages"][-1]["content"][0]
    assert "promised_delivery" in tool_result["content"]
    assert tool_result["is_error"] is False
    assert_history_is_well_formed(conversation.messages)


def test_context_reaches_the_model_as_a_system_turn(pack):
    agent, model = agent_for(pack, ["3 to 5 working days."])
    agent.respond(agent.start(), "how long does a refund take?")
    sent = model.calls[0]["messages"]
    assert [m["role"] for m in sent] == ["user", "system"]
    assert "[refund-limit]" in sent[1]["content"]
    assert "Refund timing" in sent[1]["content"]


def test_context_falls_back_to_the_user_turn(pack):
    agent, model = agent_for(pack, ["3 to 5 working days."], system_turns=False)
    agent.respond(agent.start(), "how long does a refund take?")
    (sent,) = model.calls[0]["messages"]
    assert sent["role"] == "user"
    assert sent["content"][0]["text"].startswith("<context>")


def test_refund_under_the_limit_runs(pack):
    agent, _ = agent_for(pack, [lookup(), refund("LS-4471", 2499), "Refunded ₹2,499, Priya."])
    result = agent.respond(agent.start(), "I was charged twice on LS-4471")
    assert [a.outcome for a in result.actions] == ["ok", "ok"]
    assert orders(agent)["LS-4471"]["refunded_inr"] == 2499
    assert result.handoff is None


def test_refund_over_the_limit_never_runs_and_hands_off(pack):
    agent, model = agent_for(pack, [refund("LS-6033", 4199, "damaged"), "never reached"])
    conversation = agent.start()
    result = agent.respond(conversation, "my trail loops arrived damaged, refund me")
    assert result.actions[0].outcome == "blocked"
    assert result.actions[0].rule_ids == ("refund-limit",)
    assert orders(agent)["LS-6033"]["refunded_inr"] == 0
    assert result.handoff.reason == "guard"
    assert result.text == pack.handoff.message
    assert len(model.calls) == 1
    assert_history_is_well_formed(conversation.messages)


def test_blocked_action_is_explained_to_the_model(pack):
    steps = [refund("LS-5120", 2499, "changed_mind"), "I can't refund that, but you can return it."]
    agent, model = agent_for(pack, steps)
    conversation = agent.start()
    result = agent.respond(conversation, "refund LS-5120, I changed my mind")
    assert result.actions[0].outcome == "blocked"
    assert result.handoff is None
    assert conversation.guard_blocks == 1
    blocked = model.calls[1]["messages"][-1]["content"][0]
    assert blocked["is_error"] is True
    assert "refund-reasons" in blocked["content"]
    assert "Do not retry" in blocked["content"]
    assert orders(agent)["LS-5120"]["refunded_inr"] == 0


def test_a_second_blocked_action_hands_off(pack):
    again = refund("LS-5120", 2499, "changed_mind")
    agent, _ = agent_for(pack, [again, again, "never reached"])
    result = agent.respond(agent.start(), "refund LS-5120 please, changed my mind")
    assert [a.outcome for a in result.actions] == ["blocked", "blocked"]
    assert result.handoff.reason == "guard"
    assert result.handoff.detail == "2 blocked actions"


def test_invalid_arguments_are_returned_to_the_model(pack):
    bad = {"tool": "lookup_order", "args": {"order": "LS-4471"}}
    agent, model = agent_for(pack, [bad, lookup(), "Found it."])
    result = agent.respond(agent.start(), "where is LS-4471")
    assert [a.outcome for a in result.actions] == ["invalid", "ok"]
    assert "Invalid arguments" in model.calls[1]["messages"][-1]["content"][0]["content"]


def test_parallel_actions_are_answered_in_one_message(pack):
    agent, _ = agent_for(pack, [[lookup("LS-4471"), lookup("LS-5120")], "Both look fine."])
    conversation = agent.start()
    agent.respond(conversation, "check LS-4471 and LS-5120")
    answers = conversation.messages[-2]["content"]
    assert len(answers) == 2
    assert_history_is_well_formed(conversation.messages)


def test_asking_for_a_human_skips_the_model(pack):
    agent, model = agent_for(pack, ["never reached"])
    conversation = agent.start()
    result = agent.respond(conversation, "I want to talk to a manager")
    assert result.handoff.reason == "requested"
    assert model.calls == []
    assert conversation.handed_off


def test_the_rep_stays_out_after_a_handoff(pack):
    agent, model = agent_for(pack, ["never reached"])
    conversation = agent.start()
    agent.respond(conversation, "this is fraud")
    result = agent.respond(conversation, "hello??")
    assert result.handoff.reason == "phrase"
    assert model.calls == []
    assert_history_is_well_formed(conversation.messages)


def test_discount_promise_is_replaced(pack):
    agent, _ = agent_for(pack, ["Sure, I can do 20% off for you!"])
    conversation = agent.start()
    result = agent.respond(conversation, "any deals today?")
    assert result.replaced_by == "no-discounts"
    assert "20%" not in result.text
    assert "can't change prices" in result.text
    # The history holds what the customer saw, not the rejected draft.
    assert conversation.messages[-1]["content"] == next(
        r.safe_reply for r in pack.policies if r.id == "no-discounts"
    )


def test_claiming_to_be_human_is_replaced_with_the_disclosure(pack):
    agent, _ = agent_for(pack, ["Haha yes, I'm a real person!"])
    result = agent.respond(agent.start(), "are you a real person?")
    assert result.replaced_by == "honesty"
    assert result.text == pack.persona.disclosure
    assert result.handoff is None


def test_reply_is_shaped(pack):
    draft = "I apologize for the inconvenience. **Your order** ships tomorrow — promise."
    agent, _ = agent_for(pack, [draft])
    result = agent.respond(agent.start(), "hello")
    assert result.text == "Your order ships tomorrow, promise."


def test_facts_are_remembered_across_conversations(pack):
    store = InMemoryStore()
    agent, _ = agent_for(pack, [lookup(), "Due Thursday."], store=store)
    agent.respond(agent.start("priya@example.com"), "where is LS-4471")
    assert store.load("priya@example.com")["name"] == "Priya"

    agent, model = agent_for(pack, ["Hi Priya!"], store=store)
    agent.respond(agent.start("priya@example.com"), "hi again")
    assert "name: Priya" in model.calls[0]["messages"][1]["content"]


def test_retryable_model_error_is_retried_once(pack):
    failures = iter([ModelError("overloaded", retryable=True)])

    def flaky(messages):
        error = next(failures, None)
        if error:
            raise error
        return "Back now. How can I help?"

    agent, model = agent_for(pack, [flaky, flaky])
    result = agent.respond(agent.start(), "hello")
    assert result.text == "Back now. How can I help?"
    assert result.model_calls == 1
    assert len(model.calls) == 2


def test_fatal_model_error_hands_off(pack):
    def broken(messages):
        raise ModelError("credentials rejected")

    agent, _ = agent_for(pack, [broken])
    conversation = agent.start()
    result = agent.respond(conversation, "hello")
    assert result.handoff.reason == "error"
    assert result.text == pack.handoff.message
    assert_history_is_well_formed(conversation.messages)


def test_empty_model_reply_hands_off(pack):
    agent, _ = agent_for(pack, [""])
    assert agent.respond(agent.start(), "hello").handoff.reason == "error"


def test_runaway_tool_loops_hand_off(pack):
    agent, _ = agent_for(pack, [lookup()] * 3, max_steps=3)
    result = agent.respond(agent.start(), "where is LS-4471")
    assert result.handoff.detail == "too many steps in one turn"


def test_turn_is_traced_to_disk(pack, tmp_path):
    agent, _ = agent_for(pack, [lookup(), "Due Thursday."], trace_dir=tmp_path)
    conversation = agent.start()
    result = agent.respond(conversation, "where is my order LS-4471")
    kinds = [event.kind for event in result.events]
    assert kinds == ["customer", "context", "model", "action", "model", "shaped", "turn_end"]
    records = read_trace(tmp_path / f"{conversation.id}.jsonl")
    assert [r["kind"] for r in records] == kinds
    assert records[3]["tool"] == "lookup_order"


def test_trace_is_written_even_when_the_turn_crashes(pack, tmp_path):
    def explode(messages):
        raise RuntimeError("bug")

    agent, _ = agent_for(pack, [explode], trace_dir=tmp_path)
    conversation = agent.start()
    with pytest.raises(RuntimeError):
        agent.respond(conversation, "hello")
    assert read_trace(tmp_path / f"{conversation.id}.jsonl")[-1]["kind"] == "turn_end"


def test_off_topic_message_never_reaches_the_model(pack):
    agent, model = agent_for(pack, ["never reached"])
    conversation = agent.start()
    result = agent.respond(conversation, "what is 348 * 12")
    assert result.refused == "math"
    assert result.text == pack.scope.off_topic_reply
    assert model.calls == []
    assert result.handoff is None
    assert_history_is_well_formed(conversation.messages)
    assert "scope_refused" in [event.kind for event in result.events]


def test_conversation_continues_after_an_off_topic_message(pack):
    agent, model = agent_for(pack, [lookup(), "Found it, Priya. It's due Thursday 8 October."])
    conversation = agent.start()
    agent.respond(conversation, "write me a poem")
    result = agent.respond(conversation, "ok, where is LS-4471")
    assert result.refused == ""
    assert "Thursday" in result.text


def test_invented_number_is_replaced(pack):
    agent, _ = agent_for(pack, ["Express gets there in 6 hours for just ₹49!"])
    conversation = agent.start()
    result = agent.respond(conversation, "how fast is express delivery")
    assert result.replaced_by == "grounding"
    assert result.text == pack.scope.unsure_reply
    assert conversation.messages[-1]["content"] == pack.scope.unsure_reply
    blocked = next(e for e in result.events if e.kind == "reply_blocked")
    assert blocked.data["matched"] == "49, 6"


def test_numbers_from_notes_and_tools_are_allowed(pack):
    agent, _ = agent_for(pack, ["Express takes 1 to 2 working days and costs ₹199."])
    result = agent.respond(agent.start(), "how fast is express delivery")
    assert result.replaced_by == ""
    assert "₹199" in result.text


def test_numbers_the_customer_said_are_allowed(pack):
    agent, _ = agent_for(pack, ["Got it, a UK 9. Which order is it?"])
    result = agent.respond(agent.start(), "I need a size 9 instead")
    assert result.replaced_by == ""


def test_example_chats_do_not_count_as_evidence(pack):
    # ₹2,499 appears in the example chats, but this customer never mentioned it.
    agent, _ = agent_for(pack, ["I've refunded ₹2,499 for you."])
    assert agent.respond(agent.start(), "hello").replaced_by == "grounding"


def test_grounding_can_be_switched_off(pack):
    relaxed = pack.model_copy(
        update={"scope": pack.scope.model_copy(update={"ground_numbers": False})}
    )
    agent, _ = agent_for(relaxed, ["It arrives in 6 hours."])
    assert agent.respond(agent.start(), "hello").replaced_by == ""


def test_strict_scope_lets_an_answer_to_the_reps_question_through(pack):
    strict = pack.model_copy(update={"scope": pack.scope.model_copy(update={"strict": True})})
    agent, model = agent_for(strict, ["Sure. What's your name?", "Thanks, Zubin."])
    conversation = agent.start()
    agent.respond(conversation, "hello")
    result = agent.respond(conversation, "Zubin Mistry")
    assert result.refused == ""
    assert len(model.calls) == 2
    assert agent.respond(conversation, "tell me about black holes").refused == "strict"


def test_with_pack_keeps_the_model_store_and_trace_dir(pack, tmp_path):
    store = InMemoryStore()
    agent, model = agent_for(pack, ["Hello!"], store=store, trace_dir=tmp_path, max_steps=3)
    renamed = pack.model_copy(update={"persona": pack.persona.model_copy(update={"name": "Zoya"})})
    swapped = agent.with_pack(renamed)
    assert swapped.model is model
    assert swapped.store is store
    assert swapped.trace_dir == tmp_path
    assert "You are Zoya" in swapped.context.system_prompt
