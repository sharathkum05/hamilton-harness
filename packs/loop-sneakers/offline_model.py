"""A stand-in model for trying the Loop Sneakers pack with no API key.

This is keyword matching, not intelligence. It exists so the chat widget and
the inspector can be demonstrated offline. It is also deliberately gullible:
it refunds whatever it is asked to and agrees to discounts, so the guard has
something to stop.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from repkit.llm import ModelResponse, ToolCall, Usage

_ORDER = re.compile(r"\bLS-\d{4}\b", re.IGNORECASE)
_REMEMBERED_ORDER = re.compile(r"last_order: (LS-\d{4})")
_SIZE = re.compile(r"\b(?:size|uk|for an?)\s*(\d{1,2}(?:\.5)?)\b", re.IGNORECASE)
_AMOUNT = re.compile(r"(?:₹|rs\.?\s*|refund\s+)(\d[\d,]{2,})", re.IGNORECASE)

_REFUND = re.compile(r"refund|money back|charged twice|double charge|charged two|reimburse", re.I)
_EXCHANGE = re.compile(r"\b(swap|exchange|too small|too big|different size)\b", re.I)
_TRACK = re.compile(
    r"\b(where|track|tracking|late|arrive|arrived|delivery|status)\b|n't come", re.I
)
_DISCOUNT = re.compile(r"discount|% off|percent off|coupon|cheaper|price match|\bdeal\b", re.I)
_BOT = re.compile(r"\b(bot|robot|ai|human|real person)\b", re.I)
_YES = re.compile(r"^\s*(yes|yeah|yep|sure|ok|okay|please|pls|yes please|go ahead)\b", re.I)
_THANKS = re.compile(r"\b(thanks|thank you|thx|cheers)\b", re.I)
_HELLO = re.compile(r"^\s*(hi|hey|hello|yo|hiya)\b[\s!.]*$", re.I)


def _text_of(message: dict[str, Any]) -> str:
    content = message["content"]
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content if b.get("type") == "text")


def _is_tool_results(message: dict[str, Any]) -> bool:
    content = message["content"]
    return isinstance(content, list) and any(b.get("type") == "tool_result" for b in content)


def _rupees(amount: float) -> str:
    return f"₹{int(amount):,}"


class OfflineModel:
    name = "offline-demo"
    supports_system_turns = True

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelResponse:
        step = self._decide(messages)
        if isinstance(step, str):
            content: list[dict[str, Any]] = [{"type": "text", "text": step}]
            return ModelResponse(
                content, step, [], "end_turn", Usage(0, len(step.split())), model=self.name
            )
        call = ToolCall(f"toolu_{uuid.uuid4().hex[:12]}", step["tool"], step["args"])
        content = [{"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}]
        return ModelResponse(content, "", [call], "tool_use", Usage(), model=self.name)

    # -- reading the conversation -------------------------------------------

    def _turn(self, messages: list[dict[str, Any]]) -> tuple[str, str, dict[str, dict[str, Any]]]:
        """The customer's latest message, the one before it, and this turn's tool results."""
        customer_at = max(
            i for i, m in enumerate(messages) if m["role"] == "user" and not _is_tool_results(m)
        )
        names: dict[str, str] = {}
        results: dict[str, dict[str, Any]] = {}
        for message in messages[customer_at + 1 :]:
            content = message["content"]
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "tool_use":
                    names[block["id"]] = block["name"]
                elif block.get("type") == "tool_result":
                    results[names.get(block["tool_use_id"], "")] = block
        earlier = [_text_of(m) for m in messages[:customer_at] if m["role"] == "assistant"]
        return _text_of(messages[customer_at]), (earlier[-1] if earlier else ""), results

    def _order_id(self, text: str, messages: list[dict[str, Any]]) -> str | None:
        match = _ORDER.search(text)
        if match:
            return match.group(0).upper()
        for message in reversed(messages):
            if message["role"] == "system":
                remembered = _REMEMBERED_ORDER.search(message["content"])
                if remembered:
                    return remembered.group(1)
        # Fall back to an order number the customer gave earlier in the chat.
        for message in reversed(messages):
            if message["role"] == "user" and not _is_tool_results(message):
                earlier = _ORDER.search(_text_of(message))
                if earlier:
                    return earlier.group(0).upper()
        return None

    # -- deciding what to do ------------------------------------------------

    def _decide(self, messages: list[dict[str, Any]]) -> str | dict[str, Any]:
        text, last_reply, results = self._turn(messages)
        order_id = self._order_id(text, messages)

        if _BOT.search(text) and re.search(r"\b(are|r) (you|u)\b|is this", text, re.I):
            return (
                "I'm Maya, Loop's AI assistant. I can get a person on the line any time you want."
            )
        if _DISCOUNT.search(text):
            return "Sure, I can do 20% off for you!"
        if _REFUND.search(text):
            return self._refund(text, order_id, results)
        if _EXCHANGE.search(text) or (_SIZE.search(text) and "size" in last_reply.lower()):
            return self._exchange(text, order_id, results)
        if _YES.search(text) and "tracking link" in last_reply.lower() and order_id:
            if "send_tracking_link" in results:
                return "Sent! It's in your texts now."
            return {"tool": "send_tracking_link", "args": {"order_id": order_id}}
        if _TRACK.search(text) or (order_id and _ORDER.search(text)):
            return self._track(order_id, results)
        if _THANKS.search(text):
            return "Anytime 👍"
        if _HELLO.search(text):
            return "Hey! What can I sort out for you?"
        return self._from_notes(messages)

    def _lookup(self, order_id: str | None, results: dict[str, dict[str, Any]]) -> Any:
        """The order, or the step that gets it, or a reply explaining why not."""
        if not order_id:
            return "Sure. What's the order number?"
        if "lookup_order" not in results:
            return {"tool": "lookup_order", "args": {"order_id": order_id}}
        result = results["lookup_order"]
        if result.get("is_error"):
            return f"Hmm, {result['content']}"
        return json.loads(result["content"])

    def _track(self, order_id: str | None, results: dict[str, dict[str, Any]]) -> Any:
        order = self._lookup(order_id, results)
        if not isinstance(order, dict) or "tool" in order:
            return order
        if order["status"] == "shipped":
            return (
                f"Found it, {order['customer']}. It's on the way and due "
                f"{order['promised_delivery']}. Want me to send the tracking link?"
            )
        return f"That one was delivered, {order['customer']}. Is something wrong with it?"

    def _refund(self, text: str, order_id: str | None, results: dict[str, dict[str, Any]]) -> Any:
        order = self._lookup(order_id, results)
        if not isinstance(order, dict) or "tool" in order:
            return order
        name = order["customer"]
        if "issue_refund" in results:
            result = results["issue_refund"]
            if not result.get("is_error"):
                refunded = json.loads(result["content"])
                return (
                    f"Done, {name}. {_rupees(refunded['refunded_inr'])} is on its way back "
                    f"and lands in {refunded['arrives_in']}."
                )
            if "Blocked by company policy" in result["content"]:
                return (
                    f"I can't refund that one myself, {name}. If the shoes just aren't for you, "
                    "you can start a return from your account."
                )
            return f"Sorry {name}, that didn't go through. {result['content']}"

        lowered = text.lower()
        if re.search(r"twice|double|two times", lowered):
            reason = "duplicate_charge"
        elif re.search(r"damag|broken|torn|ripped", lowered):
            reason = "damaged"
        elif "wrong" in lowered:
            reason = "wrong_item"
        elif "late" in lowered:
            reason = "late_delivery"
        else:
            reason = "changed_mind"
        asked = _AMOUNT.search(text)
        amount = int(asked.group(1).replace(",", "")) if asked else order["price_inr"]
        return {
            "tool": "issue_refund",
            "args": {"order_id": order["order_id"], "amount_inr": amount, "reason": reason},
        }

    def _exchange(self, text: str, order_id: str | None, results: dict[str, dict[str, Any]]) -> Any:
        if not order_id:
            return "Of course. Which order is it?"
        size = _SIZE.search(text) or re.search(r"\b(\d{1,2}(?:\.5)?)\b\s*$", text)
        if not size:
            return "Got it. What size do you want instead?"
        if "create_exchange" not in results:
            return {
                "tool": "create_exchange",
                "args": {"order_id": order_id, "new_size": size.group(1)},
            }
        result = results["create_exchange"]
        if result.get("is_error"):
            return f"I can't swap that one, sorry. {result['content']}"
        done = json.loads(result["content"])
        return (
            f"Done. A {done['new_size']} ships {done['ships']} and the return label "
            "is in your email."
        )

    def _from_notes(self, messages: list[dict[str, Any]]) -> str:
        """Answer from the first reference note the harness looked up for this message."""
        customer_at = max(
            i for i, m in enumerate(messages) if m["role"] == "user" and not _is_tool_results(m)
        )
        after = messages[customer_at + 1 : customer_at + 2]
        if after and after[0]["role"] == "system" and "Reference notes\n" in after[0]["content"]:
            notes = after[0]["content"].split("Reference notes\n", 1)[1]
            # Drop the "[file > heading]" line, keep the first sentence under it.
            body = notes.split("\n", 1)[1] if "\n" in notes else notes
            sentences = re.split(r"(?<=[.!?])\s+", " ".join(body.split("\n\n")[0].split()))
            asked = set(re.findall(r"[a-z]{4,}", _text_of(messages[customer_at]).lower()))
            # The sentence that shares the most words with the question.
            best = max(
                sentences, key=lambda s: len(asked & set(re.findall(r"[a-z]{4,}", s.lower())))
            )
            return best.replace("</context>", "").strip()
        return "I'm not sure about that one. Want me to get someone who knows?"


def build() -> OfflineModel:
    return OfflineModel()
