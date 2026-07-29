from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.card_profile_seed import CARD_GAMEPLAY_PROFILES
from app.db.models import Card, CardGameplayProfile


async def ensure_curated_profiles(session: AsyncSession) -> int:
    """Insert curated gameplay profiles when matching cards exist (idempotent)."""
    seeded = 0
    for row in CARD_GAMEPLAY_PROFILES:
        card_id = row["card_id"]
        variant = row["variant"]
        card_exists = await session.scalar(select(Card.id).where(Card.id == card_id))
        if card_exists is None:
            continue

        existing = await session.get(CardGameplayProfile, (card_id, variant))
        if existing is not None:
            continue

        session.add(
            CardGameplayProfile(
                card_id=card_id,
                variant=variant,
                is_core=row["is_core"],
                related_card_id=row.get("related_card_id"),
                notes=row.get("notes"),
            )
        )
        seeded += 1
    return seeded
