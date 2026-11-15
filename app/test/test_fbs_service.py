from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.main import app
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
from app.schemas.fbs import FBSReservationCreate
from app.service.fbs import (
    _deliver_reservation,
    _validate_existing_reservation,
    mark_reservation_cancelled,
    mark_reservation_delivered,
    mark_reservation_shipped,
)
from app.utils.exceptions import IdempotencyConflictError, InvalidReservationStateError


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        return None


class FakeSession:
    def __init__(self, scalar_results: list[object]) -> None:
        self.scalar = AsyncMock(side_effect=scalar_results)
        self.flush = AsyncMock()
        self.added: list[object] = []

    def begin(self) -> FakeTransaction:
        return FakeTransaction()

    def add(self, value: object) -> None:
        self.added.append(value)


def make_reservation(
    status: ReservationStatus = ReservationStatus.RESERVED,
) -> FBSReservation:
    return FBSReservation(
        id=1,
        idempotency_key="reservation-key",
        order_reference="ORDER-1",
        product_id=1,
        warehouse_id=1,
        quantity=3,
        status=status,
    )


def make_delivery_context() -> tuple[FBSReservation, Product, Warehouse, Shipment]:
    reservation = make_reservation(ReservationStatus.SHIPPED)
    reservation.created_at = datetime.now(UTC)
    product = Product(id=1, sku="SKU-101", name="Органайзер")
    warehouse = Warehouse(id=1, name="Север", is_active=True)
    shipment = Shipment(
        id=1,
        idempotency_key="fbs:1:shipment",
        shipment_type=ShipmentType.FBS,
        product_id=product.id,
        source_warehouse_id=warehouse.id,
        reservation_id=reservation.id,
        destination="ORDER-1",
        quantity=reservation.quantity,
        status=ShipmentStatus.IN_TRANSIT,
    )
    return reservation, product, warehouse, shipment


def test_reservation_requires_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        FBSReservationCreate(
            sku="SKU-101",
            warehouse_id=1,
            quantity=0,
            order_reference="ORDER-1",
            idempotency_key="reservation-key",
        )


def test_reserving_stock_does_not_change_physical_quantity() -> None:
    inventory = Inventory(
        product_id=1,
        warehouse_id=1,
        physical_quantity=10,
        reserved_quantity=0,
    )

    inventory.reserved_quantity += 3

    assert inventory.physical_quantity == 10
    assert inventory.reserved_quantity == 3
    assert inventory.available_quantity == 7


def test_cancelling_reservation_releases_stock_and_is_idempotent() -> None:
    reservation = make_reservation()
    inventory = Inventory(
        product_id=1,
        warehouse_id=1,
        physical_quantity=10,
        reserved_quantity=3,
    )
    cancelled_at = datetime.now(UTC)

    first_result = mark_reservation_cancelled(reservation, cancelled_at)
    inventory.reserved_quantity -= reservation.quantity
    second_result = mark_reservation_cancelled(
        reservation,
        cancelled_at + timedelta(minutes=1),
    )

    assert first_result is True
    assert second_result is False
    assert reservation.cancelled_at == cancelled_at
    assert inventory.physical_quantity == 10
    assert inventory.reserved_quantity == 0


def test_shipping_reservation_moves_stock_to_customer_transit() -> None:
    reservation = make_reservation()
    inventory = Inventory(
        product_id=1,
        warehouse_id=1,
        physical_quantity=10,
        reserved_quantity=3,
    )

    assert mark_reservation_shipped(reservation) is True
    inventory.physical_quantity -= reservation.quantity
    inventory.reserved_quantity -= reservation.quantity
    in_transit_to_customer = reservation.quantity

    assert inventory.physical_quantity == 7
    assert inventory.reserved_quantity == 0
    assert inventory.available_quantity == 7
    assert inventory.physical_quantity + in_transit_to_customer == 10


def test_shipped_reservation_cannot_be_cancelled() -> None:
    reservation = make_reservation(ReservationStatus.SHIPPED)

    with pytest.raises(InvalidReservationStateError):
        mark_reservation_cancelled(reservation)


def test_cancelled_reservation_cannot_be_shipped() -> None:
    reservation = make_reservation(ReservationStatus.CANCELLED)

    with pytest.raises(InvalidReservationStateError):
        mark_reservation_shipped(reservation)


def test_delivering_shipped_reservation_is_idempotent_without_stock_change() -> None:
    reservation = make_reservation(ReservationStatus.SHIPPED)
    shipment = Shipment(
        id=1,
        idempotency_key="fbs:1:shipment",
        shipment_type=ShipmentType.FBS,
        product_id=1,
        source_warehouse_id=1,
        reservation_id=reservation.id,
        destination="ORDER-1",
        quantity=reservation.quantity,
        status=ShipmentStatus.IN_TRANSIT,
    )
    inventory = Inventory(
        product_id=1,
        warehouse_id=1,
        physical_quantity=7,
        reserved_quantity=0,
    )
    delivered_at = datetime.now(UTC)

    first_result = mark_reservation_delivered(
        reservation,
        shipment,
        delivered_at,
    )
    second_result = mark_reservation_delivered(
        reservation,
        shipment,
        delivered_at + timedelta(minutes=1),
    )

    assert first_result is True
    assert second_result is False
    assert reservation.status == ReservationStatus.DELIVERED
    assert reservation.delivered_at == delivered_at
    assert shipment.status == ShipmentStatus.RECEIVED
    assert shipment.received_at == delivered_at
    assert inventory.physical_quantity == 7
    assert inventory.reserved_quantity == 0


def test_only_shipped_reservation_can_be_delivered() -> None:
    reservation = make_reservation(ReservationStatus.RESERVED)
    shipment = Shipment(status=ShipmentStatus.IN_TRANSIT)

    with pytest.raises(InvalidReservationStateError):
        mark_reservation_delivered(reservation, shipment)


@pytest.mark.asyncio
async def test_delivery_locks_reservation_and_shipment_and_adds_history() -> None:
    reservation, product, warehouse, shipment = make_delivery_context()
    session = FakeSession([reservation, product, warehouse, shipment])

    response, delivered = await _deliver_reservation(  # type: ignore[arg-type]
        session,
        reservation.id,
    )

    reservation_query = session.scalar.await_args_list[0].args[0]
    shipment_query = session.scalar.await_args_list[3].args[0]
    events = [item for item in session.added if isinstance(item, StockEvent)]
    assert reservation_query._for_update_arg is not None
    assert shipment_query._for_update_arg is not None
    assert delivered is True
    assert response.status == ReservationStatus.DELIVERED
    assert len(events) == 1
    assert events[0].event_type == StockEventType.FBS_DELIVERED
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_repeated_delivery_does_not_add_duplicate_history() -> None:
    reservation, product, warehouse, shipment = make_delivery_context()
    mark_reservation_delivered(reservation, shipment)
    session = FakeSession([reservation, product, warehouse, shipment])

    response, delivered = await _deliver_reservation(  # type: ignore[arg-type]
        session,
        reservation.id,
    )

    assert delivered is False
    assert response.status == ReservationStatus.DELIVERED
    assert session.added == []
    session.flush.assert_not_awaited()


def test_reused_idempotency_key_rejects_other_reservation() -> None:
    reservation = make_reservation()
    product = Product(id=1, sku="SKU-101", name="Органайзер")
    other_request = FBSReservationCreate(
        sku="SKU-101",
        warehouse_id=1,
        quantity=4,
        order_reference="ORDER-1",
        idempotency_key="reservation-key",
    )

    with pytest.raises(IdempotencyConflictError):
        _validate_existing_reservation(reservation, other_request, product)


def test_fbs_routes_are_registered() -> None:
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if route.path.startswith("/api/fbs")
    }

    assert ("/api/fbs/reservations", "GET") in routes
    assert ("/api/fbs/reservations", "POST") in routes
    assert ("/api/fbs/reservations/{reservation_id}/cancel", "POST") in routes
    assert ("/api/fbs/reservations/{reservation_id}/ship", "POST") in routes
    assert ("/api/fbs/reservations/{reservation_id}/deliver", "POST") in routes
