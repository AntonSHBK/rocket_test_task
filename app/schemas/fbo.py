from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models import ShipmentStatus
from app.schemas.product import ProductResponse


class FBOShipmentCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    source_warehouse_id: int = Field(gt=0)
    destination: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("destination")
    @classmethod
    def normalize_destination(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Destination must not be empty")
        return normalized


class FBOWarehouseResponse(BaseModel):
    id: int
    name: str
    is_active: bool


class FBOShipmentResponse(BaseModel):
    id: int
    idempotency_key: str
    product: ProductResponse
    source_warehouse: FBOWarehouseResponse
    destination: str
    quantity: int
    status: ShipmentStatus
    shipped_at: datetime | None
    received_at: datetime | None
    created_at: datetime
