from datetime import UTC, datetime

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.main import app
from app.models import (
    FBSReservation,
    Inventory,
    Product,
    Shipment,
    StockEvent,
    StockEventType,
    Transfer,
    Warehouse,
)
from app.service.history import build_stock_event_response


def test_history_uses_saved_labels_after_warehouse_rename() -> None:
    product = Product(id=1, sku="SKU-NEW", name="Органайзер")
    source = Warehouse(id=1, name="Новое имя Севера", is_active=True)
    destination = Warehouse(id=2, name="Новое имя Юга", is_active=True)
    event = StockEvent(
        id=1,
        event_type=StockEventType.TRANSFER_SHIPPED,
        product_id=1,
        product_sku="SKU-101",
        quantity=4,
        source_warehouse_id=1,
        destination_warehouse_id=2,
        source_label="Север",
        destination_label="Юг",
        reference_type="transfer",
        reference_id=10,
        created_at=datetime.now(UTC),
    )

    response = build_stock_event_response(event, product, source, destination)

    assert response.sku == "SKU-101"
    assert response.quantity == 4
    assert response.source == "Север"
    assert response.destination == "Юг"


def test_history_falls_back_to_current_warehouse_names() -> None:
    product = Product(id=1, sku="SKU-101", name="Органайзер")
    warehouse = Warehouse(id=1, name="Север", is_active=True)
    event = StockEvent(
        id=1,
        event_type=StockEventType.RECEIPT,
        product_id=1,
        quantity=10,
        destination_warehouse_id=1,
        created_at=datetime.now(UTC),
    )

    response = build_stock_event_response(event, product, None, warehouse)

    assert response.destination == "Север"


def test_stock_tables_have_unique_idempotency_keys() -> None:
    tables = [
        FBSReservation.__table__,
        Transfer.__table__,
        Shipment.__table__,
        StockEvent.__table__,
    ]

    for table in tables:
        unique_columns = {
            column.name
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
            for column in constraint.columns
        }
        assert "idempotency_key" in unique_columns


def test_database_constraints_prevent_invalid_quantities() -> None:
    inventory_constraints = {
        constraint.name
        for constraint in Inventory.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_inventories_physical_quantity_non_negative" in inventory_constraints
    assert "ck_inventories_reserved_quantity_non_negative" in inventory_constraints
    assert "ck_inventories_reserved_not_above_physical" in inventory_constraints

    for table in [
        FBSReservation.__table__,
        Transfer.__table__,
        Shipment.__table__,
        StockEvent.__table__,
    ]:
        check_names = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }
        assert any(name.endswith("quantity_positive") for name in check_names)


def test_all_stock_operation_types_are_registered() -> None:
    assert set(StockEventType) == {
        StockEventType.RECEIPT,
        StockEventType.WRITE_OFF,
        StockEventType.FBS_RESERVED,
        StockEventType.FBS_RESERVATION_CANCELLED,
        StockEventType.FBS_SHIPPED,
        StockEventType.TRANSFER_SHIPPED,
        StockEventType.TRANSFER_RECEIVED,
        StockEventType.FBO_SHIPPED,
        StockEventType.FBO_RECEIVED,
    }


def test_history_route_is_registered() -> None:
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    assert ("/api/history", "GET") in routes


def test_latest_alembic_revision_contains_write_off() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert script.get_heads() == ["0003_write_off"]
