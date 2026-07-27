from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class CardGameplayProfile(Base):
    __tablename__ = "card_gameplay_profiles"

    card_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cards.id"), primary_key=True)
    variant: Mapped[str] = mapped_column(String(16), primary_key=True)
    is_core: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    related_card_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("cards.id"), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    card: Mapped["Card"] = relationship(
        back_populates="gameplay_profiles",
        foreign_keys=[card_id],
    )

    __table_args__ = (
        Index("idx_cgp_is_core", "is_core"),
        Index("idx_cgp_related_card", "related_card_id"),
    )
