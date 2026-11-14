import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Product, StockEvent, StockEventType, Warehouse
from app.schemas.history import StockEventResponse

logger = logging.getLogger("api")


def build_stock_event_response(
    event: StockEvent,
    product: Product,
    source_warehouse: Warehouse | None,
    destination_warehouse: Warehouse | None,
) -> StockEventResponse:
    return StockEventResponse(
        id=event.id,
        event_type=event.event_type,
        sku=event.product_sku or product.sku,
        product_name=product.name,
        quantity=event.quantity,
        source_warehouse_id=event.source_warehouse_id,
        destination_warehouse_id=event.destination_warehouse_id,
        source=event.source_label or (
            source_warehouse.name if source_warehouse else None
        ),
        destination=event.destination_label or (
            destination_warehouse.name if destination_warehouse else None
        ),
        reason=event.reason,
        reference_type=event.reference_type,
        reference_id=event.reference_id,
        created_at=event.created_at,
    )


async def list_stock_events(
    session: AsyncSession,
    event_type: StockEventType | None = None,
    sku: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StockEventResponse]:
    source_warehouse = aliased(Warehouse)
    destination_warehouse = aliased(Warehouse)
    query = (
        select(StockEvent, Product, source_warehouse, destination_warehouse)
        .join(Product, Product.id == StockEvent.product_id)
        .outerjoin(
            source_warehouse,
            source_warehouse.id == StockEvent.source_warehouse_id,
        )
        .outerjoin(
            destination_warehouse,
            destination_warehouse.id == StockEvent.destination_warehouse_id,
        )
        .order_by(StockEvent.created_at.desc(), StockEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if event_type is not None:
        query = query.where(StockEvent.event_type == event_type)
    if sku is not None:
        query = query.where(Product.sku == sku)

    rows = (await session.execute(query)).all()
    return [
        build_stock_event_response(
            event,
            product,
            source,
            destination,
        )
        for event, product, source, destination in rows
    ]
