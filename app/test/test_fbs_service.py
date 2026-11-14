from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.main import app
from app.models import FBSReservation, Inventory, Product, ReservationStatus
from app.schemas.fbs import FBSReservationCreate
from app.service.fbs import (
    _validate_existing_reservation,
    mark_reservation_cancelled,
    mark_reservation_shipped,
)
from app.utils.exceptions import IdempotencyConflictError, InvalidReservationStateError


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
