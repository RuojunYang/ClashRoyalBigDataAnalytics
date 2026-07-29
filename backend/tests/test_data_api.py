from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.data.tower_troop_seed import TOWER_TROOPS
from app.db.models import Base, Battle, BattleDeckCard, BattleParticipant, Card, Player, TowerTroop
from app.db.session import get_db
from app.main import app


@pytest.fixture
async def data_api_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
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
            session.add_all([TowerTroop(**row) for row in TOWER_TROOPS])
            session.add(
                Player(
                    tag="#PLAYER1",
                    name="Alice",
                    is_tracked=True,
                    leaderboard_seeded=True,
                )
            )
            session.add(
                Battle(
                    id=1,
                    battle_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
                    battle_type="pathOfLegend",
                    battle_key="20260701_PLAYER1_PLAYER2",
                )
            )
            session.add(
                BattleParticipant(
                    battle_id=1,
                    player_tag="#PLAYER1",
                    side="team",
                    won=True,
                    tower_card_id=159000000,
                )
            )
            session.add(
                BattleDeckCard(
                    battle_id=1,
                    player_tag="#PLAYER1",
                    slot=0,
                    card_id=26000000,
                    played_variant="evo_1",
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
async def test_list_data_tables(data_api_client: AsyncClient):
    response = await data_api_client.get("/api/data/tables")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["tables"]}
    assert "cards" in names
    assert "battle_deck_cards" in names
    assert "tower_troops" in names


@pytest.mark.asyncio
async def test_export_table_json_records(data_api_client: AsyncClient):
    response = await data_api_client.get("/api/data/cards")
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert rows[0]["name"] == "Knight"
    assert rows[0]["has_evolution"] is True


@pytest.mark.asyncio
async def test_export_tower_troops(data_api_client: AsyncClient):
    response = await data_api_client.get("/api/data/tower_troops")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 4
    names = {row["name"] for row in rows}
    assert names == {"Tower Princess", "Cannoneer", "Dagger Duchess", "Royal Chef"}


@pytest.mark.asyncio
async def test_export_table_json_with_meta(data_api_client: AsyncClient):
    response = await data_api_client.get("/api/data/battle_deck_cards", params={"meta": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["table"] == "battle_deck_cards"
    assert payload["count"] == 1
    assert payload["rows"][0]["played_variant"] == "evo_1"
    assert "card_level" not in payload["rows"][0]


@pytest.mark.asyncio
async def test_export_table_csv(data_api_client: AsyncClient):
    response = await data_api_client.get("/api/data/players", params={"format": "csv"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text
    assert "tag,name" in body.replace("\r", "")
    assert "#PLAYER1" in body


@pytest.mark.asyncio
async def test_export_table_filter(data_api_client: AsyncClient):
    response = await data_api_client.get(
        "/api/data/battle_deck_cards",
        params={"card_id": 26000000, "meta": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["filters"] == {"card_id": "26000000"}


@pytest.mark.asyncio
async def test_export_battle_participants_filter_by_tower(data_api_client: AsyncClient):
    response = await data_api_client.get(
        "/api/data/battle_participants",
        params={"tower_card_id": 159000000, "meta": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["rows"][0]["tower_card_id"] == 159000000
    assert payload["filters"] == {"tower_card_id": "159000000"}


@pytest.mark.asyncio
async def test_export_unknown_table(data_api_client: AsyncClient):
    response = await data_api_client.get("/api/data/not_a_table")
    assert response.status_code == 404
