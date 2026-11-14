from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ReservationStatus

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.shipment import Shipment
    from app.models.warehouse import Warehouse


class FBSReservation(TimestampMixin, Base):
    __tablename__ = "fbs_reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
    )
    order_reference: Mapped[str | None] = mapped_column(String(128), index=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(
            ReservationStatus,
            name="reservation_status",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
        default=ReservationStatus.RESERVED,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped["Product"] = relationship(back_populates="reservations")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="reservations")
    shipment: Mapped["Shipment | None"] = relationship(back_populates="reservation")
