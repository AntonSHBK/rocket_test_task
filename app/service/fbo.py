import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Product,
    Shipment,
    ShipmentStatus,
    ShipmentType,
    StockEvent,
    StockEventType,
    Warehouse,
)
from app.schemas.fbo import (
    FBOShipmentCreate,
    FBOShipmentResponse,
    FBOWarehouseResponse,
)
from app.schemas.product import ProductResponse
from app.service.inventory import ensure_available_stock
from app.utils.exceptions import (
    IdempotencyConflictError,
    InvalidShipmentStateError,
    ProductNotFoundError,
    ShipmentNotFoundError,
    WarehouseInactiveError,
    WarehouseNotFoundError,
)

logger = logging.getLogger("api")


def build_fbo_shipment_response(
    shipment: Shipment,
    product: Product,
    warehouse: Warehouse,
) -> FBOShipmentResponse:
    return FBOShipmentResponse(
        id=shipment.id,
        idempotency_key=shipment.idempotency_key,
        product=ProductResponse.model_validate(product),
        source_warehouse=FBOWarehouseResponse(
            id=warehouse.id,
            name=warehouse.name,
            is_active=warehouse.is_active,
        ),
        destination=shipment.destination,
        quantity=shipment.quantity,
        status=shipment.status,
        shipped_at=shipment.shipped_at,
        received_at=shipment.received_at,
        created_at=shipment.created_at,
    )


def mark_fbo_shipment_sent(
    shipment: Shipment,
    shipped_at: datetime | None = None,
) -> bool:
    if shipment.status != ShipmentStatus.CREATED:
        return False

    shipment.status = ShipmentStatus.IN_TRANSIT
    shipment.shipped_at = shipped_at or datetime.now(UTC)
    return True


def mark_fbo_shipment_received(
    shipment: Shipment,
    received_at: datetime | None = None,
) -> bool:
    if shipment.status == ShipmentStatus.RECEIVED:
        return False
    if shipment.status != ShipmentStatus.IN_TRANSIT:
        raise InvalidShipmentStateError(
            current_status=shipment.status.value,
            expected_status=ShipmentStatus.IN_TRANSIT.value,
        )

    shipment.status = ShipmentStatus.RECEIVED
    shipment.received_at = received_at or datetime.now(UTC)
    return True


def _validate_existing_fbo_shipment(
    shipment: Shipment,
    data: FBOShipmentCreate,
    product: Product,
) -> None:
    if (
        shipment.shipment_type != ShipmentType.FBO
        or shipment.product_id != product.id
        or product.sku != data.sku
        or shipment.source_warehouse_id != data.source_warehouse_id
        or shipment.destination != data.destination
        or shipment.quantity != data.quantity
    ):
        raise IdempotencyConflictError()


async def _get_fbo_context(
    session: AsyncSession,
    shipment: Shipment,
) -> tuple[Product, Warehouse]:
    product = await session.scalar(select(Product).where(Product.id == shipment.product_id))
    warehouse = await session.scalar(
        select(Warehouse).where(Warehouse.id == shipment.source_warehouse_id)
    )
    if product is None:
        raise ProductNotFoundError(str(shipment.product_id))
    if warehouse is None:
        raise WarehouseNotFoundError(shipment.source_warehouse_id)
    return product, warehouse


async def list_fbo_shipments(
    session: AsyncSession,
) -> list[FBOShipmentResponse]:
    rows = (
        await session.execute(
            select(Shipment, Product, Warehouse)
            .join(Product, Product.id == Shipment.product_id)
            .join(Warehouse, Warehouse.id == Shipment.source_warehouse_id)
            .where(Shipment.shipment_type == ShipmentType.FBO)
            .order_by(Shipment.id.desc())
        )
    ).all()
    return [
        build_fbo_shipment_response(shipment, product, warehouse)
        for shipment, product, warehouse in rows
    ]


async def _create_fbo_shipment(
    session: AsyncSession,
    data: FBOShipmentCreate,
) -> FBOShipmentResponse:
    async with session.begin():
        existing_shipment = await session.scalar(
            select(Shipment).where(Shipment.idempotency_key == data.idempotency_key)
        )
        if existing_shipment is not None:
            product, warehouse = await _get_fbo_context(session, existing_shipment)
            _validate_existing_fbo_shipment(existing_shipment, data, product)
            return build_fbo_shipment_response(
                existing_shipment,
                product,
                warehouse,
            )

        product = await session.scalar(select(Product).where(Product.sku == data.sku))
        if product is None:
            raise ProductNotFoundError(data.sku)
        warehouse = await session.scalar(
            select(Warehouse).where(Warehouse.id == data.source_warehouse_id)
        )
        if warehouse is None:
            raise WarehouseNotFoundError(data.source_warehouse_id)
        if not warehouse.is_active:
            raise WarehouseInactiveError(warehouse.id)

        await ensure_available_stock(
            session=session,
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity=data.quantity,
        )

        shipment_id = await session.scalar(
            insert(Shipment)
            .values(
                idempotency_key=data.idempotency_key,
                shipment_type=ShipmentType.FBO,
                product_id=product.id,
                source_warehouse_id=warehouse.id,
                reservation_id=None,
                destination=data.destination,
                quantity=data.quantity,
                status=ShipmentStatus.CREATED,
            )
            .on_conflict_do_nothing(index_elements=[Shipment.idempotency_key])
            .returning(Shipment.id)
        )
        if shipment_id is None:
            shipment = await session.scalar(
                select(Shipment).where(
                    Shipment.idempotency_key == data.idempotency_key
                )
            )
            if shipment is None:
                raise RuntimeError("Existing FBO shipment was not found")
            product, warehouse = await _get_fbo_context(session, shipment)
            _validate_existing_fbo_shipment(shipment, data, product)
        else:
            shipment = await session.scalar(
                select(Shipment).where(Shipment.id == shipment_id)
            )
            if shipment is None:
                raise RuntimeError("Created FBO shipment was not found")

        return build_fbo_shipment_response(shipment, product, warehouse)


async def create_fbo_shipment(
    session: AsyncSession,
    data: FBOShipmentCreate,
) -> FBOShipmentResponse:
    response = await _create_fbo_shipment(session, data)
    logger.info(
        "FBO shipment processed: shipment_id=%s sku=%s quantity=%s "
        "source_id=%s source=%s destination=%s status=%s",
        response.id,
        response.product.sku,
        response.quantity,
        response.source_warehouse.id,
        response.source_warehouse.name,
        response.destination,
        response.status.value,
    )
    return response


async def _ship_fbo_shipment(
    session: AsyncSession,
    shipment_id: int,
) -> FBOShipmentResponse:
    async with session.begin():
        shipment = await session.scalar(
            select(Shipment)
            .where(
                Shipment.id == shipment_id,
                Shipment.shipment_type == ShipmentType.FBO,
            )
            .with_for_update()
        )
        if shipment is None:
            raise ShipmentNotFoundError(shipment_id)

        product, warehouse = await _get_fbo_context(session, shipment)
        if shipment.status != ShipmentStatus.CREATED:
            return build_fbo_shipment_response(shipment, product, warehouse)

        inventory = await ensure_available_stock(
            session=session,
            product_id=shipment.product_id,
            warehouse_id=shipment.source_warehouse_id,
            quantity=shipment.quantity,
            lock=True,
        )
        inventory.physical_quantity -= shipment.quantity
        mark_fbo_shipment_sent(shipment)
        session.add(
            StockEvent(
                event_type=StockEventType.FBO_SHIPPED,
                product_id=shipment.product_id,
                product_sku=product.sku,
                quantity=shipment.quantity,
                source_warehouse_id=shipment.source_warehouse_id,
                source_label=warehouse.name,
                destination_label=shipment.destination,
                reference_type="fbo_shipment",
                reference_id=shipment.id,
                idempotency_key=f"fbo:{shipment.id}:ship",
            )
        )
        await session.flush()
        return build_fbo_shipment_response(shipment, product, warehouse)


async def ship_fbo_shipment(
    session: AsyncSession,
    shipment_id: int,
) -> FBOShipmentResponse:
    response = await _ship_fbo_shipment(session, shipment_id)
    logger.info(
        "FBO dispatch processed: shipment_id=%s sku=%s quantity=%s "
        "source_id=%s source=%s destination=%s status=%s",
        response.id,
        response.product.sku,
        response.quantity,
        response.source_warehouse.id,
        response.source_warehouse.name,
        response.destination,
        response.status.value,
    )
    return response


async def _receive_fbo_shipment(
    session: AsyncSession,
    shipment_id: int,
) -> FBOShipmentResponse:
    async with session.begin():
        shipment = await session.scalar(
            select(Shipment)
            .where(
                Shipment.id == shipment_id,
                Shipment.shipment_type == ShipmentType.FBO,
            )
            .with_for_update()
        )
        if shipment is None:
            raise ShipmentNotFoundError(shipment_id)

        product, warehouse = await _get_fbo_context(session, shipment)
        if shipment.status not in (
            ShipmentStatus.IN_TRANSIT,
            ShipmentStatus.RECEIVED,
        ):
            logger.warning(
                "Invalid FBO receipt: shipment_id=%s sku=%s quantity=%s "
                "source_id=%s source=%s destination=%s status=%s",
                shipment.id,
                product.sku,
                shipment.quantity,
                warehouse.id,
                warehouse.name,
                shipment.destination,
                shipment.status.value,
            )
        if not mark_fbo_shipment_received(shipment):
            return build_fbo_shipment_response(shipment, product, warehouse)

        session.add(
            StockEvent(
                event_type=StockEventType.FBO_RECEIVED,
                product_id=shipment.product_id,
                product_sku=product.sku,
                quantity=shipment.quantity,
                source_warehouse_id=shipment.source_warehouse_id,
                source_label=f"В пути: {shipment.destination}",
                destination_label=shipment.destination,
                reference_type="fbo_shipment",
                reference_id=shipment.id,
                idempotency_key=f"fbo:{shipment.id}:receive",
            )
        )
        await session.flush()
        return build_fbo_shipment_response(shipment, product, warehouse)


async def receive_fbo_shipment(
    session: AsyncSession,
    shipment_id: int,
) -> FBOShipmentResponse:
    response = await _receive_fbo_shipment(session, shipment_id)
    logger.info(
        "FBO receipt processed: shipment_id=%s sku=%s quantity=%s "
        "source_id=%s source=%s destination=%s status=%s",
        response.id,
        response.product.sku,
        response.quantity,
        response.source_warehouse.id,
        response.source_warehouse.name,
        response.destination,
        response.status.value,
    )
    return response
