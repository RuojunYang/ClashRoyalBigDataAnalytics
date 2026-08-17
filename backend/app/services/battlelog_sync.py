import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.tower_troop_seed import KNOWN_TOWER_TROOP_IDS
from app.db.models import Battle, BattleDeckCard, BattleParticipant, Player
from app.schemas.leaderboard import BattlelogSyncResult
from app.services.battle_mapper import (
    extract_participant_profiles,
    map_battle_entry,
    should_include_battle,
)
from app.services.card_variant import infer_played_variant
from app.services.clash_api import ClashRoyaleClient
from app.services.operation_run_tracker import OperationRunTracker

logger = logging.getLogger(__name__)


@dataclass
class _SyncStats:
    players_processed: int = 0
    battles_created: int = 0
    battles_skipped: int = 0
    deck_cards_created: int = 0
    opponents_discovered: int = 0


@dataclass
class _PlayerSyncResult:
    opponent_tags: set[str] = field(default_factory=set)


class BattlelogSyncService:
    def __init__(self, client: ClashRoyaleClient | None = None) -> None:
        self.client = client or ClashRoyaleClient()

    async def sync_battlelog(
        self,
        session: AsyncSession,
        batch_size: int | None = None,
        battles_per_player: int | None = None,
        opponent_expansion_rounds: int | None = None,
    ) -> BattlelogSyncResult:
        now = datetime.now(UTC)
        battles_per_player = settings.battles_per_player if battles_per_player is None else battles_per_player
        opponent_expansion_rounds = (
            settings.opponent_expansion_rounds if opponent_expansion_rounds is None else opponent_expansion_rounds
        )
        if batch_size is None:
            batch_size = settings.battlelog_batch_size

        seed_result = await session.execute(
            select(Player)
            .where(Player.is_tracked.is_(True), Player.leaderboard_seeded.is_(True))
            .order_by(Player.latest_rank.nulls_last(), Player.tag)
        )
        seed_players = list(seed_result.scalars().all())
        if batch_size is not None and batch_size > 0:
            seed_players = seed_players[:batch_size]

        params = {
            "battles_per_player": battles_per_player,
            "opponent_expansion_rounds": opponent_expansion_rounds,
            "batch_size": batch_size if batch_size and batch_size > 0 else None,
            "sync_ranked_battles_only": settings.sync_ranked_battles_only,
            "leaderboard_top_n": settings.leaderboard_top_n,
            "seed_player_count": len(seed_players),
        }

        tracker = OperationRunTracker(session, "battlelog", params)
        await tracker.start()
        await session.commit()

        stats = _SyncStats()
        processed_tags: set[str] = set()
        current_frontier = [player.tag for player in seed_players]

        try:
            for round_index in range(opponent_expansion_rounds + 1):
                next_frontier: set[str] = set()
                is_expansion_round = round_index > 0

                for player_tag in current_frontier:
                    if player_tag in processed_tags:
                        continue

                    player_result = await self._sync_player_battlelog(
                        session,
                        player_tag=player_tag,
                        battles_per_player=battles_per_player,
                        now=now,
                        stats=stats,
                        is_expansion_player=is_expansion_round,
                    )
                    processed_tags.add(player_tag)
                    next_frontier.update(player_result.opponent_tags)

                    await tracker.maybe_update_progress(
                        {
                            "round": round_index,
                            "round_type": "expansion" if is_expansion_round else "seed",
                            "players_processed": stats.players_processed,
                            "battles_created": stats.battles_created,
                            "battles_skipped": stats.battles_skipped,
                            "deck_cards_created": stats.deck_cards_created,
                            "opponents_discovered": stats.opponents_discovered,
                            "current_player_tag": player_tag,
                        },
                        commit=True,
                    )

                if round_index >= opponent_expansion_rounds:
                    break

                current_frontier = sorted(next_frontier - processed_tags)
                logger.info(
                    "Battlelog expansion round %d complete: next_frontier=%d",
                    round_index + 1,
                    len(current_frontier),
                )
                await tracker.maybe_update_progress(
                    {
                        "round": round_index,
                        "round_complete": True,
                        "next_frontier_size": len(current_frontier),
                        "players_processed": stats.players_processed,
                        "battles_created": stats.battles_created,
                        "battles_skipped": stats.battles_skipped,
                        "opponents_discovered": stats.opponents_discovered,
                    },
                    force=True,
                    commit=True,
                )

            result = {
                "players_processed": stats.players_processed,
                "battles_created": stats.battles_created,
                "battles_skipped": stats.battles_skipped,
                "deck_cards_created": stats.deck_cards_created,
                "total_tracked": len(seed_players),
                "opponents_discovered": stats.opponents_discovered,
                "expansion_rounds_run": opponent_expansion_rounds,
                "battles_per_player": battles_per_player,
            }
            await tracker.finish("success", result, commit=True)

            logger.info(
                "Battlelog sync complete: players=%d battles_created=%d skipped=%d deck_cards=%d opponents=%d",
                stats.players_processed,
                stats.battles_created,
                stats.battles_skipped,
                stats.deck_cards_created,
                stats.opponents_discovered,
            )

            return BattlelogSyncResult(
                operation_run_id=tracker.run_id,
                players_processed=stats.players_processed,
                battles_created=stats.battles_created,
                battles_skipped=stats.battles_skipped,
                deck_cards_created=stats.deck_cards_created,
                total_tracked=len(seed_players),
                opponents_discovered=stats.opponents_discovered,
                expansion_rounds_run=opponent_expansion_rounds,
                battles_per_player=battles_per_player,
            )
        except Exception as exc:
            logger.exception("Battlelog sync failed")
            await session.rollback()
            await tracker.fail(str(exc), commit=True)
            raise

    async def _sync_player_battlelog(
        self,
        session: AsyncSession,
        *,
        player_tag: str,
        battles_per_player: int,
        now: datetime,
        stats: _SyncStats,
        is_expansion_player: bool,
    ) -> _PlayerSyncResult:
        result = _PlayerSyncResult()
        api_battles = await self.client.get_player_battlelog(player_tag)
        stats.players_processed += 1

        ranked_entries: list[dict] = []
        for api_entry in api_battles:
            if should_include_battle(api_entry, settings.sync_ranked_battles_only):
                ranked_entries.append(api_entry)
            if len(ranked_entries) >= battles_per_player:
                break

        player = await session.get(Player, player_tag)
        if player is None:
            created = await self._upsert_expansion_player(session, player_tag, profile={}, now=now)
            if created and is_expansion_player:
                stats.opponents_discovered += 1
        elif is_expansion_player and not player.leaderboard_seeded:
            pass

        for api_entry in ranked_entries:
            mapped = map_battle_entry(api_entry)
            if mapped is None:
                continue

            profiles = extract_participant_profiles(api_entry)
            for tag, profile in profiles.items():
                if tag == player_tag:
                    continue
                result.opponent_tags.add(tag)
                if tag != player_tag:
                    created = await self._upsert_expansion_player(session, tag, profile=profile, now=now)
                    if created:
                        stats.opponents_discovered += 1

            created_battle = await self._persist_battle(session, mapped, now=now, stats=stats)
            if created_battle:
                stats.battles_created += 1

        player = await session.get(Player, player_tag)
        if player is not None:
            player.last_battlelog_sync_at = now
            player.updated_at = now

        return result

    async def _upsert_expansion_player(
        self,
        session: AsyncSession,
        tag: str,
        *,
        profile: dict,
        now: datetime,
    ) -> bool:
        existing = await session.get(Player, tag)
        if existing is not None:
            if profile.get("name"):
                existing.name = profile["name"]
            if profile.get("latest_elo_rating") is not None:
                existing.latest_elo_rating = profile["latest_elo_rating"]
            existing.updated_at = now
            return False

        session.add(
            Player(
                tag=tag,
                name=profile.get("name"),
                latest_elo_rating=profile.get("latest_elo_rating"),
                is_tracked=False,
                leaderboard_seeded=False,
                off_leaderboard_count=0,
                first_seen_at=now,
                updated_at=now,
            )
        )
        return True

    async def _persist_battle(
        self,
        session: AsyncSession,
        mapped: dict,
        *,
        now: datetime,
        stats: _SyncStats,
    ) -> bool:
        existing = await session.execute(select(Battle.id).where(Battle.battle_key == mapped["battle_key"]))
        if existing.scalar_one_or_none() is not None:
            stats.battles_skipped += 1
            return False

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
            raw_tower_id = participant.get("tower_card_id")
            tower_card_id: int | None = None
            if raw_tower_id is not None:
                if raw_tower_id in KNOWN_TOWER_TROOP_IDS:
                    tower_card_id = raw_tower_id
                else:
                    logger.warning(
                        "Unknown tower troop id %s for player %s in battle %s",
                        raw_tower_id,
                        participant["player_tag"],
                        mapped["battle_key"],
                    )

            session.add(
                BattleParticipant(
                    battle_id=battle.id,
                    player_tag=participant["player_tag"],
                    side=participant["side"],
                    starting_trophies=participant["starting_trophies"],
                    trophy_change=participant["trophy_change"],
                    crowns=participant["crowns"],
                    won=participant["won"],
                    tower_card_id=tower_card_id,
                )
            )
            for slot, card in enumerate(participant["cards"]):
                played_variant = infer_played_variant(card.get("evolutionLevel"))
                session.add(
                    BattleDeckCard(
                        battle_id=battle.id,
                        player_tag=participant["player_tag"],
                        slot=slot,
                        card_id=card["id"],
                        played_variant=played_variant,
                    )
                )
                stats.deck_cards_created += 1

        return True
