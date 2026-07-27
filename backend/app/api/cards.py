from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Card, CardChangelog, CardGameplayProfile
from app.db.session import get_db
from app.schemas.card import (
    CardChangelogResponse,
    CardGameplayProfileResponse,
    CardResponse,
    CardWithProfilesResponse,
)

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("", response_model=list[CardResponse])
async def list_cards(
    card_type: str | None = Query(default=None),
    has_evolution: bool | None = Query(default=None),
    elixir_cost: int | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    is_core: bool | None = Query(default=None),
    variant: str = Query(default="base"),
    db: AsyncSession = Depends(get_db),
) -> list[Card]:
    query = select(Card)
    if not include_inactive:
        query = query.where(Card.is_active.is_(True))
    if card_type is not None:
        query = query.where(Card.card_type == card_type)
    if has_evolution is not None:
        query = query.where(Card.has_evolution.is_(has_evolution))
    if elixir_cost is not None:
        query = query.where(Card.elixir_cost == elixir_cost)
    if is_core is not None:
        query = query.join(
            CardGameplayProfile,
            (CardGameplayProfile.card_id == Card.id) & (CardGameplayProfile.variant == variant),
        ).where(CardGameplayProfile.is_core.is_(is_core))

    query = query.order_by(Card.elixir_cost.nulls_last(), Card.name)
    result = await db.execute(query)
    return list(result.scalars().unique().all())


@router.get("/{card_id}/profiles", response_model=CardWithProfilesResponse)
async def get_card_profiles(card_id: int, db: AsyncSession = Depends(get_db)) -> Card:
    result = await db.execute(
        select(Card)
        .options(selectinload(Card.gameplay_profiles).selectinload(CardGameplayProfile.role))
        .where(Card.id == card_id)
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(card_id: int, db: AsyncSession = Depends(get_db)) -> Card:
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.get("/{card_id}/changelog", response_model=list[CardChangelogResponse])
async def get_card_changelog(card_id: int, db: AsyncSession = Depends(get_db)) -> list[CardChangelog]:
    card_result = await db.execute(select(Card.id).where(Card.id == card_id))
    if card_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Card not found")

    result = await db.execute(
        select(CardChangelog)
        .where(CardChangelog.card_id == card_id)
        .order_by(CardChangelog.changed_at.desc())
    )
    return list(result.scalars().all())
