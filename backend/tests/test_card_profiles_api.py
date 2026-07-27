from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.data.card_profile_seed import CARD_GAMEPLAY_PROFILES, CARD_THREAT_ROLES
from app.db.models import Base, Card, CardGameplayProfile, CardThreatRole
from app.db.session import get_db
from app.main import app


@pytest.fixture
async def api_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            session.add(
                Card(
                    id=28000004,
                    name="Goblin Barrel",
                    elixir_cost=3,
                    max_evolution_level=0,
                    has_evolution=False,
                    has_hero=False,
                    card_type="spell",
                )
            )
            session.add_all([CardThreatRole(**role) for role in CARD_THREAT_ROLES])
            session.add(
                CardGameplayProfile(
                    card_id=28000004,
                    variant="base",
                    role_code="spell_win_condition",
                    is_core=True,
                    notes="Goblin Barrel",
                )
            )
            await session.commit()
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_cards_filter_is_core_spell(api_client: AsyncClient):
    response = await api_client.get("/api/cards", params={"is_core": True, "variant": "base"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Goblin Barrel"
    assert data[0]["card_type"] == "spell"


@pytest.mark.asyncio
async def test_get_card_profiles(api_client: AsyncClient):
    response = await api_client.get("/api/cards/28000004/profiles")
    assert response.status_code == 200
    data = response.json()
    assert data["card_type"] == "spell"
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["is_core"] is True
    assert data["profiles"][0]["role_code"] == "spell_win_condition"
