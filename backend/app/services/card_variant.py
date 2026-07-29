def infer_played_variant(evolution_level_from_api: int | None) -> str:
    """Map battlelog deck card evolutionLevel: 1=evo, 2=hero, else base."""
    if evolution_level_from_api == 2:
        return "hero"
    if evolution_level_from_api == 1:
        return "evo_1"
    return "base"
