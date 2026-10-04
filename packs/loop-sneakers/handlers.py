"""A pretend order system for the Loop Sneakers demo pack.

Real packs point these functions at the company's own APIs. State lives in
memory, so every run starts from the same orders.
"""

from __future__ import annotations

import copy

_SEED = {
    "LS-4471": {
        "customer": "Priya",
        "item": "Drift Runner, black, UK 7",
        "price_inr": 2499,
        "charges_inr": [2499, 2499],
        "status": "shipped",
        "promised_delivery": "Thursday 8 October",
        "days_since_delivery": None,
        "refunded_inr": 0,
    },
    "LS-5120": {
        "customer": "Arjun",
        "item": "Drift Runner, sand, UK 8",
        "price_inr": 2499,
        "charges_inr": [2499],
        "status": "delivered",
        "promised_delivery": "Monday 28 September",
        "days_since_delivery": 5,
        "refunded_inr": 0,
    },
    "LS-6033": {
        "customer": "Meera",
        "item": "Trail Loop, slate, UK 6",
        "price_inr": 4199,
        "charges_inr": [4199],
        "status": "delivered",
        "promised_delivery": "Friday 14 August",
        "days_since_delivery": 48,
        "refunded_inr": 0,
    },
}

ORDERS = copy.deepcopy(_SEED)


def reset() -> None:
    ORDERS.clear()
    ORDERS.update(copy.deepcopy(_SEED))


def _order(order_id: str) -> dict:
    order = ORDERS.get(order_id.strip().upper())
    if order is None:
        raise LookupError(f"No order {order_id}. Ask the customer to check the number.")
    return order


def lookup_order(order_id: str) -> dict:
    return {"order_id": order_id.strip().upper(), **_order(order_id)}


def issue_refund(order_id: str, amount_inr: float, reason: str) -> dict:
    order = _order(order_id)
    paid = sum(order["charges_inr"]) - order["refunded_inr"]
    if amount_inr <= 0:
        raise ValueError("Refund amount must be more than zero.")
    if amount_inr > paid:
        raise ValueError(f"Only ₹{paid} has been paid on this order.")
    order["refunded_inr"] += amount_inr
    return {"refunded_inr": amount_inr, "reason": reason, "arrives_in": "3 to 5 working days"}


def create_exchange(order_id: str, new_size: str) -> dict:
    order = _order(order_id)
    days = order["days_since_delivery"]
    if days is None:
        raise ValueError("The order has not been delivered yet, so it cannot be exchanged.")
    if days > 30:
        raise ValueError(f"Delivered {days} days ago, which is past the 30 day exchange window.")
    return {"new_size": f"UK {new_size}", "ships": "tomorrow", "return_label": "emailed"}


def send_tracking_link(order_id: str) -> dict:
    _order(order_id)
    return {"sent": True, "channel": "text message"}
