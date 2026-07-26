from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.schemas.card import CardSyncResult
from app.services.card_sync import CardSyncService

router = APIRouter(prefix="/api/admin", tags=["admin"])


def verify_admin_api_key(x_admin_api_key: str = Header(..., alias="X-Admin-API-Key")) -> None:
    if x_admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin API key")


@router.post("/sync/cards", response_model=CardSyncResult, dependencies=[Depends(verify_admin_api_key)])
async def sync_cards(db: AsyncSession = Depends(get_db)) -> CardSyncResult:
    service = CardSyncService()
    return await service.sync_cards(db)
