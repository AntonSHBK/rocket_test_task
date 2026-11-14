from pydantic import BaseModel, Field, field_validator

from app.schemas.inventory import WarehouseStockResponse
from app.schemas.product import ProductResponse


class WriteOffCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    warehouse_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Write-off reason must not be empty")
        return normalized


class WriteOffResponse(BaseModel):
    event_id: int
    idempotency_key: str
    created: bool
    product: ProductResponse
    stock: WarehouseStockResponse
    written_off_quantity: int
    reason: str
