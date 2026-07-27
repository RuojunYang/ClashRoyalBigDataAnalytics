import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.data.card_profile_seed import CARD_GAMEPLAY_PROFILES, CARD_THREAT_ROLES
from app.db.models import Base, Card, CardGameplayProfile, CardThreatRole


@pytest.fixture
async def profile_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add_all(
            [
                Card(
                    id=26000003,
                    name="Giant",
                    elixir_cost=5,
                    max_evolution_level=0,
                    has_evolution=False,
                    has_hero=False,
                    card_type="troop",
                ),
                Card(
                    id=26000038,
                    name="Ice Golem",
                    elixir_cost=2,
                    max_evolution_level=0,
                    has_evolution=False,
                    has_hero=False,
                    card_type="troop",
                ),
                Card(
                    id=28000004,
                    name="Goblin Barrel",
                    elixir_cost=3,
                    max_evolution_level=0,
                    has_evolution=False,
                    has_hero=False,
                    card_type="spell",
                ),
                Card(
                    id=27000009,
                    name="Tombstone",
                    elixir_cost=3,
                    max_evolution_level=0,
                    has_evolution=False,
                    has_hero=True,
                    card_type="building",
                ),
            ]
        )
        session.add_all([CardThreatRole(**role) for role in CARD_THREAT_ROLES])
        session.add_all([CardGameplayProfile(**row) for row in CARD_GAMEPLAY_PROFILES if row["card_id"] in {26000003, 26000038, 28000004, 27000009}])
        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_spell_can_be_core(profile_db: AsyncSession):
    barrel = await profile_db.get(CardGameplayProfile, (28000004, "base"))
    assert barrel is not None
    assert barrel.is_core is True
    assert barrel.role_code == "spell_win_condition"

    card = await profile_db.get(Card, 28000004)
    assert card is not None
    assert card.card_type == "spell"


@pytest.mark.asyncio
async def test_troop_support_is_not_core(profile_db: AsyncSession):
    ice_golem = await profile_db.get(CardGameplayProfile, (26000038, "base"))
    assert ice_golem is not None
    assert ice_golem.is_core is False
    assert ice_golem.role_code == "support_tank"


@pytest.mark.asyncio
async def test_tombstone_has_multiple_variants(profile_db: AsyncSession):
    base = await profile_db.get(CardGameplayProfile, (27000009, "base"))
    hero = await profile_db.get(CardGameplayProfile, (27000009, "hero"))
    assert base is not None and base.is_core is False
    assert hero is not None and hero.is_core is True
