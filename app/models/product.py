from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.inventory import Inventory
    from app.models.reservation import FBSReservation
    from app.models.shipment import Shipment
    from app.models.stock_event import StockEvent
    from app.models.transfer import Transfer


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    inventories: Mapped[list["Inventory"]] = relationship(back_populates="product")
    reservations: Mapped[list["FBSReservation"]] = relationship(back_populates="product")
    transfers: Mapped[list["Transfer"]] = relationship(back_populates="product")
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="product")
    stock_events: Mapped[list["StockEvent"]] = relationship(back_populates="product")
