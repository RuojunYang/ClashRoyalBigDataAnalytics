import pytest

from app.services.card_mapper import infer_card_type, map_api_card


def test_infer_card_type():
    assert infer_card_type(26000000) == "troop"
    assert infer_card_type(27000000) == "building"
    assert infer_card_type(28000004) == "spell"


def test_map_api_card_ignores_rarity_and_max_level():
    api_card = {
        "name": "Goblin Barrel",
        "id": 28000004,
        "maxLevel": 11,
        "maxEvolutionLevel": 1,
        "elixirCost": 3,
        "rarity": "epic",
        "iconUrls": {
            "medium": "https://example.com/medium.png",
            "evolutionMedium": "https://example.com/evolution.png",
        },
    }

    mapped = map_api_card(api_card)

    assert mapped["id"] == 28000004
    assert mapped["name"] == "Goblin Barrel"
    assert mapped["elixir_cost"] == 3
    assert mapped["max_evolution_level"] == 1
    assert mapped["has_evolution"] is True
    assert mapped["has_hero"] is False
    assert mapped["card_type"] == "spell"
    assert "rarity" not in mapped
    assert "max_level" not in mapped


def test_map_api_card_detects_hero():
    api_card = {
        "name": "Knight",
        "id": 26000000,
        "iconUrls": {
            "medium": "https://example.com/medium.png",
            "heroMedium": "https://example.com/hero.png",
        },
    }

    mapped = map_api_card(api_card)
    assert mapped["has_hero"] is True


def test_map_api_card_has_evolution_only_from_evolution_medium():
    api_card = {
        "name": "Ice Golem",
        "id": 26000038,
        "maxEvolutionLevel": 2,
        "elixirCost": 2,
        "iconUrls": {
            "medium": "https://example.com/medium.png",
            "heroMedium": "https://example.com/hero.png",
        },
    }

    mapped = map_api_card(api_card)

    assert mapped["has_evolution"] is False
    assert mapped["has_hero"] is True
    assert mapped["max_evolution_level"] == 2


def test_map_api_card_max_evolution_level_without_icon_is_not_evo():
    api_card = {
        "name": "Some Card",
        "id": 26000099,
        "maxEvolutionLevel": 1,
        "iconUrls": {"medium": "https://example.com/medium.png"},
    }

    mapped = map_api_card(api_card)

    assert mapped["has_evolution"] is False
