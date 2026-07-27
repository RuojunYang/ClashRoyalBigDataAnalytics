import pytest

from app.db.models import Card
from app.services.card_variant import infer_played_variant, parse_deck_slot_set


def _card(*, has_evolution: bool = False, has_hero: bool = False, max_evolution_level: int = 0) -> Card:
    return Card(
        id=1,
        name="Test",
        max_evolution_level=max_evolution_level,
        has_evolution=has_evolution,
        has_hero=has_hero,
        card_type="troop",
    )


def test_parse_deck_slot_set():
    assert parse_deck_slot_set("0,2") == frozenset({0, 2})


def test_infer_hero_slot():
    card = _card(has_hero=True)
    assert infer_played_variant(1, card, evo_slots=frozenset({0, 2}), hero_slot=1) == "hero"


def test_infer_evo_slot():
    card = _card(has_evolution=True, max_evolution_level=1)
    assert infer_played_variant(0, card, evo_slots=frozenset({0, 2}), hero_slot=1) == "evo_1"
    assert infer_played_variant(2, card, evo_slots=frozenset({0, 2}), hero_slot=1) == "evo_1"


def test_evo_slot_without_evolution_capability_is_base():
    card = _card(has_evolution=False)
    assert infer_played_variant(0, card, evo_slots=frozenset({0, 2}), hero_slot=1) == "base"


def test_hero_slot_without_hero_capability_is_base():
    card = _card(has_hero=False)
    assert infer_played_variant(1, card, evo_slots=frozenset({0, 2}), hero_slot=1) == "base"


def test_normal_slot_is_base():
    card = _card(has_evolution=True, has_hero=True, max_evolution_level=1)
    assert infer_played_variant(5, card, evo_slots=frozenset({0, 2}), hero_slot=1) == "base"


def test_api_evolution_level_overrides_default():
    card = _card(has_evolution=True, max_evolution_level=2)
    assert (
        infer_played_variant(
            0,
            card,
            evo_slots=frozenset({0, 2}),
            hero_slot=1,
            evolution_level_from_api=2,
        )
        == "evo_2"
    )
