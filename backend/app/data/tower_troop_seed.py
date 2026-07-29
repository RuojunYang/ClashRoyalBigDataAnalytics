"""Manually curated Tower Troop catalog (not available from /cards API)."""

TOWER_TROOPS: list[dict] = [
    {"id": 159000000, "name": "Tower Princess"},
    {"id": 159000001, "name": "Cannoneer"},
    {"id": 159000002, "name": "Dagger Duchess"},
    {"id": 159000004, "name": "Royal Chef"},
]

KNOWN_TOWER_TROOP_IDS: frozenset[int] = frozenset(row["id"] for row in TOWER_TROOPS)
