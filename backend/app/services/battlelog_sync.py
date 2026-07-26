import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Battle, BattleDeckCard, BattleParticipant, Player
from app.schemas.leaderboard import BattlelogSyncResult
from app.services.battle_mapper import map_battle_entry, should_include_battle
from app.services.clash_api import ClashRoyaleClient

logger = logging.getLogger(__name__)


class BattlelogSyncService:
    def __init__(self, client: ClashRoyaleClient | None = None) -> None:
        self.client = client or ClashRoyaleClient()

    async def sync_battlelog(
        self,
        session: AsyncSession,
        batch_size: int | None = None,
    ) -> BattlelogSyncResult:
        now = datetime.now(UTC)

        result = await session.execute(
            select(Player)
            .where(Player.is_tracked.is_(True))
            .order_by(Player.latest_rank.nulls_last(), Player.tag)
        )
        tracked_players = list(result.scalars().all())
        players_to_sync = tracked_players if batch_size is None else tracked_players[:batch_size]

        players_processed = 0
        battles_created = 0
        battles_skipped = 0
        deck_cards_created = 0

        for player in players_to_sync:
            api_battles = await self.client.get_player_battlelog(player.tag)
            players_processed += 1

            for api_entry in api_battles:
                if not should_include_battle(api_entry, settings.sync_ranked_battles_only):
                    continue

                mapped = map_battle_entry(api_entry)
                if mapped is None:
                    continue

                existing = await session.execute(
                    select(Battle.id).where(Battle.battle_key == mapped["battle_key"])
                )
                if existing.scalar_one_or_none() is not None:
                    battles_skipped += 1
                    continue

                battle = Battle(
                    battle_key=mapped["battle_key"],
                    battle_time=mapped["battle_time"],
                    battle_type=mapped["battle_type"],
                    game_mode_id=mapped["game_mode_id"],
                    game_mode_name=mapped["game_mode_name"],
                    arena_id=mapped["arena_id"],
                    arena_name=mapped["arena_name"],
                    league_number=mapped["league_number"],
                    synced_at=now,
                )
                session.add(battle)
                await session.flush()

                for participant in mapped["participants"]:
                    session.add(
                        BattleParticipant(
                            battle_id=battle.id,
                            player_tag=participant["player_tag"],
                            side=participant["side"],
                            starting_trophies=participant["starting_trophies"],
                            trophy_change=participant["trophy_change"],
                            crowns=participant["crowns"],
                            won=participant["won"],
                        )
                    )
                    for slot, card in enumerate(participant["cards"]):
                        session.add(
                            BattleDeckCard(
                                battle_id=battle.id,
                                player_tag=participant["player_tag"],
                                slot=slot,
                                card_id=card["id"],
                                card_level=card.get("level"),
                            )
                        )
                        deck_cards_created += 1

                battles_created += 1

            player.last_battlelog_sync_at = now
            player.updated_at = now

        await session.commit()

        logger.info(
            "Battlelog sync complete: players=%d battles_created=%d skipped=%d deck_cards=%d",
            players_processed,
            battles_created,
            battles_skipped,
            deck_cards_created,
        )

        return BattlelogSyncResult(
            players_processed=players_processed,
            battles_created=battles_created,
            battles_skipped=battles_skipped,
            deck_cards_created=deck_cards_created,
            total_tracked=len(tracked_players),
        )
