from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Card, LeaderboardEntry, LeaderboardSnapshot, Player, BattleDeckCard
from app.services.battlelog_sync import BattlelogSyncService
from app.services.leaderboard_sync import LeaderboardSyncService


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            Card(
                id=26000000,
                name="Knight",
                elixir_cost=3,
                max_evolution_level=1,
                has_evolution=True,
                has_hero=False,
                card_type="troop",
            )
        )
        session.add(
            Card(
                id=26000001,
                name="Archers",
                elixir_cost=3,
                max_evolution_level=0,
                has_evolution=False,
                has_hero=True,
                card_type="troop",
            )
        )
        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_leaderboard_sync_upserts_players(db_session: AsyncSession):
    api_entries = [
        {
            "tag": "#G0CYJ00J",
            "name": "Nicoco23",
            "expLevel": 87,
            "eloRating": 3160,
            "rank": 1,
            "clan": {"tag": "#JYLVYG8C", "name": "CLASH COACHING"},
        },
        {
            "tag": "#2YQJJG0VL",
            "name": "GençAslan:)",
            "expLevel": 86,
            "eloRating": 3154,
            "rank": 2,
        },
    ]
    client = AsyncMock()
    client.get_global_pol_players_top_n = AsyncMock(return_value=api_entries)
    service = LeaderboardSyncService(client=client)

    result = await service.sync_leaderboard(db_session, top_n=2, page_limit=100)
    assert result.entries_synced == 2
    assert result.players_tracked == 2

    player = await db_session.get(Player, "#G0CYJ00J")
    assert player is not None
    assert player.latest_rank == 1
    assert player.is_tracked is True

    entries = await db_session.execute(select(LeaderboardEntry))
    assert len(list(entries.scalars().all())) == 2


@pytest.mark.asyncio
async def test_leaderboard_sync_untracks_dropped_players(db_session: AsyncSession):
    db_session.add(
        Player(
            tag="#OLDPLAYER",
            name="Old",
            latest_rank=999,
            is_tracked=True,
            leaderboard_seeded=True,
        )
    )
    await db_session.commit()

    client = AsyncMock()
    client.get_global_pol_players_top_n = AsyncMock(
        return_value=[
            {
                "tag": "#G0CYJ00J",
                "name": "Nicoco23",
                "expLevel": 87,
                "eloRating": 3160,
                "rank": 1,
            }
        ]
    )
    service = LeaderboardSyncService(client=client)
    await service.sync_leaderboard(db_session, top_n=1, page_limit=100, untrack_after_misses=1)

    old_player = await db_session.get(Player, "#OLDPLAYER")
    assert old_player is not None
    assert old_player.is_tracked is False
    assert old_player.off_leaderboard_count == 1


@pytest.mark.asyncio
async def test_leaderboard_sync_grace_period_before_untrack(db_session: AsyncSession):
    db_session.add(
        Player(
            tag="#OLDPLAYER",
            name="Old",
            latest_rank=999,
            is_tracked=True,
            leaderboard_seeded=True,
        )
    )
    await db_session.commit()

    client = AsyncMock()
    client.get_global_pol_players_top_n = AsyncMock(
        return_value=[
            {
                "tag": "#G0CYJ00J",
                "name": "Nicoco23",
                "expLevel": 87,
                "eloRating": 3160,
                "rank": 1,
            }
        ]
    )
    service = LeaderboardSyncService(client=client)

    await service.sync_leaderboard(db_session, top_n=1, page_limit=100, untrack_after_misses=3)
    old_player = await db_session.get(Player, "#OLDPLAYER")
    assert old_player is not None
    assert old_player.is_tracked is True
    assert old_player.off_leaderboard_count == 1

    await service.sync_leaderboard(db_session, top_n=1, page_limit=100, untrack_after_misses=3)
    await db_session.refresh(old_player)
    assert old_player.is_tracked is True
    assert old_player.off_leaderboard_count == 2

    await service.sync_leaderboard(db_session, top_n=1, page_limit=100, untrack_after_misses=3)
    await db_session.refresh(old_player)
    assert old_player.is_tracked is False
    assert old_player.off_leaderboard_count == 3


@pytest.mark.asyncio
async def test_leaderboard_sync_resets_off_leaderboard_count_when_back(db_session: AsyncSession):
    db_session.add(
        Player(
            tag="#G0CYJ00J",
            name="Nicoco23",
            latest_rank=2,
            is_tracked=True,
            off_leaderboard_count=2,
        )
    )
    await db_session.commit()

    client = AsyncMock()
    client.get_global_pol_players_top_n = AsyncMock(
        return_value=[
            {
                "tag": "#G0CYJ00J",
                "name": "Nicoco23",
                "expLevel": 87,
                "eloRating": 3160,
                "rank": 1,
            }
        ]
    )
    service = LeaderboardSyncService(client=client)
    await service.sync_leaderboard(db_session, top_n=1, page_limit=100, untrack_after_misses=3)

    player = await db_session.get(Player, "#G0CYJ00J")
    assert player is not None
    assert player.is_tracked is True
    assert player.off_leaderboard_count == 0


@pytest.mark.asyncio
async def test_battlelog_sync_creates_battle(db_session: AsyncSession):
    db_session.add(
        Player(
            tag="#G0CYJ00J",
            name="Nicoco23",
            latest_rank=1,
            is_tracked=True,
            leaderboard_seeded=True,
        )
    )
    await db_session.commit()

    battlelog = [
        {
            "type": "pathOfLegend",
            "battleTime": "20250726T120000.000Z",
            "gameMode": {"id": 72000450, "name": "Ranked1v1_NewArena"},
            "arena": {"id": 54000016, "name": "Legend Arena"},
            "team": [
                {
                    "tag": "#G0CYJ00J",
                    "startingTrophies": 3160,
                    "trophyChange": 25,
                    "crowns": 3,
                    "cards": [
                        {"id": 26000000, "level": 14},
                        {"id": 26000001, "level": 14},
                    ],
                }
            ],
            "opponent": [
                {
                    "tag": "#OPPONENT1",
                    "startingTrophies": 3150,
                    "trophyChange": -25,
                    "crowns": 1,
                    "cards": [{"id": 26000000, "level": 14}],
                }
            ],
        }
    ]
    client = AsyncMock()
    client.get_player_battlelog = AsyncMock(return_value=battlelog)
    service = BattlelogSyncService(client=client)

    result = await service.sync_battlelog(db_session, opponent_expansion_rounds=0)
    assert result.battles_created == 1
    assert result.deck_cards_created == 3

    result_again = await service.sync_battlelog(db_session, opponent_expansion_rounds=0)
    assert result_again.battles_skipped == 1
    assert result_again.battles_created == 0


@pytest.mark.asyncio
async def test_battlelog_sync_sets_played_variant_from_evolution_level(db_session: AsyncSession):
    knight = await db_session.get(Card, 26000000)
    assert knight is not None
    knight.max_evolution_level = 3
    knight.has_evolution = True
    knight.has_hero = True

    for card in (
        Card(id=26000015, name="Baby Dragon", elixir_cost=4, max_evolution_level=1, has_evolution=True, has_hero=False, card_type="troop"),
        Card(id=28000015, name="Barbarian Barrel", elixir_cost=2, max_evolution_level=2, has_evolution=False, has_hero=True, card_type="spell"),
        Card(id=28000000, name="Zap", elixir_cost=2, max_evolution_level=0, has_evolution=False, has_hero=False, card_type="spell"),
        Card(id=28000010, name="Arrows", elixir_cost=3, max_evolution_level=0, has_evolution=False, has_hero=False, card_type="spell"),
        Card(id=28000009, name="Giant Snowball", elixir_cost=2, max_evolution_level=0, has_evolution=False, has_hero=False, card_type="spell"),
        Card(id=26000023, name="Golem", elixir_cost=8, max_evolution_level=0, has_evolution=False, has_hero=False, card_type="troop"),
        Card(id=28000012, name="Rocket", elixir_cost=6, max_evolution_level=0, has_evolution=False, has_hero=False, card_type="spell"),
        Card(id=27000009, name="Tombstone", elixir_cost=3, max_evolution_level=0, has_evolution=False, has_hero=False, card_type="building"),
    ):
        db_session.add(card)
    db_session.add(
        Player(
            tag="#V9U9LQJ02",
            name="Fireking",
            latest_rank=1,
            is_tracked=True,
            leaderboard_seeded=True,
        )
    )
    await db_session.commit()

    team_cards = [
        {"id": 26000015, "level": 6, "evolutionLevel": 1},
        {"id": 28000015, "level": 6, "evolutionLevel": 2},
        {"id": 26000000, "level": 11, "evolutionLevel": 1},
        {"id": 28000010, "level": 11},
        {"id": 28000009, "level": 11},
        {"id": 26000023, "level": 6},
        {"id": 28000012, "level": 11},
        {"id": 27000009, "level": 11},
    ]
    battlelog = [
        {
            "type": "pathOfLegend",
            "battleTime": "20250726T120000.000Z",
            "gameMode": {"id": 72000450, "name": "Ranked1v1_NewArena"},
            "arena": {"id": 54000016, "name": "Legend Arena"},
            "team": [
                {
                    "tag": "#V9U9LQJ02",
                    "startingTrophies": 3160,
                    "trophyChange": 25,
                    "crowns": 3,
                    "cards": team_cards,
                }
            ],
            "opponent": [
                {
                    "tag": "#OPPONENT1",
                    "startingTrophies": 3150,
                    "trophyChange": -25,
                    "crowns": 1,
                    "cards": [{"id": 26000001, "level": 14}],
                }
            ],
        }
    ]
    client = AsyncMock()
    client.get_player_battlelog = AsyncMock(return_value=battlelog)
    service = BattlelogSyncService(client=client)
    await service.sync_battlelog(db_session, opponent_expansion_rounds=0)

    result = await db_session.execute(
        select(BattleDeckCard).where(BattleDeckCard.player_tag == "#V9U9LQJ02")
    )
    deck_cards = {(row.slot, row.played_variant) for row in result.scalars()}
    assert (0, "evo_1") in deck_cards
    assert (1, "hero") in deck_cards
    assert (2, "evo_1") in deck_cards
    assert (3, "base") in deck_cards


def _make_battle(team_tag: str, opponent_tag: str, battle_time: str = "20250726T120000.000Z") -> dict:
    return {
        "type": "pathOfLegend",
        "battleTime": battle_time,
        "gameMode": {"id": 72000450, "name": "Ranked1v1_NewArena"},
        "arena": {"id": 54000016, "name": "Legend Arena"},
        "team": [
            {
                "tag": team_tag,
                "name": team_tag,
                "startingTrophies": 3000,
                "trophyChange": 25,
                "crowns": 3,
                "cards": [{"id": 26000000, "level": 14}],
            }
        ],
        "opponent": [
            {
                "tag": opponent_tag,
                "name": opponent_tag,
                "startingTrophies": 2950,
                "trophyChange": -25,
                "crowns": 1,
                "cards": [{"id": 26000001, "level": 14}],
            }
        ],
    }


@pytest.mark.asyncio
async def test_battlelog_respects_battles_per_player(db_session: AsyncSession):
    db_session.add(
        Player(
            tag="#SEED",
            name="Seed",
            latest_rank=1,
            is_tracked=True,
            leaderboard_seeded=True,
        )
    )
    await db_session.commit()

    battlelog = [
        _make_battle("#SEED", "#OPP1", "20250726T120000.000Z"),
        _make_battle("#SEED", "#OPP2", "20250726T130000.000Z"),
        _make_battle("#SEED", "#OPP3", "20250726T140000.000Z"),
    ]
    client = AsyncMock()
    client.get_player_battlelog = AsyncMock(return_value=battlelog)
    service = BattlelogSyncService(client=client)

    result = await service.sync_battlelog(
        db_session,
        battles_per_player=1,
        opponent_expansion_rounds=0,
    )
    assert result.battles_created == 1
    assert result.players_processed == 1


@pytest.mark.asyncio
async def test_battlelog_opponent_expansion_rounds(db_session: AsyncSession):
    db_session.add(
        Player(
            tag="#SEED",
            name="Seed",
            latest_rank=1,
            is_tracked=True,
            leaderboard_seeded=True,
        )
    )
    await db_session.commit()

    async def get_battlelog(tag: str) -> list[dict]:
        if tag == "#SEED":
            return [_make_battle("#SEED", "#OPP1")]
        if tag == "#OPP1":
            return [_make_battle("#OPP1", "#OPP2")]
        if tag == "#OPP2":
            return [_make_battle("#OPP2", "#OPP3")]
        return []

    client = AsyncMock()
    client.get_player_battlelog = AsyncMock(side_effect=get_battlelog)
    service = BattlelogSyncService(client=client)

    result = await service.sync_battlelog(
        db_session,
        opponent_expansion_rounds=2,
        battles_per_player=25,
    )
    assert result.players_processed == 3
    assert result.battles_created == 3
    assert result.opponents_discovered == 3

    opp2 = await db_session.get(Player, "#OPP2")
    assert opp2 is not None
    assert opp2.leaderboard_seeded is False
    assert opp2.is_tracked is False


@pytest.mark.asyncio
async def test_leaderboard_untrack_skips_expansion_players(db_session: AsyncSession):
    db_session.add(
        Player(
            tag="#EXPANSION",
            name="FromExpansion",
            is_tracked=False,
            leaderboard_seeded=False,
        )
    )
    db_session.add(
        Player(
            tag="#OLDPLAYER",
            name="Old",
            latest_rank=999,
            is_tracked=True,
            leaderboard_seeded=True,
        )
    )
    await db_session.commit()

    client = AsyncMock()
    client.get_global_pol_players_top_n = AsyncMock(
        return_value=[
            {
                "tag": "#G0CYJ00J",
                "name": "Nicoco23",
                "expLevel": 87,
                "eloRating": 3160,
                "rank": 1,
            }
        ]
    )
    service = LeaderboardSyncService(client=client)
    await service.sync_leaderboard(db_session, top_n=1, page_limit=100, untrack_after_misses=1)

    expansion = await db_session.get(Player, "#EXPANSION")
    assert expansion is not None
    assert expansion.off_leaderboard_count == 0
    assert expansion.is_tracked is False
