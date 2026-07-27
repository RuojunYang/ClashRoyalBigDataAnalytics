"""Curated gameplay profiles: is_core per variant (independent of cards.card_type)."""

CARD_GAMEPLAY_PROFILES: list[dict] = [
    {"card_id": 26000003, "variant": "base", "is_core": True, "notes": "Giant"},
    {"card_id": 26000009, "variant": "base", "is_core": True, "notes": "Golem"},
    {"card_id": 26000038, "variant": "base", "is_core": False, "notes": "Ice Golem"},
    {"card_id": 26000021, "variant": "base", "is_core": True, "notes": "Hog Rider"},
    {"card_id": 27000009, "variant": "base", "is_core": False, "notes": "Tombstone"},
    {
        "card_id": 27000009,
        "variant": "hero",
        "is_core": True,
        "notes": "Tombstone Hero form summons a major threat",
    },
    {
        "card_id": 28000004,
        "variant": "base",
        "is_core": True,
        "notes": "Goblin Barrel — spell win condition",
    },
]
