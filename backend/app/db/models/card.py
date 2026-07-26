from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.db.models.base import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    elixir_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_evolution_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_evolution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_hero: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    card_type: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    changelog_entries: Mapped[list["CardChangelog"]] = relationship(back_populates="card")

    __table_args__ = (
        Index("idx_cards_elixir", "elixir_cost"),
        Index("idx_cards_type", "card_type"),
    )


class CardChangelog(Base):
    __tablename__ = "card_changelog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cards.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    field_name: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    card: Mapped["Card"] = relationship(back_populates="changelog_entries")

    __table_args__ = (Index("idx_changelog_card", "card_id", changed_at.desc()),)
