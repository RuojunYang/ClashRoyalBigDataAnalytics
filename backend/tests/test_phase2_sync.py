from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Card, LeaderboardEntry, LeaderboardSnapshot, Player
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
                max_evolution_level=0,
                has_evolution=False,
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
                has_hero=False,
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

    result = await service.sync_battlelog(db_session)
    assert result.battles_created == 1
    assert result.deck_cards_created == 3

    result_again = await service.sync_battlelog(db_session)
    assert result_again.battles_skipped == 1
    assert result_again.battles_created == 0
