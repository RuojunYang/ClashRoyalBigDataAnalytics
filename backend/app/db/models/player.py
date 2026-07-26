from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class Player(Base):
    __tablename__ = "players"

    tag: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_elo_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exp_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clan_tag: Mapped[str | None] = mapped_column(String(16), nullable=True)
    clan_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    off_leaderboard_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_leaderboard_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_battlelog_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
