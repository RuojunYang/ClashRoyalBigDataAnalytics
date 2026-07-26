from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class LeaderboardSnapshot(Base):
    __tablename__ = "leaderboard_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="global_pol")
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    top_n: Mapped[int] = mapped_column(Integer, nullable=False)
    entries_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")

    entries: Mapped[list["LeaderboardEntry"]] = relationship(back_populates="snapshot")


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, ForeignKey("leaderboard_snapshots.id"), nullable=False)
    player_tag: Mapped[str] = mapped_column(String(16), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    elo_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exp_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clan_tag: Mapped[str | None] = mapped_column(String(16), nullable=True)
    clan_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    snapshot: Mapped["LeaderboardSnapshot"] = relationship(back_populates="entries")

    __table_args__ = (
        UniqueConstraint("snapshot_id", "player_tag", name="uq_leaderboard_entry_snapshot_player"),
        Index("idx_le_snapshot_rank", "snapshot_id", "rank"),
        Index("idx_le_player_tag", "player_tag"),
    )
