import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Card, CardChangelog, SyncRun
from app.schemas.card import CardSyncResult
from app.services.card_mapper import map_api_card
from app.services.card_profile_seed_service import ensure_curated_profiles
from app.services.clash_api import ClashRoyaleClient
from app.services.operation_run_tracker import OperationRunTracker

logger = logging.getLogger(__name__)

TRACKED_FIELDS = (
    "name",
    "elixir_cost",
    "max_evolution_level",
    "has_evolution",
    "has_hero",
    "card_type",
)


def _serialize(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class CardSyncService:
    def __init__(self, client: ClashRoyaleClient | None = None) -> None:
        self.client = client or ClashRoyaleClient()

    async def sync_cards(self, session: AsyncSession) -> CardSyncResult:
        sync_batch_id = uuid.uuid4()
        sync_run = SyncRun(sync_type="cards", status="running", sync_batch_id=sync_batch_id)
        session.add(sync_run)
        await session.flush()
        sync_run_id = sync_run.id

        tracker = OperationRunTracker(session, "cards", {"sync_batch_id": str(sync_batch_id)})
        await tracker.start()
        await session.commit()

        try:
            api_cards = await self.client.get_cards()
            mapped_cards = [map_api_card(card) for card in api_cards]
            api_ids = {card["id"] for card in mapped_cards}

            existing_result = await session.execute(select(Card))
            existing_cards = {card.id: card for card in existing_result.scalars().all()}

            if not mapped_cards and any(card.is_active for card in existing_cards.values()):
                raise ValueError(
                    "Refusing to sync: API returned zero cards while active cards exist in the database"
                )

            now = datetime.now(UTC)
            created = 0
            updated = 0
            changes_logged = 0

            await tracker.maybe_update_progress(
                {"items_processed": len(mapped_cards), "phase": "fetched"},
                force=True,
            )

            for mapped in mapped_cards:
                card_id = mapped["id"]
                existing = existing_cards.get(card_id)

                if existing is None:
                    card = Card(**mapped, is_active=True, first_seen_at=now, synced_at=now, updated_at=now)
                    session.add(card)
                    session.add(
                        CardChangelog(
                            card_id=card_id,
                            field_name="created",
                            old_value=None,
                            new_value=mapped["name"],
                            sync_batch_id=sync_batch_id,
                        )
                    )
                    created += 1
                    changes_logged += 1
                    continue

                field_changes: list[tuple[str, Any, Any]] = []
                for field in TRACKED_FIELDS:
                    old_value = getattr(existing, field)
                    new_value = mapped[field]
                    if old_value != new_value:
                        field_changes.append((field, old_value, new_value))
                        setattr(existing, field, new_value)

                if not existing.is_active:
                    field_changes.append(("is_active", False, True))
                    existing.is_active = True

                if field_changes:
                    existing.synced_at = now
                    existing.updated_at = now
                    updated += 1
                    for field_name, old_value, new_value in field_changes:
                        session.add(
                            CardChangelog(
                                card_id=card_id,
                                field_name=field_name,
                                old_value=_serialize(old_value),
                                new_value=_serialize(new_value),
                                sync_batch_id=sync_batch_id,
                            )
                        )
                        changes_logged += 1
                else:
                    existing.synced_at = now

            deactivated = 0
            for card_id, existing in existing_cards.items():
                if card_id not in api_ids and existing.is_active:
                    existing.is_active = False
                    existing.synced_at = now
                    existing.updated_at = now
                    session.add(
                        CardChangelog(
                            card_id=card_id,
                            field_name="is_active",
                            old_value="True",
                            new_value="False",
                            sync_batch_id=sync_batch_id,
                        )
                    )
                    deactivated += 1
                    changes_logged += 1

            total_active_result = await session.execute(
                select(func.count()).select_from(Card).where(Card.is_active.is_(True))
            )
            total_active_cards = total_active_result.scalar_one()

            profiles_seeded = await ensure_curated_profiles(session)

            sync_run.status = "success"
            sync_run.finished_at = datetime.now(UTC)
            sync_run.cards_created = created
            sync_run.cards_updated = updated
            sync_run.cards_deactivated = deactivated
            sync_run.changes_logged = changes_logged

            result = {
                "sync_run_id": sync_run.id,
                "sync_batch_id": str(sync_batch_id),
                "cards_created": created,
                "cards_updated": updated,
                "cards_deactivated": deactivated,
                "changes_logged": changes_logged,
                "total_active_cards": total_active_cards,
                "profiles_seeded": profiles_seeded,
            }
            await tracker.finish("success", result, commit=False)
            await session.commit()

            logger.info(
                "Card sync complete: created=%d updated=%d deactivated=%d changes=%d profiles_seeded=%d",
                created,
                updated,
                deactivated,
                changes_logged,
                profiles_seeded,
            )

            return CardSyncResult(
                operation_run_id=tracker.run_id,
                sync_run_id=sync_run.id,
                sync_batch_id=sync_batch_id,
                cards_created=created,
                cards_updated=updated,
                cards_deactivated=deactivated,
                changes_logged=changes_logged,
                total_active_cards=total_active_cards,
            )
        except Exception as exc:
            logger.exception("Card sync failed")
            await session.rollback()
            sync_run_row = await session.get(SyncRun, sync_run_id)
            if sync_run_row is not None:
                sync_run_row.status = "failed"
                sync_run_row.finished_at = datetime.now(UTC)
                sync_run_row.error_message = str(exc)
            await tracker.fail(str(exc), commit=True)
            raise
