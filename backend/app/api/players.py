from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import LeaderboardSnapshot, Player
from app.db.session import get_db
from app.schemas.leaderboard import LeaderboardSnapshotResponse, PlayerResponse

router = APIRouter(tags=["players"])


@router.get("/api/players", response_model=list[PlayerResponse])
async def list_players(
    tracked_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
) -> list[Player]:
    query = select(Player)
    if tracked_only:
        query = query.where(Player.is_tracked.is_(True))
    query = query.order_by(Player.latest_rank.nulls_last(), Player.tag)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/api/leaderboard/latest", response_model=LeaderboardSnapshotResponse)
async def get_latest_leaderboard(db: AsyncSession = Depends(get_db)) -> LeaderboardSnapshot:
    result = await db.execute(
        select(LeaderboardSnapshot)
        .options(selectinload(LeaderboardSnapshot.entries))
        .order_by(LeaderboardSnapshot.synced_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No leaderboard snapshot found")
    snapshot.entries.sort(key=lambda entry: entry.rank)
    return snapshot
