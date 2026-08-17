from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import OperationRun
from app.db.session import get_db
from app.schemas.card import CardSyncResult
from app.schemas.leaderboard import BattlelogSyncResult, LeaderboardSyncResult
from app.schemas.operation_run import OperationRunResponse
from app.services.battlelog_sync import BattlelogSyncService
from app.services.card_sync import CardSyncService
from app.services.leaderboard_sync import LeaderboardSyncService

router = APIRouter(prefix="/api/admin", tags=["admin"])


def verify_admin_api_key(x_admin_api_key: str = Header(..., alias="X-Admin-API-Key")) -> None:
    if x_admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin API key")


@router.get("/operations/{run_id}", response_model=OperationRunResponse, dependencies=[Depends(verify_admin_api_key)])
async def get_operation_run(run_id: int, db: AsyncSession = Depends(get_db)) -> OperationRun:
    run = await db.get(OperationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Operation run not found")
    return run


@router.get("/operations/latest", response_model=OperationRunResponse, dependencies=[Depends(verify_admin_api_key)])
async def get_latest_operation_run(
    operation: str = Query(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
) -> OperationRun:
    result = await db.execute(
        select(OperationRun)
        .where(OperationRun.operation == operation)
        .order_by(OperationRun.started_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"No operation runs for {operation}")
    return run


@router.post("/sync/cards", response_model=CardSyncResult, dependencies=[Depends(verify_admin_api_key)])
async def sync_cards(db: AsyncSession = Depends(get_db)) -> CardSyncResult:
    service = CardSyncService()
    return await service.sync_cards(db)


@router.post("/sync/leaderboard", response_model=LeaderboardSyncResult, dependencies=[Depends(verify_admin_api_key)])
async def sync_leaderboard(
    top_n: int | None = Query(default=None, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardSyncResult:
    service = LeaderboardSyncService()
    return await service.sync_leaderboard(db, top_n=top_n)


@router.post("/sync/battlelog", response_model=BattlelogSyncResult, dependencies=[Depends(verify_admin_api_key)])
async def sync_battlelog(
    batch_size: int | None = Query(default=None, ge=0, le=1000),
    battles_per_player: int | None = Query(default=None, ge=1, le=100),
    opponent_expansion_rounds: int | None = Query(default=None, ge=0, le=10),
    db: AsyncSession = Depends(get_db),
) -> BattlelogSyncResult:
    service = BattlelogSyncService()
    return await service.sync_battlelog(
        db,
        batch_size=batch_size,
        battles_per_player=battles_per_player,
        opponent_expansion_rounds=opponent_expansion_rounds,
    )
