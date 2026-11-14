from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models import TransferStatus
from app.schemas.product import ProductResponse


class TransferCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    source_warehouse_id: int = Field(gt=0)
    destination_warehouse_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_warehouses(self) -> "TransferCreate":
        if self.source_warehouse_id == self.destination_warehouse_id:
            raise ValueError("Source and destination warehouses must be different")
        return self


class TransferWarehouseResponse(BaseModel):
    id: int
    name: str
    is_active: bool


class TransferResponse(BaseModel):
    id: int
    idempotency_key: str
    product: ProductResponse
    source_warehouse: TransferWarehouseResponse
    destination_warehouse: TransferWarehouseResponse
    quantity: int
    status: TransferStatus
    shipped_at: datetime | None
    received_at: datetime | None
    created_at: datetime
