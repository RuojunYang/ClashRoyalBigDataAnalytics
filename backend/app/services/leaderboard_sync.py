import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import LeaderboardEntry, LeaderboardSnapshot, Player
from app.schemas.leaderboard import LeaderboardSyncResult
from app.services.clash_api import ClashRoyaleClient
from app.services.leaderboard_mapper import map_leaderboard_entry
from app.services.operation_run_tracker import OperationRunTracker

logger = logging.getLogger(__name__)


class LeaderboardSyncService:
    def __init__(self, client: ClashRoyaleClient | None = None) -> None:
        self.client = client or ClashRoyaleClient()

    async def sync_leaderboard(
        self,
        session: AsyncSession,
        top_n: int | None = None,
        page_limit: int | None = None,
        untrack_after_misses: int | None = None,
    ) -> LeaderboardSyncResult:
        top_n = top_n or settings.leaderboard_top_n
        page_limit = page_limit or settings.leaderboard_page_limit
        untrack_after_misses = untrack_after_misses or settings.untrack_after_misses
        now = datetime.now(UTC)

        params = {
            "top_n": top_n,
            "page_limit": page_limit,
            "untrack_after_misses": untrack_after_misses,
        }
        tracker = OperationRunTracker(session, "leaderboard", params)
        await tracker.start()
        await session.commit()

        try:
            api_entries = await self.client.get_global_pol_players_top_n(top_n, page_limit)
            mapped_entries = [map_leaderboard_entry(entry) for entry in api_entries]

            await tracker.maybe_update_progress(
                {"items_processed": len(mapped_entries), "phase": "fetched"},
                force=True,
            )

            snapshot = LeaderboardSnapshot(
                source="global_pol",
                top_n=top_n,
                entries_count=len(mapped_entries),
                status="success",
                synced_at=now,
            )
            session.add(snapshot)
            await session.flush()

            tracked_tags: set[str] = set()
            for entry in mapped_entries:
                session.add(LeaderboardEntry(snapshot_id=snapshot.id, **entry))
                tracked_tags.add(entry["player_tag"])

                existing = await session.get(Player, entry["player_tag"])
                if existing is None:
                    session.add(
                        Player(
                            tag=entry["player_tag"],
                            name=entry["name"],
                            latest_elo_rating=entry["elo_rating"],
                            latest_rank=entry["rank"],
                            exp_level=entry["exp_level"],
                            clan_tag=entry["clan_tag"],
                            clan_name=entry["clan_name"],
                            is_tracked=True,
                            leaderboard_seeded=True,
                            off_leaderboard_count=0,
                            last_leaderboard_sync_at=now,
                            first_seen_at=now,
                            updated_at=now,
                        )
                    )
                else:
                    existing.name = entry["name"]
                    existing.latest_elo_rating = entry["elo_rating"]
                    existing.latest_rank = entry["rank"]
                    existing.exp_level = entry["exp_level"]
                    existing.clan_tag = entry["clan_tag"]
                    existing.clan_name = entry["clan_name"]
                    existing.is_tracked = True
                    existing.leaderboard_seeded = True
                    existing.off_leaderboard_count = 0
                    existing.last_leaderboard_sync_at = now
                    existing.updated_at = now

            if tracked_tags:
                tracked_result = await session.execute(
                    select(Player).where(Player.leaderboard_seeded.is_(True), Player.is_tracked.is_(True))
                )
                for player in tracked_result.scalars():
                    if player.tag in tracked_tags:
                        continue
                    player.off_leaderboard_count += 1
                    if player.off_leaderboard_count >= untrack_after_misses:
                        player.is_tracked = False
                    player.updated_at = now

            result = {
                "snapshot_id": snapshot.id,
                "top_n": top_n,
                "entries_synced": len(mapped_entries),
                "players_tracked": len(tracked_tags),
            }
            await tracker.finish("success", result, commit=True)

            logger.info(
                "Leaderboard sync complete: snapshot_id=%s entries=%d top_n=%d",
                snapshot.id,
                len(mapped_entries),
                top_n,
            )

            return LeaderboardSyncResult(
                operation_run_id=tracker.run_id,
                snapshot_id=snapshot.id,
                top_n=top_n,
                entries_synced=len(mapped_entries),
                players_tracked=len(tracked_tags),
            )
        except Exception as exc:
            logger.exception("Leaderboard sync failed")
            await session.rollback()
            await tracker.fail(str(exc), commit=True)
            raise
