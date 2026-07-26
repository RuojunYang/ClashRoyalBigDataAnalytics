from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    elixir_cost: int | None
    max_evolution_level: int
    has_evolution: bool
    has_hero: bool
    card_type: str
    is_active: bool
    first_seen_at: datetime
    synced_at: datetime
    updated_at: datetime


class CardChangelogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    changed_at: datetime
    field_name: str
    old_value: str | None
    new_value: str | None
    sync_batch_id: UUID


class SyncRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sync_type: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    cards_created: int
    cards_updated: int
    cards_deactivated: int
    changes_logged: int
    error_message: str | None
    sync_batch_id: UUID


class CardSyncResult(BaseModel):
    sync_run_id: int
    sync_batch_id: UUID
    cards_created: int = 0
    cards_updated: int = 0
    cards_deactivated: int = 0
    changes_logged: int = 0
    total_active_cards: int = 0
