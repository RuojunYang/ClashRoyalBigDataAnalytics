from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeaderboardSyncResult(BaseModel):
    snapshot_id: int
    top_n: int
    entries_synced: int
    players_tracked: int


class BattlelogSyncResult(BaseModel):
    players_processed: int
    battles_created: int
    battles_skipped: int
    deck_cards_created: int
    total_tracked: int


class LeaderboardEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int
    player_tag: str
    rank: int
    elo_rating: int
    name: str | None
    exp_level: int | None
    clan_tag: str | None
    clan_name: str | None


class LeaderboardSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    synced_at: datetime
    top_n: int
    entries_count: int
    status: str
    entries: list[LeaderboardEntryResponse] = []


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tag: str
    name: str | None
    latest_elo_rating: int | None
    latest_rank: int | None
    exp_level: int | None
    clan_tag: str | None
    clan_name: str | None
    is_tracked: bool
    off_leaderboard_count: int
    last_leaderboard_sync_at: datetime | None
    last_battlelog_sync_at: datetime | None
    first_seen_at: datetime
    updated_at: datetime
