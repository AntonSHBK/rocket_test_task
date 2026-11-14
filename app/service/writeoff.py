import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Inventory, Product, StockEvent, StockEventType, Warehouse
from app.schemas.inventory import WarehouseStockResponse
from app.schemas.product import ProductResponse
from app.schemas.writeoff import WriteOffCreate, WriteOffResponse
from app.service.inventory import ensure_available_stock
from app.utils.exceptions import (
    IdempotencyConflictError,
    ProductNotFoundError,
    WarehouseInactiveError,
    WarehouseNotFoundError,
)

logger = logging.getLogger("api")


def apply_write_off(inventory: Inventory, quantity: int) -> None:
    if quantity <= 0:
        raise ValueError("Write-off quantity must be positive")
    if quantity > inventory.available_quantity:
        raise ValueError("Write-off quantity exceeds available stock")

    inventory.physical_quantity -= quantity


def _validate_existing_write_off(
    event: StockEvent,
    data: WriteOffCreate,
) -> None:
    if (
        event.event_type != StockEventType.WRITE_OFF
        or event.product_sku != data.sku
        or event.source_warehouse_id != data.warehouse_id
        or event.quantity != data.quantity
        or event.reason != data.reason
    ):
        raise IdempotencyConflictError()


def _build_response(
    event: StockEvent,
    product: Product,
    warehouse: Warehouse,
    inventory: Inventory,
    created: bool,
) -> WriteOffResponse:
    return WriteOffResponse(
        event_id=event.id,
        idempotency_key=event.idempotency_key or "",
        created=created,
        product=ProductResponse.model_validate(product),
        stock=WarehouseStockResponse(
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name,
            is_active=warehouse.is_active,
            physical=inventory.physical_quantity,
            reserved=inventory.reserved_quantity,
            available=inventory.available_quantity,
        ),
        written_off_quantity=event.quantity,
        reason=event.reason or "",
    )


async def _get_existing_response(
    session: AsyncSession,
    event: StockEvent,
    data: WriteOffCreate,
) -> WriteOffResponse:
    _validate_existing_write_off(event, data)
    product = await session.scalar(select(Product).where(Product.id == event.product_id))
    warehouse = await session.scalar(
        select(Warehouse).where(Warehouse.id == event.source_warehouse_id)
    )
    inventory = await session.scalar(
        select(Inventory).where(
            Inventory.product_id == event.product_id,
            Inventory.warehouse_id == event.source_warehouse_id,
        )
    )
    if product is None or warehouse is None or inventory is None:
        raise RuntimeError("Existing write-off context was not found")
    return _build_response(event, product, warehouse, inventory, created=False)


async def write_off_stock(
    session: AsyncSession,
    data: WriteOffCreate,
) -> WriteOffResponse:
    async with session.begin():
        existing_event = await session.scalar(
            select(StockEvent).where(
                StockEvent.idempotency_key == data.idempotency_key
            )
        )
        if existing_event is not None:
            response = await _get_existing_response(session, existing_event, data)
        else:
            product = await session.scalar(
                select(Product).where(Product.sku == data.sku)
            )
            if product is None:
                raise ProductNotFoundError(data.sku)

            warehouse = await session.scalar(
                select(Warehouse).where(Warehouse.id == data.warehouse_id)
            )
            if warehouse is None:
                raise WarehouseNotFoundError(data.warehouse_id)
            if not warehouse.is_active:
                raise WarehouseInactiveError(data.warehouse_id)

            event_id = await session.scalar(
                insert(StockEvent)
                .values(
                    event_type=StockEventType.WRITE_OFF,
                    product_id=product.id,
                    product_sku=product.sku,
                    quantity=data.quantity,
                    source_warehouse_id=warehouse.id,
                    source_label=warehouse.name,
                    destination_label="Списание",
                    reason=data.reason,
                    reference_type="write_off",
                    idempotency_key=data.idempotency_key,
                )
                .on_conflict_do_nothing(index_elements=[StockEvent.idempotency_key])
                .returning(StockEvent.id)
            )
            if event_id is None:
                existing_event = await session.scalar(
                    select(StockEvent).where(
                        StockEvent.idempotency_key == data.idempotency_key
                    )
                )
                if existing_event is None:
                    raise RuntimeError("Existing write-off event was not found")
                response = await _get_existing_response(session, existing_event, data)
            else:
                inventory = await ensure_available_stock(
                    session=session,
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    quantity=data.quantity,
                    lock=True,
                )
                apply_write_off(inventory, data.quantity)
                await session.flush()
                event = await session.scalar(
                    select(StockEvent).where(StockEvent.id == event_id)
                )
                if event is None:
                    raise RuntimeError("Created write-off event was not found")
                response = _build_response(
                    event,
                    product,
                    warehouse,
                    inventory,
                    created=True,
                )

    logger.info(
        "Stock written off: event_id=%s sku=%s quantity=%s warehouse_id=%s "
        "warehouse=%s created=%s",
        response.event_id,
        response.product.sku,
        response.written_off_quantity,
        response.stock.warehouse_id,
        response.stock.warehouse_name,
        response.created,
    )
    return response
