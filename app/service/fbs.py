import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FBSReservation,
    Inventory,
    Product,
    ReservationStatus,
    Shipment,
    ShipmentStatus,
    ShipmentType,
    StockEvent,
    StockEventType,
    Warehouse,
)
from app.schemas.fbs import (
    FBSReservationCreate,
    FBSReservationResponse,
    FBSWarehouseResponse,
)
from app.schemas.product import ProductResponse
from app.service.inventory import ensure_available_stock
from app.utils.exceptions import (
    IdempotencyConflictError,
    InvalidReservationStateError,
    InvalidShipmentStateError,
    ProductNotFoundError,
    ReservationNotFoundError,
    WarehouseInactiveError,
    WarehouseNotFoundError,
)

logger = logging.getLogger("api")


def build_reservation_response(
    reservation: FBSReservation,
    product: Product,
    warehouse: Warehouse,
    shipment_id: int | None,
) -> FBSReservationResponse:
    return FBSReservationResponse(
        id=reservation.id,
        idempotency_key=reservation.idempotency_key,
        order_reference=reservation.order_reference,
        product=ProductResponse.model_validate(product),
        warehouse=FBSWarehouseResponse(
            id=warehouse.id,
            name=warehouse.name,
            is_active=warehouse.is_active,
        ),
        quantity=reservation.quantity,
        status=reservation.status,
        shipment_id=shipment_id,
        cancelled_at=reservation.cancelled_at,
        shipped_at=reservation.shipped_at,
        delivered_at=reservation.delivered_at,
        created_at=reservation.created_at,
    )


def mark_reservation_cancelled(
    reservation: FBSReservation,
    cancelled_at: datetime | None = None,
) -> bool:
    if reservation.status == ReservationStatus.CANCELLED:
        return False
    if reservation.status != ReservationStatus.RESERVED:
        raise InvalidReservationStateError(
            current_status=reservation.status.value,
            operation="cancel",
        )

    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = cancelled_at or datetime.now(UTC)
    return True


def mark_reservation_shipped(
    reservation: FBSReservation,
    shipped_at: datetime | None = None,
) -> bool:
    if reservation.status == ReservationStatus.SHIPPED:
        return False
    if reservation.status != ReservationStatus.RESERVED:
        raise InvalidReservationStateError(
            current_status=reservation.status.value,
            operation="ship",
        )

    reservation.status = ReservationStatus.SHIPPED
    reservation.shipped_at = shipped_at or datetime.now(UTC)
    return True


def mark_reservation_delivered(
    reservation: FBSReservation,
    shipment: Shipment,
    delivered_at: datetime | None = None,
) -> bool:
    if (
        reservation.status == ReservationStatus.DELIVERED
        and shipment.status == ShipmentStatus.RECEIVED
    ):
        return False
    if reservation.status != ReservationStatus.SHIPPED:
        raise InvalidReservationStateError(
            current_status=reservation.status.value,
            operation="deliver",
        )
    if shipment.status != ShipmentStatus.IN_TRANSIT:
        raise InvalidShipmentStateError(
            current_status=shipment.status.value,
            expected_status=ShipmentStatus.IN_TRANSIT.value,
        )

    completed_at = delivered_at or datetime.now(UTC)
    reservation.status = ReservationStatus.DELIVERED
    reservation.delivered_at = completed_at
    shipment.status = ShipmentStatus.RECEIVED
    shipment.received_at = completed_at
    return True


def _validate_existing_reservation(
    reservation: FBSReservation,
    data: FBSReservationCreate,
    product: Product,
) -> None:
    if (
        reservation.product_id != product.id
        or product.sku != data.sku
        or reservation.warehouse_id != data.warehouse_id
        or reservation.quantity != data.quantity
        or reservation.order_reference != data.order_reference
    ):
        raise IdempotencyConflictError()


async def _get_reservation_context(
    session: AsyncSession,
    reservation: FBSReservation,
) -> tuple[Product, Warehouse, int | None]:
    product = await session.scalar(
        select(Product).where(Product.id == reservation.product_id)
    )
    warehouse = await session.scalar(
        select(Warehouse).where(Warehouse.id == reservation.warehouse_id)
    )
    shipment_id = await session.scalar(
        select(Shipment.id).where(Shipment.reservation_id == reservation.id)
    )
    if product is None:
        raise ProductNotFoundError(str(reservation.product_id))
    if warehouse is None:
        raise WarehouseNotFoundError(reservation.warehouse_id)
    return product, warehouse, shipment_id


async def list_reservations(
    session: AsyncSession,
) -> list[FBSReservationResponse]:
    rows = (
        await session.execute(
            select(FBSReservation, Product, Warehouse, Shipment.id)
            .join(Product, Product.id == FBSReservation.product_id)
            .join(Warehouse, Warehouse.id == FBSReservation.warehouse_id)
            .outerjoin(Shipment, Shipment.reservation_id == FBSReservation.id)
            .order_by(FBSReservation.id.desc())
        )
    ).all()
    return [
        build_reservation_response(reservation, product, warehouse, shipment_id)
        for reservation, product, warehouse, shipment_id in rows
    ]


async def _create_reservation(
    session: AsyncSession,
    data: FBSReservationCreate,
) -> FBSReservationResponse:
    async with session.begin():
        existing_reservation = await session.scalar(
            select(FBSReservation).where(
                FBSReservation.idempotency_key == data.idempotency_key
            )
        )
        if existing_reservation is not None:
            product, warehouse, shipment_id = await _get_reservation_context(
                session,
                existing_reservation,
            )
            _validate_existing_reservation(existing_reservation, data, product)
            return build_reservation_response(
                existing_reservation,
                product,
                warehouse,
                shipment_id,
            )

        product = await session.scalar(select(Product).where(Product.sku == data.sku))
        if product is None:
            raise ProductNotFoundError(data.sku)
        warehouse = await session.scalar(
            select(Warehouse).where(Warehouse.id == data.warehouse_id)
        )
        if warehouse is None:
            raise WarehouseNotFoundError(data.warehouse_id)
        if not warehouse.is_active:
            raise WarehouseInactiveError(warehouse.id)

        reservation_id = await session.scalar(
            insert(FBSReservation)
            .values(
                idempotency_key=data.idempotency_key,
                order_reference=data.order_reference,
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=data.quantity,
                status=ReservationStatus.RESERVED,
            )
            .on_conflict_do_nothing(index_elements=[FBSReservation.idempotency_key])
            .returning(FBSReservation.id)
        )
        if reservation_id is None:
            reservation = await session.scalar(
                select(FBSReservation).where(
                    FBSReservation.idempotency_key == data.idempotency_key
                )
            )
            if reservation is None:
                raise RuntimeError("Existing FBS reservation was not found")
            product, warehouse, shipment_id = await _get_reservation_context(
                session,
                reservation,
            )
            _validate_existing_reservation(reservation, data, product)
            return build_reservation_response(
                reservation,
                product,
                warehouse,
                shipment_id,
            )

        reservation = await session.scalar(
            select(FBSReservation).where(FBSReservation.id == reservation_id)
        )
        if reservation is None:
            raise RuntimeError("Created FBS reservation was not found")

        inventory = await ensure_available_stock(
            session=session,
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity=data.quantity,
            lock=True,
        )
        inventory.reserved_quantity += data.quantity
        session.add(
            StockEvent(
                event_type=StockEventType.FBS_RESERVED,
                product_id=product.id,
                product_sku=product.sku,
                quantity=data.quantity,
                source_warehouse_id=warehouse.id,
                source_label=warehouse.name,
                destination_label=(
                    f"Резерв FBS {data.order_reference}"
                    if data.order_reference
                    else "Резерв FBS"
                ),
                reference_type="fbs_reservation",
                reference_id=reservation.id,
                idempotency_key=f"fbs:{reservation.id}:reserve",
            )
        )
        await session.flush()
        return build_reservation_response(
            reservation,
            product,
            warehouse,
            shipment_id=None,
        )


async def create_reservation(
    session: AsyncSession,
    data: FBSReservationCreate,
) -> FBSReservationResponse:
    response = await _create_reservation(session, data)
    logger.info(
        "FBS reservation processed: reservation_id=%s sku=%s quantity=%s "
        "warehouse_id=%s warehouse=%s status=%s",
        response.id,
        response.product.sku,
        response.quantity,
        response.warehouse.id,
        response.warehouse.name,
        response.status.value,
    )
    return response


async def _cancel_reservation(
    session: AsyncSession,
    reservation_id: int,
) -> FBSReservationResponse:
    async with session.begin():
        reservation = await session.scalar(
            select(FBSReservation)
            .where(FBSReservation.id == reservation_id)
            .with_for_update()
        )
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)

        product, warehouse, shipment_id = await _get_reservation_context(
            session,
            reservation,
        )
        if reservation.status == ReservationStatus.CANCELLED:
            return build_reservation_response(
                reservation,
                product,
                warehouse,
                shipment_id,
            )
        if reservation.status != ReservationStatus.RESERVED:
            logger.warning(
                "Invalid FBS cancellation: reservation_id=%s sku=%s quantity=%s "
                "warehouse_id=%s warehouse=%s status=%s",
                reservation.id,
                product.sku,
                reservation.quantity,
                warehouse.id,
                warehouse.name,
                reservation.status.value,
            )
            mark_reservation_cancelled(reservation)

        inventory = await session.scalar(
            select(Inventory)
            .where(
                Inventory.product_id == reservation.product_id,
                Inventory.warehouse_id == reservation.warehouse_id,
            )
            .with_for_update()
        )
        if inventory is None or inventory.reserved_quantity < reservation.quantity:
            logger.warning(
                "Inconsistent FBS reserved stock: reservation_id=%s sku=%s "
                "quantity=%s warehouse_id=%s warehouse=%s reserved=%s",
                reservation.id,
                product.sku,
                reservation.quantity,
                warehouse.id,
                warehouse.name,
                inventory.reserved_quantity if inventory else 0,
            )
            raise RuntimeError("Reserved inventory is inconsistent")

        inventory.reserved_quantity -= reservation.quantity
        mark_reservation_cancelled(reservation)
        session.add(
            StockEvent(
                event_type=StockEventType.FBS_RESERVATION_CANCELLED,
                product_id=reservation.product_id,
                product_sku=product.sku,
                quantity=reservation.quantity,
                destination_warehouse_id=reservation.warehouse_id,
                source_label=(
                    f"Резерв FBS {reservation.order_reference}"
                    if reservation.order_reference
                    else "Резерв FBS"
                ),
                destination_label=warehouse.name,
                reference_type="fbs_reservation",
                reference_id=reservation.id,
                idempotency_key=f"fbs:{reservation.id}:cancel",
            )
        )
        await session.flush()
        return build_reservation_response(
            reservation,
            product,
            warehouse,
            shipment_id=None,
        )


async def cancel_reservation(
    session: AsyncSession,
    reservation_id: int,
) -> FBSReservationResponse:
    response = await _cancel_reservation(session, reservation_id)
    logger.info(
        "FBS cancellation processed: reservation_id=%s sku=%s quantity=%s "
        "warehouse_id=%s warehouse=%s status=%s",
        response.id,
        response.product.sku,
        response.quantity,
        response.warehouse.id,
        response.warehouse.name,
        response.status.value,
    )
    return response


async def _ship_reservation(
    session: AsyncSession,
    reservation_id: int,
) -> FBSReservationResponse:
    async with session.begin():
        reservation = await session.scalar(
            select(FBSReservation)
            .where(FBSReservation.id == reservation_id)
            .with_for_update()
        )
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)

        product, warehouse, shipment_id = await _get_reservation_context(
            session,
            reservation,
        )
        if reservation.status == ReservationStatus.SHIPPED:
            return build_reservation_response(
                reservation,
                product,
                warehouse,
                shipment_id,
            )
        if reservation.status != ReservationStatus.RESERVED:
            logger.warning(
                "Invalid FBS shipment: reservation_id=%s sku=%s quantity=%s "
                "warehouse_id=%s warehouse=%s status=%s",
                reservation.id,
                product.sku,
                reservation.quantity,
                warehouse.id,
                warehouse.name,
                reservation.status.value,
            )
            mark_reservation_shipped(reservation)

        inventory = await session.scalar(
            select(Inventory)
            .where(
                Inventory.product_id == reservation.product_id,
                Inventory.warehouse_id == reservation.warehouse_id,
            )
            .with_for_update()
        )
        if (
            inventory is None
            or inventory.physical_quantity < reservation.quantity
            or inventory.reserved_quantity < reservation.quantity
        ):
            logger.warning(
                "Inconsistent FBS shipment stock: reservation_id=%s sku=%s "
                "quantity=%s warehouse_id=%s warehouse=%s physical=%s reserved=%s",
                reservation.id,
                product.sku,
                reservation.quantity,
                warehouse.id,
                warehouse.name,
                inventory.physical_quantity if inventory else 0,
                inventory.reserved_quantity if inventory else 0,
            )
            raise RuntimeError("Reserved inventory is inconsistent")

        inventory.physical_quantity -= reservation.quantity
        inventory.reserved_quantity -= reservation.quantity
        mark_reservation_shipped(reservation)

        shipment = Shipment(
            idempotency_key=f"fbs:{reservation.id}:shipment",
            shipment_type=ShipmentType.FBS,
            product_id=reservation.product_id,
            source_warehouse_id=reservation.warehouse_id,
            reservation_id=reservation.id,
            destination=reservation.order_reference or "Клиент",
            quantity=reservation.quantity,
            status=ShipmentStatus.IN_TRANSIT,
            shipped_at=reservation.shipped_at,
        )
        session.add(shipment)
        session.add(
            StockEvent(
                event_type=StockEventType.FBS_SHIPPED,
                product_id=reservation.product_id,
                product_sku=product.sku,
                quantity=reservation.quantity,
                source_warehouse_id=reservation.warehouse_id,
                source_label=warehouse.name,
                destination_label=reservation.order_reference or "Клиент",
                reference_type="fbs_reservation",
                reference_id=reservation.id,
                idempotency_key=f"fbs:{reservation.id}:ship",
            )
        )
        await session.flush()
        return build_reservation_response(
            reservation,
            product,
            warehouse,
            shipment_id=shipment.id,
        )


async def ship_reservation(
    session: AsyncSession,
    reservation_id: int,
) -> FBSReservationResponse:
    response = await _ship_reservation(session, reservation_id)
    logger.info(
        "FBS shipment processed: reservation_id=%s shipment_id=%s sku=%s "
        "quantity=%s warehouse_id=%s warehouse=%s status=%s",
        response.id,
        response.shipment_id,
        response.product.sku,
        response.quantity,
        response.warehouse.id,
        response.warehouse.name,
        response.status.value,
    )
    return response


async def _deliver_reservation(
    session: AsyncSession,
    reservation_id: int,
) -> tuple[FBSReservationResponse, bool]:
    async with session.begin():
        reservation = await session.scalar(
            select(FBSReservation)
            .where(FBSReservation.id == reservation_id)
            .with_for_update()
        )
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)

        product = await session.scalar(
            select(Product).where(Product.id == reservation.product_id)
        )
        warehouse = await session.scalar(
            select(Warehouse).where(Warehouse.id == reservation.warehouse_id)
        )
        if product is None:
            raise ProductNotFoundError(str(reservation.product_id))
        if warehouse is None:
            raise WarehouseNotFoundError(reservation.warehouse_id)

        if reservation.status not in {
            ReservationStatus.SHIPPED,
            ReservationStatus.DELIVERED,
        }:
            logger.warning(
                "Invalid FBS delivery: reservation_id=%s sku=%s quantity=%s "
                "warehouse_id=%s warehouse=%s status=%s",
                reservation.id,
                product.sku,
                reservation.quantity,
                warehouse.id,
                warehouse.name,
                reservation.status.value,
            )
            raise InvalidReservationStateError(
                current_status=reservation.status.value,
                operation="deliver",
            )

        shipment = await session.scalar(
            select(Shipment)
            .where(
                Shipment.reservation_id == reservation.id,
                Shipment.shipment_type == ShipmentType.FBS,
            )
            .with_for_update()
        )
        if shipment is None:
            raise RuntimeError("FBS shipment was not found")

        delivered = mark_reservation_delivered(reservation, shipment)
        if delivered:
            session.add(
                StockEvent(
                    event_type=StockEventType.FBS_DELIVERED,
                    product_id=reservation.product_id,
                    product_sku=product.sku,
                    quantity=reservation.quantity,
                    source_label="В пути к клиенту",
                    destination_label=reservation.order_reference or "Клиент",
                    reference_type="fbs_reservation",
                    reference_id=reservation.id,
                    idempotency_key=f"fbs:{reservation.id}:deliver",
                )
            )
            await session.flush()

        return (
            build_reservation_response(
                reservation,
                product,
                warehouse,
                shipment_id=shipment.id,
            ),
            delivered,
        )


async def deliver_reservation(
    session: AsyncSession,
    reservation_id: int,
) -> FBSReservationResponse:
    response, delivered = await _deliver_reservation(session, reservation_id)
    logger.info(
        "FBS delivery %s: reservation_id=%s shipment_id=%s sku=%s quantity=%s "
        "warehouse_id=%s warehouse=%s status=%s",
        "completed" if delivered else "replayed",
        response.id,
        response.shipment_id,
        response.product.sku,
        response.quantity,
        response.warehouse.id,
        response.warehouse.name,
        response.status.value,
    )
    return response
