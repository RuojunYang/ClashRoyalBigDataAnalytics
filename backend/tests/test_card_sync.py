from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Card, CardChangelog, CardGameplayProfile
from app.services.card_sync import CardSyncService


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_sync_cards_creates_and_updates(db_session: AsyncSession):
    initial_cards = [
        {
            "name": "Knight",
            "id": 26000000,
            "elixirCost": 3,
            "maxEvolutionLevel": 0,
            "iconUrls": {"medium": "https://example.com/knight.png"},
        }
    ]
    updated_cards = [
        {
            "name": "Knight",
            "id": 26000000,
            "elixirCost": 3,
            "maxEvolutionLevel": 1,
            "iconUrls": {
                "medium": "https://example.com/knight.png",
                "evolutionMedium": "https://example.com/knight-evo.png",
            },
        },
        {
            "name": "Archers",
            "id": 26000001,
            "elixirCost": 3,
            "iconUrls": {"medium": "https://example.com/archers.png"},
        },
    ]

    client = AsyncMock()
    client.get_cards = AsyncMock(side_effect=[initial_cards, updated_cards])
    service = CardSyncService(client=client)

    create_result = await service.sync_cards(db_session)
    assert create_result.cards_created == 1
    assert create_result.cards_updated == 0
    assert create_result.total_active_cards == 1

    update_result = await service.sync_cards(db_session)
    assert update_result.cards_created == 1
    assert update_result.cards_updated == 1
    assert update_result.changes_logged >= 2
    assert update_result.total_active_cards == 2

    changelog_result = await db_session.execute(
        select(CardChangelog).where(CardChangelog.card_id == 26000000)
    )
    changelog_entries = list(changelog_result.scalars().all())
    field_names = {entry.field_name for entry in changelog_entries}
    assert "has_evolution" in field_names or "max_evolution_level" in field_names


@pytest.mark.asyncio
async def test_sync_cards_refuses_empty_api_response_when_cards_exist(db_session: AsyncSession):
    client = AsyncMock()
    client.get_cards = AsyncMock(
        side_effect=[
            [{"name": "Knight", "id": 26000000, "elixirCost": 3, "iconUrls": {"medium": "x"}}],
            [],
        ]
    )
    service = CardSyncService(client=client)

    await service.sync_cards(db_session)

    with pytest.raises(ValueError, match="Refusing to sync"):
        await service.sync_cards(db_session)

    card = await db_session.get(Card, 26000000)
    assert card is not None
    assert card.is_active is True


@pytest.mark.asyncio
async def test_sync_cards_deactivates_missing_card(db_session: AsyncSession):
    client = AsyncMock()
    client.get_cards = AsyncMock(
        side_effect=[
            [
                {"name": "Knight", "id": 26000000, "elixirCost": 3, "iconUrls": {"medium": "x"}},
                {"name": "Archers", "id": 26000001, "elixirCost": 3, "iconUrls": {"medium": "y"}},
            ],
            [{"name": "Archers", "id": 26000001, "elixirCost": 3, "iconUrls": {"medium": "y"}}],
        ]
    )
    service = CardSyncService(client=client)

    await service.sync_cards(db_session)
    result = await service.sync_cards(db_session)

    knight = await db_session.get(Card, 26000000)
    archers = await db_session.get(Card, 26000001)
    assert knight is not None
    assert knight.is_active is False
    assert archers is not None
    assert archers.is_active is True
    assert result.cards_deactivated == 1


@pytest.mark.asyncio
async def test_sync_cards_seeds_curated_profiles_when_cards_exist(db_session: AsyncSession):
    client = AsyncMock()
    client.get_cards = AsyncMock(
        return_value=[
            {"name": "Giant", "id": 26000003, "elixirCost": 5, "maxEvolutionLevel": 0, "iconUrls": {"medium": "x"}},
            {"name": "Goblin Barrel", "id": 28000004, "elixirCost": 3, "maxEvolutionLevel": 1, "iconUrls": {"medium": "y"}},
        ]
    )
    service = CardSyncService(client=client)

    await service.sync_cards(db_session)

    profiles = list((await db_session.execute(select(CardGameplayProfile))).scalars().all())
    assert len(profiles) >= 2
    giant = await db_session.get(CardGameplayProfile, (26000003, "base"))
    assert giant is not None
    assert giant.is_core is True
