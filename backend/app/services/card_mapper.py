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


def map_api_card(api_card: dict) -> dict:
    icon_urls = api_card.get("iconUrls") or {}
    max_evolution_level = api_card.get("maxEvolutionLevel", 0) or 0
    return {
        "id": api_card["id"],
        "name": api_card["name"],
        "elixir_cost": api_card.get("elixirCost"),
        "max_evolution_level": max_evolution_level,
        "has_evolution": "evolutionMedium" in icon_urls,
        "has_hero": "heroMedium" in icon_urls,
        "card_type": infer_card_type(api_card["id"]),
    }
