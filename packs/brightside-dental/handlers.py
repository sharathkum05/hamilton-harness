"""A pretend appointment book for the Brightside Dental demo pack."""

from __future__ import annotations

import copy

_SEED_SLOTS = {
    "S-101": {"when": "tomorrow at 10:00 am", "free": True},
    "S-102": {"when": "tomorrow at 4:30 pm", "free": True},
    "S-103": {"when": "Friday at 11:15 am", "free": True},
}

SLOTS = copy.deepcopy(_SEED_SLOTS)
BOOKINGS: dict[str, dict] = {}


def reset() -> None:
    SLOTS.clear()
    SLOTS.update(copy.deepcopy(_SEED_SLOTS))
    BOOKINGS.clear()


def find_slots(treatment: str) -> dict:
    free = [{"slot_id": key, "when": slot["when"]} for key, slot in SLOTS.items() if slot["free"]]
    if not free:
        raise LookupError("There are no free appointments this week.")
    return {"treatment": treatment, "slots": free[:2]}


def book_appointment(patient_name: str, phone: str, treatment: str, slot_id: str) -> dict:
    slot = SLOTS.get(slot_id)
    if slot is None:
        raise LookupError(f"There is no slot {slot_id}. Use find_slots to see what is free.")
    if not slot["free"]:
        raise ValueError("That slot has just been taken. Offer another one.")
    slot["free"] = False
    booking_id = f"BD-{len(BOOKINGS) + 1:03d}"
    BOOKINGS[booking_id] = {"patient": patient_name, "phone": phone, "slot_id": slot_id}
    return {
        "booking_id": booking_id,
        "patient_name": patient_name,
        "treatment": treatment,
        "when": slot["when"],
    }


def cancel_appointment(booking_id: str) -> dict:
    booking = BOOKINGS.pop(booking_id.strip().upper(), None)
    if booking is None:
        raise LookupError(f"There is no booking {booking_id}.")
    SLOTS[booking["slot_id"]]["free"] = True
    return {"cancelled": booking_id}
