"""Run one customer message through the harness.

The model writes a draft in the middle. Everything around it is code:

    customer message
      -> handoff check on the customer's own words
      -> context for this message (rules, notes, what we know)
      -> model drafts a reply or proposes actions
      -> every action is validated, then checked by the guard, then run
      -> the reply is checked by the guard, then shaped into chat bubbles
      -> every step is traced
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from repkit.context import ContextBuilder, user_turn
from repkit.guard import PolicyGuard
from repkit.handoff import HandoffDecision, HandoffDetector
from repkit.llm import Model, ModelError, ModelResponse, ToolCall, Usage
from repkit.memory import Conversation, CustomerStore, InMemoryStore, facts_from_result
from repkit.pack.schema import Pack
from repkit.scope import ScopeGate, evidence_text, ungrounded_numbers
from repkit.shaper import Bubble, ReplyShaper
from repkit.tools import ToolRegistry
from repkit.trace import Event, Trace, TraceWriter

Outcome = Literal["ok", "error", "invalid", "blocked"]


@dataclass(frozen=True)
class ActionRecord:
    tool: str
    arguments: Any
    outcome: Outcome
    detail: str = ""
    rule_ids: tuple[str, ...] = ()


@dataclass
class TurnResult:
    bubbles: list[Bubble]
    handoff: HandoffDecision | None = None
    actions: list[ActionRecord] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latency_ms: float = 0.0
    model_calls: int = 0
    # Rule that replaced the model's draft, if the reply guard stepped in.
    replaced_by: str = ""
    # Why the message was turned away as off topic, if it was.
    refused: str = ""
    dropped: list[str] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(b.text for b in self.bubbles)


def _blocked_message(explanation: str, *, escalated: bool) -> str:
    ending = (
        "A human colleague is taking over this conversation."
        if escalated
        else "Do not retry this action. Tell the customer plainly what you can't do and "
        "what they can do instead."
    )
    return f"Blocked by company policy. {explanation} {ending}"


class Agent:
    def __init__(
        self,
        pack: Pack,
        model: Model,
        *,
        store: CustomerStore | None = None,
        trace_dir: str | Path | None = None,
        max_steps: int = 6,
        retry_wait: float = 0.5,
    ) -> None:
        self.pack = pack
        self.model = model
        self.tools = ToolRegistry(pack)
        self.guard = PolicyGuard(pack.policies, pack.persona)
        self.handoffs = HandoffDetector(pack.handoff)
        self.context = ContextBuilder(pack)
        self.scope = ScopeGate(pack.scope)
        self.shaper = ReplyShaper(pack.persona)
        # Fixed lines the rep may say, whose numbers therefore count as given.
        self._static_evidence = " ".join(
            [
                pack.persona.disclosure,
                pack.widget.greeting,
                pack.handoff.message,
                pack.scope.off_topic_reply,
                pack.scope.unsure_reply,
                *(rule.safe_reply for rule in pack.policies),
                *(rule.text for rule in pack.policies if not rule.topics),
            ]
        )
        self.store = store or InMemoryStore()
        self.trace_dir = Path(trace_dir) if trace_dir else None
        self._writer = TraceWriter(trace_dir) if trace_dir else None
        self._tool_definitions = self.tools.definitions()
        self._max_steps = max_steps
        self._retry_wait = retry_wait

    def with_pack(self, pack: Pack) -> Agent:
        """The same agent on a different pack, for when a pack is edited while serving."""
        return Agent(
            pack,
            self.model,
            store=self.store,
            trace_dir=self.trace_dir,
            max_steps=self._max_steps,
            retry_wait=self._retry_wait,
        )

    def start(self, customer_id: str | None = None) -> Conversation:
        facts = self.store.load(customer_id) if customer_id else {}
        return Conversation(customer_id=customer_id, facts=facts)

    # -- one turn -----------------------------------------------------------

    def respond(self, conversation: Conversation, message: str) -> TurnResult:
        started = time.perf_counter()
        conversation.turns += 1
        trace = Trace(conversation.id, turn=conversation.turns)
        trace.add("customer", text=message)
        result = TurnResult(bubbles=[])

        try:
            self._turn(conversation, message, trace, result)
        finally:
            result.latency_ms = (time.perf_counter() - started) * 1000
            trace.add(
                "turn_end",
                bubbles=[b.text for b in result.bubbles],
                handoff=result.handoff.reason if result.handoff else None,
                model_calls=result.model_calls,
                usage=result.usage,
                latency_ms=round(result.latency_ms, 1),
            )
            result.events = trace.events
            if self._writer:
                self._writer.write(trace)
        return result

    def _turn(
        self, conversation: Conversation, message: str, trace: Trace, result: TurnResult
    ) -> None:
        if conversation.handed_off:
            # A human owns this conversation now. The rep stays out of it.
            conversation.messages.append({"role": "user", "content": message})
            self._hand_off(conversation, conversation.handoff, trace, result, repeat=True)
            return

        decision = self.handoffs.check_message(message)
        if decision:
            conversation.messages.append({"role": "user", "content": message})
            self._hand_off(conversation, decision, trace, result)
            return

        context = self.context.for_turn(message, conversation.facts)
        trace.add(
            "context",
            rules=[r.id for r in context.rules],
            notes=[f"{c.source} > {c.heading}" for c in context.notes],
            facts=context.facts,
        )
        answering = conversation.last_reply.rstrip().endswith("?")
        scope = self.scope.check(message, context, answering=answering)
        if not scope.in_scope:
            self._refuse(conversation, message, scope.reason, scope.matched, trace, result)
            return

        conversation.messages.extend(
            user_turn(message, context, system_turns=self.model.supports_system_turns)
        )

        for _ in range(self._max_steps):
            response = self._call_model(conversation, trace, result)
            if response is None:
                return
            if response.tool_calls:
                if self._run_actions(conversation, response, trace, result):
                    return
                continue
            self._reply(conversation, response, trace, result)
            return

        self._hand_off(
            conversation, self.handoffs.for_error("too many steps in one turn"), trace, result
        )

    # -- model --------------------------------------------------------------

    def _call_model(
        self, conversation: Conversation, trace: Trace, result: TurnResult
    ) -> ModelResponse | None:
        """Call the model, retrying once if that might help. None means the turn is over."""
        response = None
        for attempt in (1, 2):
            try:
                response = self.model.complete(
                    system=self.context.system_prompt,
                    messages=conversation.messages,
                    tools=self._tool_definitions,
                )
                break
            except ModelError as error:
                trace.add(
                    "model_error", error=str(error), retryable=error.retryable, attempt=attempt
                )
                if error.retryable and attempt == 1:
                    time.sleep(self._retry_wait)
                    continue
                self._hand_off(conversation, self.handoffs.for_error(str(error)), trace, result)
                return None

        result.model_calls += 1
        result.usage = result.usage + response.usage
        trace.add(
            "model",
            stop_reason=response.stop_reason,
            text=response.text,
            tool_calls=[{"name": c.name, "arguments": c.arguments} for c in response.tool_calls],
            usage=response.usage,
            latency_ms=round(response.latency_ms, 1),
            model=response.model,
        )
        if response.stop_reason == "refusal" or not (response.tool_calls or response.text):
            # Nothing usable came back, so nothing is added to the history.
            detail = f"model stopped with '{response.stop_reason}' and no reply"
            self._hand_off(conversation, self.handoffs.for_error(detail), trace, result)
            return None
        return response

    # -- actions ------------------------------------------------------------

    def _run_actions(
        self,
        conversation: Conversation,
        response: ModelResponse,
        trace: Trace,
        result: TurnResult,
    ) -> bool:
        """Run the proposed actions. True means the turn ended in a handoff."""
        conversation.messages.append({"role": "assistant", "content": response.content})
        escalated: list[str] = []
        outputs = []
        for call in response.tool_calls:
            record, content, needs_human = self._run_action(conversation, call)
            result.actions.append(record)
            trace.add("action", **record.__dict__)
            if needs_human:
                escalated.extend(record.rule_ids)
            outputs.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": content,
                    "is_error": record.outcome != "ok",
                }
            )
        # Every proposed action gets an answer, in one message, even when the turn ends here.
        conversation.messages.append({"role": "user", "content": outputs})

        if escalated:
            self._hand_off(conversation, self.handoffs.for_violation(escalated), trace, result)
            return True
        decision = self.handoffs.check_guard_blocks(conversation.guard_blocks)
        if decision:
            self._hand_off(conversation, decision, trace, result)
            return True
        return False

    def _run_action(
        self, conversation: Conversation, call: ToolCall
    ) -> tuple[ActionRecord, str, bool]:
        """Validate, guard and run one action.

        Returns the record, the text the model sees, and whether a rule asked
        for a human.
        """
        problem = self.tools.validate(call.name, call.arguments)
        if problem:
            return ActionRecord(call.name, call.arguments, "invalid", problem), problem, False

        verdict = self.guard.check_action(call.name, call.arguments)
        if not verdict.allowed:
            conversation.guard_blocks += 1
            needs_human = verdict.action == "handoff"
            content = _blocked_message(verdict.explain(), escalated=needs_human)
            record = ActionRecord(
                call.name, call.arguments, "blocked", verdict.explain(), tuple(verdict.rule_ids)
            )
            return record, content, needs_human

        outcome = self.tools.call(call.name, call.arguments)
        if not outcome.ok:
            record = ActionRecord(call.name, call.arguments, "error", outcome.content)
            return record, outcome.content, False

        spec = self.tools.spec(call.name)
        learned = facts_from_result(spec, outcome.data) if spec else {}
        if learned:
            conversation.facts.update(learned)
            if conversation.customer_id:
                self.store.save(conversation.customer_id, conversation.facts)
        return (
            ActionRecord(call.name, call.arguments, "ok", outcome.content),
            outcome.content,
            False,
        )

    # -- replies ------------------------------------------------------------

    def _reply(
        self,
        conversation: Conversation,
        response: ModelResponse,
        trace: Trace,
        result: TurnResult,
    ) -> None:
        verdict = self.guard.check_reply(response.text)
        invented = self._invented_numbers(conversation, response.text) if verdict.ok else []
        if invented:
            # A figure from nowhere is an invented fact. Say so instead of sending it.
            text = self.pack.scope.unsure_reply
            result.replaced_by = "grounding"
            conversation.messages.append({"role": "assistant", "content": text})
            trace.add(
                "reply_blocked", rule="grounding", matched=", ".join(invented), draft=response.text
            )
        elif verdict.ok:
            text = response.text
            conversation.messages.append({"role": "assistant", "content": response.content})
        else:
            # The draft was never sent, so the history records what the customer saw.
            text = verdict.replacement
            conversation.guard_blocks += 1
            result.replaced_by = verdict.rule_id
            conversation.messages.append({"role": "assistant", "content": text})
            trace.add(
                "reply_blocked", rule=verdict.rule_id, matched=verdict.matched, draft=response.text
            )

        shaped = self.shaper.shape(text)
        conversation.last_reply = shaped.text
        result.bubbles = shaped.bubbles
        result.dropped = shaped.dropped
        trace.add(
            "shaped",
            draft=text,
            bubbles=[b.text for b in shaped.bubbles],
            dropped=shaped.dropped,
            removed_phrases=shaped.removed_phrases,
        )

    def _invented_numbers(self, conversation: Conversation, draft: str) -> list[str]:
        if not self.pack.scope.ground_numbers:
            return []
        evidence = evidence_text(self._static_evidence, conversation.messages)
        return ungrounded_numbers(draft, evidence)

    def _refuse(
        self,
        conversation: Conversation,
        message: str,
        reason: str,
        matched: str,
        trace: Trace,
        result: TurnResult,
    ) -> None:
        """Turn away an off-topic message without calling the model."""
        reply = self.pack.scope.off_topic_reply
        conversation.messages.append({"role": "user", "content": message})
        conversation.messages.append({"role": "assistant", "content": reply})
        conversation.last_reply = reply
        result.refused = reason
        result.bubbles = self.shaper.shape(reply).bubbles
        trace.add("scope_refused", reason=reason, matched=matched)

    def _hand_off(
        self,
        conversation: Conversation,
        decision: HandoffDecision,
        trace: Trace,
        result: TurnResult,
        *,
        repeat: bool = False,
    ) -> None:
        conversation.handoff = decision
        conversation.last_reply = decision.message
        conversation.messages.append({"role": "assistant", "content": decision.message})
        result.handoff = decision
        result.bubbles = self.shaper.shape(decision.message).bubbles
        trace.add("handoff", reason=decision.reason, detail=decision.detail, repeat=repeat)
