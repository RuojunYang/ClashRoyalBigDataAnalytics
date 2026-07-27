"""Curated threat roles and gameplay profiles (independent of cards.card_type)."""

CARD_THREAT_ROLES: list[dict] = [
    {
        "code": "tower_tank",
        "label": "Tower Tank",
        "description": "Heavy troop that primarily targets towers and anchors a push.",
    },
    {
        "code": "building_target",
        "label": "Building Target",
        "description": "Win condition that targets buildings directly (e.g. Hog, Balloon).",
    },
    {
        "code": "support_tank",
        "label": "Support Tank",
        "description": "Troop that soaks damage or distracts but is not the main win condition.",
    },
    {
        "code": "spawner",
        "label": "Spawner",
        "description": "Building or effect that produces units over time.",
    },
    {
        "code": "summoned_threat",
        "label": "Summoned Threat",
        "description": "Primary threat created by another card (hero skill, spawn, etc.).",
    },
    {
        "code": "spell_win_condition",
        "label": "Spell Win Condition",
        "description": "Spell that can serve as the deck's primary damage plan (e.g. Goblin Barrel).",
    },
    {
        "code": "spell_support",
        "label": "Spell Support",
        "description": "Spell that supports a push but is not the deck core on its own.",
    },
]

# Supercell card ids; profiles are independent of card_type (spell/troop/building).
CARD_GAMEPLAY_PROFILES: list[dict] = [
    {"card_id": 26000003, "variant": "base", "role_code": "tower_tank", "is_core": True, "notes": "Giant"},
    {"card_id": 26000009, "variant": "base", "role_code": "tower_tank", "is_core": True, "notes": "Golem"},
    {"card_id": 26000038, "variant": "base", "role_code": "support_tank", "is_core": False, "notes": "Ice Golem"},
    {"card_id": 26000021, "variant": "base", "role_code": "building_target", "is_core": True, "notes": "Hog Rider"},
    {"card_id": 27000009, "variant": "base", "role_code": "spawner", "is_core": False, "notes": "Tombstone"},
    {
        "card_id": 27000009,
        "variant": "hero",
        "role_code": "summoned_threat",
        "is_core": True,
        "notes": "Tombstone Hero form summons a major threat",
    },
    {
        "card_id": 28000004,
        "variant": "base",
        "role_code": "spell_win_condition",
        "is_core": True,
        "notes": "Goblin Barrel — spell win condition",
    },
]
