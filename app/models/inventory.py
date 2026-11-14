from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.warehouse import Warehouse


class Inventory(TimestampMixin, Base):
    __tablename__ = "inventories"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "warehouse_id",
            name="uq_inventories_product_warehouse",
        ),
        CheckConstraint(
            "physical_quantity >= 0",
            name="physical_quantity_non_negative",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="reserved_quantity_non_negative",
        ),
        CheckConstraint(
            "reserved_quantity <= physical_quantity",
            name="reserved_not_above_physical",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
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
    physical_quantity: Mapped[int] = mapped_column(nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(nullable=False, default=0)

    product: Mapped["Product"] = relationship(back_populates="inventories")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="inventories")

    @property
    def available_quantity(self) -> int:
        return self.physical_quantity - self.reserved_quantity
