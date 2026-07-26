import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import admin, cards, players
from app.config import settings
from app.db.session import async_session_factory
from app.scheduler import start_scheduler, stop_scheduler
from app.services.card_sync import CardSyncService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()

    if settings.sync_on_startup and settings.clash_royale_api_key:
        logger.info("Running startup card sync")
        async with async_session_factory() as session:
            service = CardSyncService()
            try:
                result = await service.sync_cards(session)
                logger.info("Startup card sync finished: %s", result.model_dump())
            except Exception:
                logger.exception("Startup card sync failed")

    yield

    stop_scheduler()


app = FastAPI(title="Clash Royale Big Data Analytics", lifespan=lifespan)
app.include_router(cards.router)
app.include_router(admin.router)
app.include_router(players.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
