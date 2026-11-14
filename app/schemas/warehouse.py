from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class WarehouseName(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Warehouse name must not be empty")
        return normalized


class WarehouseCreate(WarehouseName):
    pass


class WarehouseUpdate(WarehouseName):
    pass


class WarehouseResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    archived_at: datetime | None
    physical_quantity: int
    reserved_quantity: int
    available_quantity: int
