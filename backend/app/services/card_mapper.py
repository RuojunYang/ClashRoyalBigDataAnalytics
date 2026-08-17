from app.db.models import CardType


def infer_card_type(card_id: int) -> str:
    prefix = card_id // 1_000_000
    if prefix == 26:
        return CardType.TROOP.value
    if prefix == 27:
        return CardType.BUILDING.value
    if prefix == 28:
        return CardType.SPELL.value
    raise ValueError(f"Unknown card id prefix for card {card_id}")


def infer_card_capabilities(max_evolution_level: int) -> tuple[bool, bool]:
    """Map API maxEvolutionLevel bitmask: 1=evo, 2=hero, 3=both."""
    return bool(max_evolution_level & 1), bool(max_evolution_level & 2)


def map_api_card(api_card: dict) -> dict:
    max_evolution_level = api_card.get("maxEvolutionLevel", 0) or 0
    has_evolution, has_hero = infer_card_capabilities(max_evolution_level)
    return {
        "id": api_card["id"],
        "name": api_card["name"],
        "elixir_cost": api_card.get("elixirCost"),
        "max_evolution_level": max_evolution_level,
        "has_evolution": has_evolution,
        "has_hero": has_hero,
        "card_type": infer_card_type(api_card["id"]),
    }
