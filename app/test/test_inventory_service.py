import pytest
from pydantic import ValidationError

from app.main import app
from app.models import (
    Inventory,
    Product,
    ShipmentType,
    StockEvent,
    StockEventType,
    Warehouse,
)
from app.schemas.inventory import ReceiptCreate
from app.service.inventory import (
    _validate_existing_receipt,
    build_inventory_snapshot,
    validate_stock_availability,
)
from app.utils.exceptions import IdempotencyConflictError, InsufficientStockError


def test_inventory_snapshot_calculates_stock_and_transit_totals() -> None:
    product = Product(id=1, sku="SKU-101", name="Органайзер")
    north = Warehouse(id=1, name="Север", is_active=True)
    south = Warehouse(id=2, name="Юг", is_active=True)
    inventories = [
        Inventory(
            product_id=1,
            warehouse_id=1,
            physical_quantity=10,
            reserved_quantity=3,
        ),
        Inventory(
            product_id=1,
            warehouse_id=2,
            physical_quantity=6,
            reserved_quantity=1,
        ),
    ]

    snapshot = build_inventory_snapshot(
        products=[product],
        warehouses=[north, south],
        inventories=inventories,
        transfer_totals={1: 2},
        shipment_totals={
            (1, ShipmentType.FBS): 3,
            (1, ShipmentType.FBO): 4,
        },
    )

    assert snapshot[0].totals.model_dump() == {
        "physical": 16,
        "reserved": 4,
        "available": 12,
    }
    assert snapshot[0].in_transit.model_dump() == {
        "between_warehouses": 2,
        "to_marketplace": 4,
        "to_customer": 3,
        "total": 9,
    }
    assert snapshot[0].warehouses[0].available == 7


def test_stock_validation_rejects_insufficient_selected_warehouse() -> None:
    with pytest.raises(InsufficientStockError) as error:
        validate_stock_availability(
            warehouse_name="Север",
            requested=5,
            available=2,
            other_warehouses=[
                {"warehouse_id": 2, "name": "Юг", "available": 8}
            ],
        )

    assert error.value.details == {
        "requested": 5,
        "available": 2,
        "other_warehouses": [
            {"warehouse_id": 2, "name": "Юг", "available": 8}
        ],
    }


def test_stock_validation_accepts_exact_available_quantity() -> None:
    validate_stock_availability(
        warehouse_name="Север",
        requested=5,
        available=5,
        other_warehouses=[],
    )


def test_receipt_requires_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        ReceiptCreate(sku="SKU-101", warehouse_id=1, quantity=0)


def test_existing_receipt_rejects_reused_key_with_other_payload() -> None:
    event = StockEvent(
        event_type=StockEventType.RECEIPT,
        product_id=1,
        destination_warehouse_id=1,
        quantity=5,
        idempotency_key="receipt-key",
    )

    with pytest.raises(IdempotencyConflictError):
        _validate_existing_receipt(
            event=event,
            product_id=1,
            warehouse_id=1,
            quantity=6,
        )


def test_inventory_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/api/products" in paths
    assert "/api/inventory" in paths
    assert "/api/receipts" in paths
