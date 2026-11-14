from datetime import datetime

from pydantic import BaseModel, Field

from app.models import ReservationStatus
from app.schemas.product import ProductResponse


class FBSReservationCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    warehouse_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    order_reference: str | None = Field(default=None, min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)


class FBSWarehouseResponse(BaseModel):
    id: int
    name: str
    is_active: bool


class FBSReservationResponse(BaseModel):
    id: int
    idempotency_key: str
    order_reference: str | None
    product: ProductResponse
    warehouse: FBSWarehouseResponse
    quantity: int
    status: ReservationStatus
    shipment_id: int | None
    cancelled_at: datetime | None
    shipped_at: datetime | None
    created_at: datetime
