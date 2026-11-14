from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.inventory import Inventory
    from app.models.reservation import FBSReservation
    from app.models.shipment import Shipment
    from app.models.stock_event import StockEvent
    from app.models.transfer import Transfer


class Warehouse(TimestampMixin, Base):
    __tablename__ = "warehouses"
    __table_args__ = (
        CheckConstraint(
            "(is_active AND archived_at IS NULL) OR "
            "(NOT is_active AND archived_at IS NOT NULL)",
            name="archive_state_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    inventories: Mapped[list["Inventory"]] = relationship(back_populates="warehouse")
    reservations: Mapped[list["FBSReservation"]] = relationship(back_populates="warehouse")
    source_transfers: Mapped[list["Transfer"]] = relationship(
        back_populates="source_warehouse",
        foreign_keys="Transfer.source_warehouse_id",
    )
    destination_transfers: Mapped[list["Transfer"]] = relationship(
        back_populates="destination_warehouse",
        foreign_keys="Transfer.destination_warehouse_id",
    )
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="source_warehouse")
    outgoing_stock_events: Mapped[list["StockEvent"]] = relationship(
        back_populates="source_warehouse",
        foreign_keys="StockEvent.source_warehouse_id",
    )
    incoming_stock_events: Mapped[list["StockEvent"]] = relationship(
        back_populates="destination_warehouse",
        foreign_keys="StockEvent.destination_warehouse_id",
    )
