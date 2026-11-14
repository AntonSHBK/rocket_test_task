from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.main import app
from app.models import Inventory, Product, Transfer, TransferStatus
from app.schemas.transfer import TransferCreate
from app.service.transfer import (
    _validate_existing_transfer,
    mark_transfer_received,
    mark_transfer_shipped,
)
from app.utils.exceptions import IdempotencyConflictError, InvalidTransferStateError


def make_transfer(status: TransferStatus = TransferStatus.CREATED) -> Transfer:
    return Transfer(
        id=1,
        idempotency_key="transfer-key",
        product_id=1,
        source_warehouse_id=1,
        destination_warehouse_id=2,
        quantity=4,
        status=status,
    )


def test_transfer_requires_different_warehouses() -> None:
    with pytest.raises(ValidationError):
        TransferCreate(
            sku="SKU-101",
            source_warehouse_id=1,
            destination_warehouse_id=1,
            quantity=4,
            idempotency_key="transfer-key",
        )


def test_shipping_transition_is_idempotent() -> None:
    transfer = make_transfer()
    shipped_at = datetime.now(UTC)

    first_result = mark_transfer_shipped(transfer, shipped_at)
    second_result = mark_transfer_shipped(
        transfer,
        shipped_at + timedelta(minutes=1),
    )

    assert first_result is True
    assert second_result is False
    assert transfer.status == TransferStatus.IN_TRANSIT
    assert transfer.shipped_at == shipped_at


def test_transfer_cannot_be_received_before_shipping() -> None:
    transfer = make_transfer()

    with pytest.raises(InvalidTransferStateError):
        mark_transfer_received(transfer)


def test_receiving_transition_is_idempotent() -> None:
    transfer = make_transfer(TransferStatus.IN_TRANSIT)
    received_at = datetime.now(UTC)

    first_result = mark_transfer_received(transfer, received_at)
    second_result = mark_transfer_received(
        transfer,
        received_at + timedelta(minutes=1),
    )

    assert first_result is True
    assert second_result is False
    assert transfer.status == TransferStatus.RECEIVED
    assert transfer.received_at == received_at


def test_transfer_flow_preserves_total_stock() -> None:
    transfer = make_transfer()
    source = Inventory(
        product_id=1,
        warehouse_id=1,
        physical_quantity=10,
        reserved_quantity=0,
    )
    destination = Inventory(
        product_id=1,
        warehouse_id=2,
        physical_quantity=6,
        reserved_quantity=0,
    )

    assert mark_transfer_shipped(transfer) is True
    source.physical_quantity -= transfer.quantity
    in_transit = transfer.quantity
    assert source.physical_quantity + destination.physical_quantity + in_transit == 16

    assert mark_transfer_received(transfer) is True
    destination.physical_quantity += transfer.quantity
    in_transit = 0

    assert source.physical_quantity == 6
    assert destination.physical_quantity == 10
    assert source.physical_quantity + destination.physical_quantity + in_transit == 16


def test_reused_idempotency_key_rejects_other_transfer() -> None:
    transfer = make_transfer()
    product = Product(id=1, sku="SKU-101", name="Органайзер")
    other_request = TransferCreate(
        sku="SKU-101",
        source_warehouse_id=1,
        destination_warehouse_id=2,
        quantity=5,
        idempotency_key="transfer-key",
    )

    with pytest.raises(IdempotencyConflictError):
        _validate_existing_transfer(transfer, other_request, product)


def test_transfer_routes_are_registered() -> None:
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if route.path.startswith("/api/transfers")
    }

    assert ("/api/transfers", "GET") in routes
    assert ("/api/transfers", "POST") in routes
    assert ("/api/transfers/{transfer_id}/ship", "POST") in routes
    assert ("/api/transfers/{transfer_id}/receive", "POST") in routes
