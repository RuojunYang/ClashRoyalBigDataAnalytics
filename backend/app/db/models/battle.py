from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class Battle(Base):
    __tablename__ = "battles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    battle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    battle_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    game_mode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    game_mode_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    arena_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    arena_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    league_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    battle_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    participants: Mapped[list["BattleParticipant"]] = relationship(back_populates="battle")
    deck_cards: Mapped[list["BattleDeckCard"]] = relationship(back_populates="battle")


class BattleParticipant(Base):
    __tablename__ = "battle_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    battle_id: Mapped[int] = mapped_column(Integer, ForeignKey("battles.id"), nullable=False)
    player_tag: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    starting_trophies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trophy_change: Mapped[int | None] = mapped_column(Integer, nullable=True)
    crowns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    battle: Mapped["Battle"] = relationship(back_populates="participants")

    __table_args__ = (Index("idx_bp_battle", "battle_id"), Index("idx_bp_player", "player_tag"),)


class BattleDeckCard(Base):
    __tablename__ = "battle_deck_cards"

    battle_id: Mapped[int] = mapped_column(Integer, ForeignKey("battles.id"), primary_key=True)
    player_tag: Mapped[str] = mapped_column(String(16), primary_key=True)
    slot: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    card_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cards.id"), nullable=False)
    card_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    played_variant: Mapped[str] = mapped_column(String(16), nullable=False, default="base")

    battle: Mapped["Battle"] = relationship(back_populates="deck_cards")

    __table_args__ = (
        Index("idx_bdc_card", "card_id"),
        Index("idx_bdc_played_variant", "played_variant"),
    )
