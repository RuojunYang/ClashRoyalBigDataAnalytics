from datetime import datetime


def parse_battle_time(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw)


def build_battle_key(battle_time: datetime, tag_a: str, tag_b: str) -> str:
    sorted_tags = sorted([tag_a, tag_b])
    return f"{battle_time.isoformat()}_{sorted_tags[0]}_{sorted_tags[1]}"


def should_include_battle(entry: dict, ranked_only: bool) -> bool:
    if not ranked_only:
        return True
    battle_type = entry.get("type")
    if battle_type == "pathOfLegend":
        return True
    game_mode = entry.get("gameMode") or {}
    name = game_mode.get("name") or ""
    return "Ranked1v1" in name


def map_battle_entry(entry: dict) -> dict | None:
    team = (entry.get("team") or [None])[0]
    opponent = (entry.get("opponent") or [None])[0]
    if team is None or opponent is None:
        return None

    team_tag = team.get("tag")
    opponent_tag = opponent.get("tag")
    if not team_tag or not opponent_tag:
        return None

    battle_time = parse_battle_time(entry["battleTime"])
    game_mode = entry.get("gameMode") or {}
    arena = entry.get("arena") or {}
    team_crowns = team.get("crowns") or 0
    opponent_crowns = opponent.get("crowns") or 0

    return {
        "battle_key": build_battle_key(battle_time, team_tag, opponent_tag),
        "battle_time": battle_time,
        "battle_type": entry.get("type"),
        "game_mode_id": game_mode.get("id"),
        "game_mode_name": game_mode.get("name"),
        "arena_id": arena.get("id"),
        "arena_name": arena.get("name"),
        "league_number": entry.get("leagueNumber"),
        "participants": [
            {
                "player_tag": team_tag,
                "side": "team",
                "starting_trophies": team.get("startingTrophies"),
                "trophy_change": team.get("trophyChange"),
                "crowns": team_crowns,
                "won": team_crowns > opponent_crowns,
                "cards": team.get("cards") or [],
            },
            {
                "player_tag": opponent_tag,
                "side": "opponent",
                "starting_trophies": opponent.get("startingTrophies"),
                "trophy_change": opponent.get("trophyChange"),
                "crowns": opponent_crowns,
                "won": opponent_crowns > team_crowns,
                "cards": opponent.get("cards") or [],
            },
        ],
    }


def get_opponent_tags(mapped: dict, player_tag: str) -> list[str]:
    return [p["player_tag"] for p in mapped["participants"] if p["player_tag"] != player_tag]


def extract_participant_profiles(entry: dict) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for side in ("team", "opponent"):
        participant = (entry.get(side) or [None])[0]
        if participant is None:
            continue
        tag = participant.get("tag")
        if not tag:
            continue
        profiles[tag] = {
            "name": participant.get("name"),
            "latest_elo_rating": participant.get("startingTrophies"),
        }
    return profiles
