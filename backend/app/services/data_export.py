import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase

from app.db.models import (
    Battle,
    BattleDeckCard,
    BattleParticipant,
    Card,
    CardChangelog,
    CardGameplayProfile,
    LeaderboardEntry,
    LeaderboardSnapshot,
    Player,
    SyncRun,
    TowerTroop,
)

TABLE_MODELS: dict[str, type[DeclarativeBase]] = {
    "cards": Card,
    "card_changelog": CardChangelog,
    "card_gameplay_profiles": CardGameplayProfile,
    "players": Player,
    "leaderboard_snapshots": LeaderboardSnapshot,
    "leaderboard_entries": LeaderboardEntry,
    "battles": Battle,
    "battle_participants": BattleParticipant,
    "battle_deck_cards": BattleDeckCard,
    "sync_runs": SyncRun,
    "tower_troops": TowerTroop,
}

TABLE_FILTERS: dict[str, tuple[str, ...]] = {
    "battles": ("battle_time_after", "synced_at_after"),
    "battle_participants": ("battle_id", "player_tag", "tower_card_id"),
    "battle_deck_cards": ("battle_id", "player_tag", "card_id"),
    "leaderboard_entries": ("snapshot_id", "player_tag"),
    "card_changelog": ("card_id",),
    "card_gameplay_profiles": ("card_id", "is_core"),
    "players": ("is_tracked", "leaderboard_seeded"),
}


def list_export_tables() -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for name, model in TABLE_MODELS.items():
        mapper = sa_inspect(model)
        tables.append(
            {
                "name": name,
                "columns": [column.key for column in mapper.columns],
                "filters": list(TABLE_FILTERS.get(name, ())),
            }
        )
    return tables


def serialize_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dict, list)):
        return value
    return value


def model_to_dict(instance: DeclarativeBase) -> dict[str, Any]:
    mapper = sa_inspect(type(instance))
    row: dict[str, Any] = {}
    for attr in mapper.column_attrs:
        column_name = attr.columns[0].key
        row[column_name] = serialize_cell(getattr(instance, attr.key))
    return row


def _apply_bool_filter(query: Select[Any], column: Any, raw: str) -> Select[Any]:
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return query.where(column.is_(True))
    if normalized in {"false", "0", "no"}:
        return query.where(column.is_(False))
    raise ValueError(f"Invalid boolean filter value: {raw}")


def _apply_datetime_filter(query: Select[Any], column: Any, raw: str) -> Select[Any]:
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return query.where(column >= value)


def build_table_query(
    table: str,
    *,
    limit: int,
    offset: int,
    filters: dict[str, str],
) -> Select[Any]:
    model = TABLE_MODELS[table]
    query = select(model)

    if table == "battles":
        if "battle_time_after" in filters:
            query = _apply_datetime_filter(query, Battle.battle_time, filters["battle_time_after"])
        if "synced_at_after" in filters:
            query = _apply_datetime_filter(query, Battle.synced_at, filters["synced_at_after"])
    elif table == "battle_participants":
        if "battle_id" in filters:
            query = query.where(BattleParticipant.battle_id == int(filters["battle_id"]))
        if "player_tag" in filters:
            query = query.where(BattleParticipant.player_tag == filters["player_tag"])
        if "tower_card_id" in filters:
            query = query.where(BattleParticipant.tower_card_id == int(filters["tower_card_id"]))
    elif table == "battle_deck_cards":
        if "battle_id" in filters:
            query = query.where(BattleDeckCard.battle_id == int(filters["battle_id"]))
        if "player_tag" in filters:
            query = query.where(BattleDeckCard.player_tag == filters["player_tag"])
        if "card_id" in filters:
            query = query.where(BattleDeckCard.card_id == int(filters["card_id"]))
    elif table == "leaderboard_entries":
        if "snapshot_id" in filters:
            query = query.where(LeaderboardEntry.snapshot_id == int(filters["snapshot_id"]))
        if "player_tag" in filters:
            query = query.where(LeaderboardEntry.player_tag == filters["player_tag"])
    elif table == "card_changelog":
        if "card_id" in filters:
            query = query.where(CardChangelog.card_id == int(filters["card_id"]))
    elif table == "card_gameplay_profiles":
        if "card_id" in filters:
            query = query.where(CardGameplayProfile.card_id == int(filters["card_id"]))
        if "is_core" in filters:
            query = _apply_bool_filter(query, CardGameplayProfile.is_core, filters["is_core"])
    elif table == "players":
        if "is_tracked" in filters:
            query = _apply_bool_filter(query, Player.is_tracked, filters["is_tracked"])
        if "leaderboard_seeded" in filters:
            query = _apply_bool_filter(query, Player.leaderboard_seeded, filters["leaderboard_seeded"])

    pk_names = [column.key for column in sa_inspect(model).primary_key]
    order_columns = [getattr(model, name) for name in pk_names]
    query = query.order_by(*order_columns).limit(limit).offset(offset)
    return query


async def fetch_table_rows(
    db: AsyncSession,
    table: str,
    *,
    limit: int,
    offset: int,
    filters: dict[str, str],
) -> tuple[list[dict[str, Any]], int | None]:
    query = build_table_query(table, limit=limit, offset=offset, filters=filters)
    result = await db.execute(query)
    rows = [model_to_dict(row) for row in result.scalars().all()]

    total_count: int | None = None
    if offset == 0 and len(rows) < limit:
        total_count = len(rows)
    return rows, total_count


async def count_table_rows(db: AsyncSession, table: str, filters: dict[str, str]) -> int:
    model = TABLE_MODELS[table]
    query = select(func.count()).select_from(model)

    if table == "battles":
        if "battle_time_after" in filters:
            query = _apply_datetime_filter(query, Battle.battle_time, filters["battle_time_after"])
        if "synced_at_after" in filters:
            query = _apply_datetime_filter(query, Battle.synced_at, filters["synced_at_after"])
    elif table == "battle_participants":
        if "battle_id" in filters:
            query = query.where(BattleParticipant.battle_id == int(filters["battle_id"]))
        if "player_tag" in filters:
            query = query.where(BattleParticipant.player_tag == filters["player_tag"])
        if "tower_card_id" in filters:
            query = query.where(BattleParticipant.tower_card_id == int(filters["tower_card_id"]))
    elif table == "battle_deck_cards":
        if "battle_id" in filters:
            query = query.where(BattleDeckCard.battle_id == int(filters["battle_id"]))
        if "player_tag" in filters:
            query = query.where(BattleDeckCard.player_tag == filters["player_tag"])
        if "card_id" in filters:
            query = query.where(BattleDeckCard.card_id == int(filters["card_id"]))
    elif table == "leaderboard_entries":
        if "snapshot_id" in filters:
            query = query.where(LeaderboardEntry.snapshot_id == int(filters["snapshot_id"]))
        if "player_tag" in filters:
            query = query.where(LeaderboardEntry.player_tag == filters["player_tag"])
    elif table == "card_changelog":
        if "card_id" in filters:
            query = query.where(CardChangelog.card_id == int(filters["card_id"]))
    elif table == "card_gameplay_profiles":
        if "card_id" in filters:
            query = query.where(CardGameplayProfile.card_id == int(filters["card_id"]))
        if "is_core" in filters:
            query = _apply_bool_filter(query, CardGameplayProfile.is_core, filters["is_core"])
    elif table == "players":
        if "is_tracked" in filters:
            query = _apply_bool_filter(query, Player.is_tracked, filters["is_tracked"])
        if "leaderboard_seeded" in filters:
            query = _apply_bool_filter(query, Player.leaderboard_seeded, filters["leaderboard_seeded"])

    result = await db.execute(query)
    return int(result.scalar_one())


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""

    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                for key, value in row.items()
            }
        )
    return output.getvalue()
