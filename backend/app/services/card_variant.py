from app.db.models import Card


def parse_deck_slot_set(raw: str) -> frozenset[int]:
    return frozenset(int(part.strip()) for part in raw.split(",") if part.strip())


def infer_played_variant(
    slot: int,
    card: Card | None,
    *,
    evo_slots: frozenset[int],
    hero_slot: int,
    evolution_level_from_api: int | None = None,
) -> str:
    if card is None:
        return "base"

    if slot == hero_slot and card.has_hero:
        return "hero"

    if slot in evo_slots and card.has_evolution:
        level = evolution_level_from_api
        if level is None or level < 1:
            level = 1
        if card.max_evolution_level and level > card.max_evolution_level:
            level = card.max_evolution_level
        return f"evo_{level}"

    return "base"
