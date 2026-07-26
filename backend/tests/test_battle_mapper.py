from datetime import UTC, datetime

import pytest

from app.services.battle_mapper import (
    build_battle_key,
    map_battle_entry,
    parse_battle_time,
    should_include_battle,
)
from app.services.leaderboard_mapper import encode_player_tag, map_leaderboard_entry


def test_encode_player_tag():
    assert encode_player_tag("#G0CYJ00J") == "%23G0CYJ00J"


def test_map_leaderboard_entry():
    api_entry = {
        "tag": "#G0CYJ00J",
        "name": "Nicoco23",
        "expLevel": 87,
        "eloRating": 3160,
        "rank": 1,
        "clan": {"tag": "#JYLVYG8C", "name": "CLASH COACHING"},
    }
    mapped = map_leaderboard_entry(api_entry)
    assert mapped["player_tag"] == "#G0CYJ00J"
    assert mapped["rank"] == 1
    assert mapped["elo_rating"] == 3160
    assert mapped["clan_tag"] == "#JYLVYG8C"


def test_parse_battle_time():
    dt = parse_battle_time("20250726T120000.000Z")
    assert dt.year == 2025
    assert dt.month == 7
    assert dt.day == 26


def test_should_include_battle_path_of_legend():
    assert should_include_battle({"type": "pathOfLegend"}, ranked_only=True) is True
    assert should_include_battle({"type": "PvP", "gameMode": {"name": "Ladder"}}, ranked_only=True) is False


def test_map_battle_entry():
    entry = {
        "type": "pathOfLegend",
        "battleTime": "20250726T120000.000Z",
        "gameMode": {"id": 72000450, "name": "Ranked1v1_NewArena"},
        "arena": {"id": 54000016, "name": "Legend Arena"},
        "leagueNumber": 10,
        "team": [
            {
                "tag": "#G0CYJ00J",
                "startingTrophies": 3160,
                "trophyChange": 25,
                "crowns": 3,
                "cards": [{"id": 26000000, "level": 14}, {"id": 26000001, "level": 14}],
            }
        ],
        "opponent": [
            {
                "tag": "#OPPONENT1",
                "startingTrophies": 3150,
                "trophyChange": -25,
                "crowns": 1,
                "cards": [{"id": 26000002, "level": 14}],
            }
        ],
    }
    mapped = map_battle_entry(entry)
    assert mapped is not None
    assert mapped["battle_type"] == "pathOfLegend"
    assert len(mapped["participants"]) == 2
    assert mapped["participants"][0]["won"] is True
    assert build_battle_key(mapped["battle_time"], "#G0CYJ00J", "#OPPONENT1") == mapped["battle_key"]
