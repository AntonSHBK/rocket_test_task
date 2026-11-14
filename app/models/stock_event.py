from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import StockEventType

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.warehouse import Warehouse


class StockEvent(Base):
    __tablename__ = "stock_events"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        Index("ix_stock_events_reference", "reference_type", "reference_id"),
        Index("ix_stock_events_product_created", "product_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[StockEventType] = mapped_column(
        Enum(
            StockEventType,
            name="stock_event_type",
            native_enum=False,
            create_constraint=True,
            length=64,
        ),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_sku: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    source_warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
    )
    destination_warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
    )
    source_label: Mapped[str | None] = mapped_column(String(255))
    destination_label: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(String(500))
    reference_type: Mapped[str | None] = mapped_column(String(64))
    reference_id: Mapped[int | None]
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    product: Mapped["Product"] = relationship(back_populates="stock_events")
    source_warehouse: Mapped["Warehouse | None"] = relationship(
        back_populates="outgoing_stock_events",
        foreign_keys=[source_warehouse_id],
    )
    destination_warehouse: Mapped["Warehouse | None"] = relationship(
        back_populates="incoming_stock_events",
        foreign_keys=[destination_warehouse_id],
    )
