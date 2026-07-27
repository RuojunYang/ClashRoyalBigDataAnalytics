from urllib.parse import quote


def encode_player_tag(tag: str) -> str:
    if tag.startswith("#"):
        return quote(tag, safe="")
    return quote(f"#{tag}", safe="")


def map_leaderboard_entry(api_entry: dict) -> dict:
    clan = api_entry.get("clan") or {}
    return {
        "player_tag": api_entry["tag"],
        "rank": api_entry["rank"],
        "elo_rating": api_entry["eloRating"],
        "name": api_entry.get("name"),
        "exp_level": api_entry.get("expLevel"),
        "clan_tag": clan.get("tag"),
        "clan_name": clan.get("name"),
    }
