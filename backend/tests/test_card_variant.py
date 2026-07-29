import pytest

from app.services.card_variant import infer_played_variant


def test_infer_base_when_missing_or_zero():
    assert infer_played_variant(None) == "base"
    assert infer_played_variant(0) == "base"


def test_infer_evo_from_evolution_level_one():
    assert infer_played_variant(1) == "evo_1"


def test_infer_hero_from_evolution_level_two():
    assert infer_played_variant(2) == "hero"


def test_knight_evo_in_wild_slot_is_still_evo():
    """Slot position does not matter; evolutionLevel drives variant."""
    assert infer_played_variant(1) == "evo_1"


def test_barbarian_barrel_hero():
    assert infer_played_variant(2) == "hero"
