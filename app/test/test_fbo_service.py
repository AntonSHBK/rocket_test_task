from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.main import app
from app.models import Inventory, Product, Shipment, ShipmentStatus, ShipmentType
from app.schemas.fbo import FBOShipmentCreate
from app.service.fbo import (
    _validate_existing_fbo_shipment,
    mark_fbo_shipment_received,
    mark_fbo_shipment_sent,
)
from app.utils.exceptions import IdempotencyConflictError, InvalidShipmentStateError


def make_shipment(
    status: ShipmentStatus = ShipmentStatus.CREATED,
) -> Shipment:
    return Shipment(
        id=1,
        idempotency_key="fbo-key",
        shipment_type=ShipmentType.FBO,
        product_id=1,
        source_warehouse_id=1,
        reservation_id=None,
        destination="Маркетплейс Москва",
        quantity=6,
        status=status,
    )


def test_fbo_destination_is_normalized() -> None:
    data = FBOShipmentCreate(
        sku="SKU-101",
        source_warehouse_id=1,
        destination="  Маркетплейс   Москва  ",
        quantity=6,
        idempotency_key="fbo-key",
    )

    assert data.destination == "Маркетплейс Москва"


def test_fbo_destination_must_not_be_blank() -> None:
    with pytest.raises(ValidationError):
        FBOShipmentCreate(
            sku="SKU-101",
            source_warehouse_id=1,
            destination="   ",
            quantity=6,
            idempotency_key="fbo-key",
        )


def test_sending_fbo_shipment_is_idempotent() -> None:
    shipment = make_shipment()
    shipped_at = datetime.now(UTC)

    first_result = mark_fbo_shipment_sent(shipment, shipped_at)
    second_result = mark_fbo_shipment_sent(
        shipment,
        shipped_at + timedelta(minutes=1),
    )

    assert first_result is True
    assert second_result is False
    assert shipment.status == ShipmentStatus.IN_TRANSIT
    assert shipment.shipped_at == shipped_at


def test_fbo_shipment_cannot_be_received_before_shipping() -> None:
    shipment = make_shipment()

    with pytest.raises(InvalidShipmentStateError):
        mark_fbo_shipment_received(shipment)


def test_receiving_fbo_shipment_is_idempotent() -> None:
    shipment = make_shipment(ShipmentStatus.IN_TRANSIT)
    received_at = datetime.now(UTC)

    first_result = mark_fbo_shipment_received(shipment, received_at)
    second_result = mark_fbo_shipment_received(
        shipment,
        received_at + timedelta(minutes=1),
    )

    assert first_result is True
    assert second_result is False
    assert shipment.status == ShipmentStatus.RECEIVED
    assert shipment.received_at == received_at


def test_fbo_flow_preserves_total_stock() -> None:
    shipment = make_shipment()
    inventory = Inventory(
        product_id=1,
        warehouse_id=1,
        physical_quantity=10,
        reserved_quantity=0,
    )

    assert mark_fbo_shipment_sent(shipment) is True
    inventory.physical_quantity -= shipment.quantity
    in_transit = shipment.quantity
    accepted_by_marketplace = 0
    assert inventory.physical_quantity + in_transit + accepted_by_marketplace == 10

    assert mark_fbo_shipment_received(shipment) is True
    in_transit = 0
    accepted_by_marketplace = shipment.quantity

    assert inventory.physical_quantity == 4
    assert accepted_by_marketplace == 6
    assert inventory.physical_quantity + in_transit + accepted_by_marketplace == 10


def test_reused_idempotency_key_rejects_other_fbo_shipment() -> None:
    shipment = make_shipment()
    product = Product(id=1, sku="SKU-101", name="Органайзер")
    other_request = FBOShipmentCreate(
        sku="SKU-101",
        source_warehouse_id=1,
        destination="Маркетплейс Москва",
        quantity=5,
        idempotency_key="fbo-key",
    )

    with pytest.raises(IdempotencyConflictError):
        _validate_existing_fbo_shipment(shipment, other_request, product)


def test_fbo_routes_are_registered() -> None:
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if route.path.startswith("/api/fbo")
    }

    assert ("/api/fbo/shipments", "GET") in routes
    assert ("/api/fbo/shipments", "POST") in routes
    assert ("/api/fbo/shipments/{shipment_id}/ship", "POST") in routes
    assert ("/api/fbo/shipments/{shipment_id}/receive", "POST") in routes
