import logging
from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Inventory,
    Product,
    Shipment,
    ShipmentStatus,
    ShipmentType,
    StockEvent,
    StockEventType,
    Transfer,
    TransferStatus,
    Warehouse,
)
from app.schemas.inventory import (
    InTransitStockResponse,
    ProductInventoryResponse,
    ReceiptCreate,
    ReceiptResponse,
    StockTotalsResponse,
    WarehouseStockResponse,
)
from app.schemas.product import ProductResponse
from app.utils.exceptions import (
    IdempotencyConflictError,
    InsufficientStockError,
    ProductNotFoundError,
    WarehouseInactiveError,
    WarehouseNotFoundError,
)

logger = logging.getLogger("api")


async def list_products(session: AsyncSession) -> list[Product]:
    result = await session.scalars(select(Product).order_by(Product.sku))
    return list(result.all())


def build_inventory_snapshot(
    products: Sequence[Product],
    warehouses: Sequence[Warehouse],
    inventories: Sequence[Inventory],
    transfer_totals: dict[int, int],
    shipment_totals: dict[tuple[int, ShipmentType], int],
) -> list[ProductInventoryResponse]:
    inventory_by_location = {
        (inventory.product_id, inventory.warehouse_id): inventory
        for inventory in inventories
    }
    snapshot: list[ProductInventoryResponse] = []

    for product in products:
        warehouse_stocks: list[WarehouseStockResponse] = []
        total_physical = 0
        total_reserved = 0

        for warehouse in warehouses:
            inventory = inventory_by_location.get((product.id, warehouse.id))
            physical = inventory.physical_quantity if inventory else 0
            reserved = inventory.reserved_quantity if inventory else 0
            available = physical - reserved

            warehouse_stocks.append(
                WarehouseStockResponse(
                    warehouse_id=warehouse.id,
                    warehouse_name=warehouse.name,
                    is_active=warehouse.is_active,
                    physical=physical,
                    reserved=reserved,
                    available=available,
                )
            )
            total_physical += physical
            total_reserved += reserved

        between_warehouses = transfer_totals.get(product.id, 0)
        to_marketplace = shipment_totals.get((product.id, ShipmentType.FBO), 0)
        to_customer = shipment_totals.get((product.id, ShipmentType.FBS), 0)

        snapshot.append(
            ProductInventoryResponse(
                product=ProductResponse.model_validate(product),
                warehouses=warehouse_stocks,
                totals=StockTotalsResponse(
                    physical=total_physical,
                    reserved=total_reserved,
                    available=total_physical - total_reserved,
                ),
                in_transit=InTransitStockResponse(
                    between_warehouses=between_warehouses,
                    to_marketplace=to_marketplace,
                    to_customer=to_customer,
                    total=between_warehouses + to_marketplace + to_customer,
                ),
            )
        )

    return snapshot


async def get_inventory_snapshot(
    session: AsyncSession,
) -> list[ProductInventoryResponse]:
    products = list(
        (await session.scalars(select(Product).order_by(Product.sku))).all()
    )
    warehouses = list(
        (await session.scalars(select(Warehouse).order_by(Warehouse.id))).all()
    )
    inventories = list((await session.scalars(select(Inventory))).all())

    transfer_rows = (
        await session.execute(
            select(Transfer.product_id, func.sum(Transfer.quantity))
            .where(Transfer.status == TransferStatus.IN_TRANSIT)
            .group_by(Transfer.product_id)
        )
    ).all()
    shipment_rows = (
        await session.execute(
            select(
                Shipment.product_id,
                Shipment.shipment_type,
                func.sum(Shipment.quantity),
            )
            .where(Shipment.status == ShipmentStatus.IN_TRANSIT)
            .group_by(Shipment.product_id, Shipment.shipment_type)
        )
    ).all()

    transfer_totals = {
        product_id: int(quantity)
        for product_id, quantity in transfer_rows
    }
    shipment_totals = {
        (product_id, ShipmentType(shipment_type)): int(quantity)
        for product_id, shipment_type, quantity in shipment_rows
    }
    return build_inventory_snapshot(
        products=products,
        warehouses=warehouses,
        inventories=inventories,
        transfer_totals=transfer_totals,
        shipment_totals=shipment_totals,
    )


def validate_stock_availability(
    warehouse_name: str,
    requested: int,
    available: int,
    other_warehouses: list[dict[str, object]],
) -> None:
    if available >= requested:
        return

    raise InsufficientStockError(
        warehouse_name=warehouse_name,
        requested=requested,
        available=available,
        other_warehouses=other_warehouses,
    )


async def ensure_available_stock(
    session: AsyncSession,
    product_id: int,
    warehouse_id: int,
    quantity: int,
    lock: bool = False,
) -> Inventory:
    product = await session.scalar(
        select(Product).where(Product.id == product_id)
    )
    if product is None:
        raise ProductNotFoundError(str(product_id))

    warehouse = await session.scalar(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    )
    if warehouse is None:
        raise WarehouseNotFoundError(warehouse_id)
    if not warehouse.is_active:
        raise WarehouseInactiveError(warehouse_id)

    inventory_query = select(Inventory).where(
        Inventory.product_id == product_id,
        Inventory.warehouse_id == warehouse_id,
    )
    if lock:
        inventory_query = inventory_query.with_for_update()
    inventory = await session.scalar(inventory_query)
    available = inventory.available_quantity if inventory else 0

    alternative_rows = (
        await session.execute(
            select(
                Warehouse.id,
                Warehouse.name,
                (Inventory.physical_quantity - Inventory.reserved_quantity).label(
                    "available"
                ),
            )
            .join(Inventory, Inventory.warehouse_id == Warehouse.id)
            .where(
                Inventory.product_id == product_id,
                Warehouse.id != warehouse_id,
                Warehouse.is_active.is_(True),
                Inventory.physical_quantity - Inventory.reserved_quantity > 0,
            )
            .order_by(Warehouse.id)
        )
    ).all()
    other_warehouses = [
        {
            "warehouse_id": alternative_id,
            "name": alternative_name,
            "available": alternative_available,
        }
        for alternative_id, alternative_name, alternative_available in alternative_rows
    ]

    if available < quantity:
        logger.warning(
            "Insufficient stock: sku=%s quantity=%s warehouse_id=%s "
            "warehouse=%s available=%s",
            product.sku,
            quantity,
            warehouse.id,
            warehouse.name,
            available,
        )

    validate_stock_availability(
        warehouse_name=warehouse.name,
        requested=quantity,
        available=available,
        other_warehouses=other_warehouses,
    )
    if inventory is None:
        raise RuntimeError("Inventory must exist when stock is available")
    return inventory


def _validate_existing_receipt(
    event: StockEvent,
    product_id: int,
    warehouse_id: int,
    quantity: int,
) -> None:
    if (
        event.event_type != StockEventType.RECEIPT
        or event.product_id != product_id
        or event.destination_warehouse_id != warehouse_id
        or event.quantity != quantity
    ):
        raise IdempotencyConflictError()


async def receive_stock(
    session: AsyncSession,
    receipt: ReceiptCreate,
) -> ReceiptResponse:
    idempotency_key = receipt.idempotency_key or f"receipt:{uuid4().hex}"

    async with session.begin():
        product = await session.scalar(select(Product).where(Product.sku == receipt.sku))
        if product is None:
            raise ProductNotFoundError(receipt.sku)

        warehouse = await session.scalar(
            select(Warehouse).where(Warehouse.id == receipt.warehouse_id)
        )
        if warehouse is None:
            raise WarehouseNotFoundError(receipt.warehouse_id)
        if not warehouse.is_active:
            raise WarehouseInactiveError(receipt.warehouse_id)

        await session.execute(
            insert(Inventory)
            .values(
                product_id=product.id,
                warehouse_id=warehouse.id,
                physical_quantity=0,
                reserved_quantity=0,
            )
            .on_conflict_do_nothing(
                index_elements=[Inventory.product_id, Inventory.warehouse_id]
            )
        )
        inventory = await session.scalar(
            select(Inventory)
            .where(
                Inventory.product_id == product.id,
                Inventory.warehouse_id == warehouse.id,
            )
            .with_for_update()
        )
        if inventory is None:
            raise RuntimeError("Inventory row was not created")

        event_id = await session.scalar(
            insert(StockEvent)
            .values(
                event_type=StockEventType.RECEIPT,
                product_id=product.id,
                product_sku=product.sku,
                quantity=receipt.quantity,
                destination_warehouse_id=warehouse.id,
                source_label="Поставка",
                destination_label=warehouse.name,
                reference_type="receipt",
                idempotency_key=idempotency_key,
            )
            .on_conflict_do_nothing(index_elements=[StockEvent.idempotency_key])
            .returning(StockEvent.id)
        )

        created = event_id is not None
        if created:
            inventory.physical_quantity += receipt.quantity
            await session.flush()
        else:
            existing_event = await session.scalar(
                select(StockEvent).where(
                    StockEvent.idempotency_key == idempotency_key
                )
            )
            if existing_event is None:
                raise RuntimeError("Existing receipt event was not found")
            _validate_existing_receipt(
                event=existing_event,
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=receipt.quantity,
            )
            event_id = existing_event.id

        stock = WarehouseStockResponse(
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name,
            is_active=warehouse.is_active,
            physical=inventory.physical_quantity,
            reserved=inventory.reserved_quantity,
            available=inventory.available_quantity,
        )
        response = ReceiptResponse(
            event_id=event_id,
            idempotency_key=idempotency_key,
            created=created,
            product=ProductResponse.model_validate(product),
            stock=stock,
            received_quantity=receipt.quantity,
        )

    logger.info(
        "Stock received: event_id=%s sku=%s quantity=%s warehouse_id=%s "
        "warehouse=%s created=%s",
        response.event_id,
        response.product.sku,
        response.received_quantity,
        response.stock.warehouse_id,
        response.stock.warehouse_name,
        response.created,
    )
    return response
