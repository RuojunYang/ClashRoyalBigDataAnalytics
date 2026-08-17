from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base

if TYPE_CHECKING:
    from app.db.models.battle import BattleParticipant


class TowerTroop(Base):
    __tablename__ = "tower_troops"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    participants: Mapped[list["BattleParticipant"]] = relationship(back_populates="tower_troop")
