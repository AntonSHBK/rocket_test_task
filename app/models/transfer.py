from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import TransferStatus

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.warehouse import Warehouse


class Transfer(TimestampMixin, Base):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "source_warehouse_id <> destination_warehouse_id",
            name="different_warehouses",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
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
    destination_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[TransferStatus] = mapped_column(
        Enum(
            TransferStatus,
            name="transfer_status",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
        default=TransferStatus.CREATED,
    )
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped["Product"] = relationship(back_populates="transfers")
    source_warehouse: Mapped["Warehouse"] = relationship(
        back_populates="source_transfers",
        foreign_keys=[source_warehouse_id],
    )
    destination_warehouse: Mapped["Warehouse"] = relationship(
        back_populates="destination_transfers",
        foreign_keys=[destination_warehouse_id],
    )
