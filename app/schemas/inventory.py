from pydantic import BaseModel, Field

from app.schemas.product import ProductResponse


class WarehouseStockResponse(BaseModel):
    warehouse_id: int
    warehouse_name: str
    is_active: bool
    physical: int
    reserved: int
    available: int


class StockTotalsResponse(BaseModel):
    physical: int
    reserved: int
    available: int


class InTransitStockResponse(BaseModel):
    between_warehouses: int
    to_marketplace: int
    to_customer: int
    total: int


class ProductInventoryResponse(BaseModel):
    product: ProductResponse
    warehouses: list[WarehouseStockResponse]
    totals: StockTotalsResponse
    in_transit: InTransitStockResponse


class ReceiptCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    warehouse_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class ReceiptResponse(BaseModel):
    event_id: int
    idempotency_key: str
    created: bool
    product: ProductResponse
    stock: WarehouseStockResponse
    received_quantity: int
