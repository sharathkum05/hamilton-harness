"""A pretend property list for the Kestrel Lettings demo pack."""

from __future__ import annotations

HOMES = [
    {
        "home": "Marlowe Court 4",
        "bedrooms": 2,
        "rent_inr": 32000,
        "max_occupants": 3,
        "available_from": "1 November",
    },
    {
        "home": "Orchard Row 12",
        "bedrooms": 3,
        "rent_inr": 48000,
        "max_occupants": 4,
        "available_from": "15 November",
    },
    {
        "home": "Canal Wharf 7",
        "bedrooms": 0,
        "rent_inr": 19500,
        "max_occupants": 1,
        "available_from": "now",
    },
]


def find_homes(min_bedrooms: int = 0, max_rent_inr: float | None = None) -> dict:
    matches = [
        home
        for home in HOMES
        if home["bedrooms"] >= min_bedrooms
        and (max_rent_inr is None or home["rent_inr"] <= max_rent_inr)
    ]
    if not matches:
        raise LookupError("No home matches that. Offer to pass the request to the lettings team.")
    return {"homes": matches}
