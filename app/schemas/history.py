from datetime import datetime

from pydantic import BaseModel

from app.models import StockEventType


class StockEventResponse(BaseModel):
    id: int
    event_type: StockEventType
    sku: str
    product_name: str
    quantity: int
    source_warehouse_id: int | None
    destination_warehouse_id: int | None
    source: str | None
    destination: str | None
    reason: str | None
    reference_type: str | None
    reference_id: int | None
    created_at: datetime
