from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ShipmentStatus, ShipmentType

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.reservation import FBSReservation
    from app.models.warehouse import Warehouse


class Shipment(TimestampMixin, Base):
    __tablename__ = "shipments"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "(shipment_type = 'FBS' AND reservation_id IS NOT NULL) OR "
            "(shipment_type = 'FBO' AND reservation_id IS NULL)",
            name="reservation_matches_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
    )
    shipment_type: Mapped[ShipmentType] = mapped_column(
        Enum(
            ShipmentType,
            name="shipment_type",
            native_enum=False,
            create_constraint=True,
            length=16,
        ),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reservation_id: Mapped[int | None] = mapped_column(
        ForeignKey("fbs_reservations.id", ondelete="RESTRICT"),
        unique=True,
    )
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(
            ShipmentStatus,
            name="shipment_status",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
        default=ShipmentStatus.CREATED,
    )
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped["Product"] = relationship(back_populates="shipments")
    source_warehouse: Mapped["Warehouse"] = relationship(back_populates="shipments")
    reservation: Mapped["FBSReservation | None"] = relationship(
        back_populates="shipment"
    )
