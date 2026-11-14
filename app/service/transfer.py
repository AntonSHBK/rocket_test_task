import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    Inventory,
    Product,
    StockEvent,
    StockEventType,
    Transfer,
    TransferStatus,
    Warehouse,
)
from app.schemas.product import ProductResponse
from app.schemas.transfer import (
    TransferCreate,
    TransferResponse,
    TransferWarehouseResponse,
)
from app.service.inventory import ensure_available_stock
from app.utils.exceptions import (
    IdempotencyConflictError,
    InvalidTransferStateError,
    ProductNotFoundError,
    TransferNotFoundError,
    WarehouseInactiveError,
    WarehouseNotFoundError,
)

logger = logging.getLogger("api")


def build_transfer_response(
    transfer: Transfer,
    product: Product,
    source_warehouse: Warehouse,
    destination_warehouse: Warehouse,
) -> TransferResponse:
    return TransferResponse(
        id=transfer.id,
        idempotency_key=transfer.idempotency_key,
        product=ProductResponse.model_validate(product),
        source_warehouse=TransferWarehouseResponse(
            id=source_warehouse.id,
            name=source_warehouse.name,
            is_active=source_warehouse.is_active,
        ),
        destination_warehouse=TransferWarehouseResponse(
            id=destination_warehouse.id,
            name=destination_warehouse.name,
            is_active=destination_warehouse.is_active,
        ),
        quantity=transfer.quantity,
        status=transfer.status,
        shipped_at=transfer.shipped_at,
        received_at=transfer.received_at,
        created_at=transfer.created_at,
    )


def mark_transfer_shipped(
    transfer: Transfer,
    shipped_at: datetime | None = None,
) -> bool:
    if transfer.status != TransferStatus.CREATED:
        return False

    transfer.status = TransferStatus.IN_TRANSIT
    transfer.shipped_at = shipped_at or datetime.now(UTC)
    return True


def mark_transfer_received(
    transfer: Transfer,
    received_at: datetime | None = None,
) -> bool:
    if transfer.status == TransferStatus.RECEIVED:
        return False
    if transfer.status != TransferStatus.IN_TRANSIT:
        raise InvalidTransferStateError(
            current_status=transfer.status.value,
            expected_status=TransferStatus.IN_TRANSIT.value,
        )

    transfer.status = TransferStatus.RECEIVED
    transfer.received_at = received_at or datetime.now(UTC)
    return True


def _validate_existing_transfer(
    transfer: Transfer,
    data: TransferCreate,
    product: Product,
) -> None:
    if (
        transfer.product_id != product.id
        or product.sku != data.sku
        or transfer.source_warehouse_id != data.source_warehouse_id
        or transfer.destination_warehouse_id != data.destination_warehouse_id
        or transfer.quantity != data.quantity
    ):
        raise IdempotencyConflictError()


async def _get_transfer_context(
    session: AsyncSession,
    transfer: Transfer,
) -> tuple[Product, Warehouse, Warehouse]:
    product = await session.scalar(select(Product).where(Product.id == transfer.product_id))
    warehouses = list(
        (
            await session.scalars(
                select(Warehouse).where(
                    Warehouse.id.in_(
                        [
                            transfer.source_warehouse_id,
                            transfer.destination_warehouse_id,
                        ]
                    )
                )
            )
        ).all()
    )
    warehouses_by_id = {warehouse.id: warehouse for warehouse in warehouses}
    if product is None:
        raise ProductNotFoundError(str(transfer.product_id))
    if transfer.source_warehouse_id not in warehouses_by_id:
        raise WarehouseNotFoundError(transfer.source_warehouse_id)
    if transfer.destination_warehouse_id not in warehouses_by_id:
        raise WarehouseNotFoundError(transfer.destination_warehouse_id)
    return (
        product,
        warehouses_by_id[transfer.source_warehouse_id],
        warehouses_by_id[transfer.destination_warehouse_id],
    )


async def list_transfers(session: AsyncSession) -> list[TransferResponse]:
    source_warehouse = aliased(Warehouse)
    destination_warehouse = aliased(Warehouse)
    rows = (
        await session.execute(
            select(Transfer, Product, source_warehouse, destination_warehouse)
            .join(Product, Product.id == Transfer.product_id)
            .join(
                source_warehouse,
                source_warehouse.id == Transfer.source_warehouse_id,
            )
            .join(
                destination_warehouse,
                destination_warehouse.id == Transfer.destination_warehouse_id,
            )
            .order_by(Transfer.id.desc())
        )
    ).all()
    return [
        build_transfer_response(transfer, product, source, destination)
        for transfer, product, source, destination in rows
    ]


async def _create_transfer(
    session: AsyncSession,
    data: TransferCreate,
) -> TransferResponse:
    async with session.begin():
        existing_transfer = await session.scalar(
            select(Transfer).where(Transfer.idempotency_key == data.idempotency_key)
        )
        if existing_transfer is not None:
            product, source, destination = await _get_transfer_context(
                session,
                existing_transfer,
            )
            _validate_existing_transfer(existing_transfer, data, product)
            return build_transfer_response(
                existing_transfer,
                product,
                source,
                destination,
            )

        product = await session.scalar(select(Product).where(Product.sku == data.sku))
        if product is None:
            raise ProductNotFoundError(data.sku)

        source = await session.scalar(
            select(Warehouse).where(Warehouse.id == data.source_warehouse_id)
        )
        destination = await session.scalar(
            select(Warehouse).where(Warehouse.id == data.destination_warehouse_id)
        )
        if source is None:
            raise WarehouseNotFoundError(data.source_warehouse_id)
        if destination is None:
            raise WarehouseNotFoundError(data.destination_warehouse_id)
        if not source.is_active:
            raise WarehouseInactiveError(source.id)
        if not destination.is_active:
            raise WarehouseInactiveError(destination.id)

        await ensure_available_stock(
            session=session,
            product_id=product.id,
            warehouse_id=source.id,
            quantity=data.quantity,
        )

        transfer_id = await session.scalar(
            insert(Transfer)
            .values(
                idempotency_key=data.idempotency_key,
                product_id=product.id,
                source_warehouse_id=source.id,
                destination_warehouse_id=destination.id,
                quantity=data.quantity,
                status=TransferStatus.CREATED,
            )
            .on_conflict_do_nothing(index_elements=[Transfer.idempotency_key])
            .returning(Transfer.id)
        )
        if transfer_id is None:
            transfer = await session.scalar(
                select(Transfer).where(
                    Transfer.idempotency_key == data.idempotency_key
                )
            )
            if transfer is None:
                raise RuntimeError("Existing transfer was not found")
            _validate_existing_transfer(transfer, data, product)
        else:
            transfer = await session.scalar(
                select(Transfer).where(Transfer.id == transfer_id)
            )
            if transfer is None:
                raise RuntimeError("Created transfer was not found")

        return build_transfer_response(transfer, product, source, destination)


async def create_transfer(
    session: AsyncSession,
    data: TransferCreate,
) -> TransferResponse:
    response = await _create_transfer(session, data)
    logger.info(
        "Transfer processed: transfer_id=%s sku=%s quantity=%s source_id=%s "
        "source=%s destination_id=%s destination=%s status=%s",
        response.id,
        response.product.sku,
        response.quantity,
        response.source_warehouse.id,
        response.source_warehouse.name,
        response.destination_warehouse.id,
        response.destination_warehouse.name,
        response.status.value,
    )
    return response


async def _ship_transfer(
    session: AsyncSession,
    transfer_id: int,
) -> TransferResponse:
    async with session.begin():
        transfer = await session.scalar(
            select(Transfer)
            .where(Transfer.id == transfer_id)
            .with_for_update()
        )
        if transfer is None:
            raise TransferNotFoundError(transfer_id)

        product, source, destination = await _get_transfer_context(session, transfer)
        if transfer.status != TransferStatus.CREATED:
            return build_transfer_response(transfer, product, source, destination)

        source_inventory = await ensure_available_stock(
            session=session,
            product_id=transfer.product_id,
            warehouse_id=transfer.source_warehouse_id,
            quantity=transfer.quantity,
            lock=True,
        )
        source_inventory.physical_quantity -= transfer.quantity
        mark_transfer_shipped(transfer)
        session.add(
            StockEvent(
                event_type=StockEventType.TRANSFER_SHIPPED,
                product_id=transfer.product_id,
                product_sku=product.sku,
                quantity=transfer.quantity,
                source_warehouse_id=transfer.source_warehouse_id,
                destination_warehouse_id=transfer.destination_warehouse_id,
                source_label=source.name,
                destination_label=destination.name,
                reference_type="transfer",
                reference_id=transfer.id,
                idempotency_key=f"transfer:{transfer.id}:ship",
            )
        )
        await session.flush()
        return build_transfer_response(transfer, product, source, destination)


async def ship_transfer(
    session: AsyncSession,
    transfer_id: int,
) -> TransferResponse:
    response = await _ship_transfer(session, transfer_id)
    logger.info(
        "Transfer shipment processed: transfer_id=%s sku=%s quantity=%s "
        "source_id=%s source=%s destination_id=%s destination=%s status=%s",
        response.id,
        response.product.sku,
        response.quantity,
        response.source_warehouse.id,
        response.source_warehouse.name,
        response.destination_warehouse.id,
        response.destination_warehouse.name,
        response.status.value,
    )
    return response


async def _receive_transfer(
    session: AsyncSession,
    transfer_id: int,
) -> TransferResponse:
    async with session.begin():
        transfer = await session.scalar(
            select(Transfer)
            .where(Transfer.id == transfer_id)
            .with_for_update()
        )
        if transfer is None:
            raise TransferNotFoundError(transfer_id)

        product, source, destination = await _get_transfer_context(session, transfer)
        if transfer.status not in (
            TransferStatus.IN_TRANSIT,
            TransferStatus.RECEIVED,
        ):
            logger.warning(
                "Invalid transfer receipt: transfer_id=%s sku=%s quantity=%s "
                "source_id=%s destination_id=%s status=%s",
                transfer.id,
                product.sku,
                transfer.quantity,
                source.id,
                destination.id,
                transfer.status.value,
            )
        if not mark_transfer_received(transfer):
            return build_transfer_response(transfer, product, source, destination)

        await session.execute(
            insert(Inventory)
            .values(
                product_id=transfer.product_id,
                warehouse_id=transfer.destination_warehouse_id,
                physical_quantity=0,
                reserved_quantity=0,
            )
            .on_conflict_do_nothing(
                index_elements=[Inventory.product_id, Inventory.warehouse_id]
            )
        )
        destination_inventory = await session.scalar(
            select(Inventory)
            .where(
                Inventory.product_id == transfer.product_id,
                Inventory.warehouse_id == transfer.destination_warehouse_id,
            )
            .with_for_update()
        )
        if destination_inventory is None:
            raise RuntimeError("Destination inventory row was not created")

        destination_inventory.physical_quantity += transfer.quantity
        session.add(
            StockEvent(
                event_type=StockEventType.TRANSFER_RECEIVED,
                product_id=transfer.product_id,
                product_sku=product.sku,
                quantity=transfer.quantity,
                source_warehouse_id=transfer.source_warehouse_id,
                destination_warehouse_id=transfer.destination_warehouse_id,
                source_label=source.name,
                destination_label=destination.name,
                reference_type="transfer",
                reference_id=transfer.id,
                idempotency_key=f"transfer:{transfer.id}:receive",
            )
        )
        await session.flush()
        return build_transfer_response(transfer, product, source, destination)


async def receive_transfer(
    session: AsyncSession,
    transfer_id: int,
) -> TransferResponse:
    response = await _receive_transfer(session, transfer_id)
    logger.info(
        "Transfer receipt processed: transfer_id=%s sku=%s quantity=%s "
        "source_id=%s source=%s destination_id=%s destination=%s status=%s",
        response.id,
        response.product.sku,
        response.quantity,
        response.source_warehouse.id,
        response.source_warehouse.name,
        response.destination_warehouse.id,
        response.destination_warehouse.name,
        response.status.value,
    )
    return response
