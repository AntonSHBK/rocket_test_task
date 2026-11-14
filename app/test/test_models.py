from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app.migrations.seed import INITIAL_STOCK, PRODUCTS, WAREHOUSES
from app.models import Base, Inventory, StockEvent, StockEventType


def test_all_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "products",
        "warehouses",
        "inventories",
        "fbs_reservations",
        "transfers",
        "shipments",
        "stock_events",
    }


def test_all_mappers_and_postgresql_ddl_are_valid() -> None:
    configure_mappers()

    for table in Base.metadata.sorted_tables:
        compiled_ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert f"CREATE TABLE {table.name}" in compiled_ddl


def test_inventory_has_quantity_and_uniqueness_constraints() -> None:
    constraints = {constraint.name for constraint in Inventory.__table__.constraints}

    assert "uq_inventories_product_warehouse" in constraints
    assert "ck_inventories_physical_quantity_non_negative" in constraints
    assert "ck_inventories_reserved_quantity_non_negative" in constraints
    assert "ck_inventories_reserved_not_above_physical" in constraints
    assert any(
        isinstance(constraint, UniqueConstraint)
        for constraint in Inventory.__table__.constraints
    )
    assert sum(
        isinstance(constraint, CheckConstraint)
        for constraint in Inventory.__table__.constraints
    ) == 3


def test_inventory_available_quantity_is_calculated() -> None:
    inventory = Inventory(physical_quantity=10, reserved_quantity=3)

    assert inventory.available_quantity == 7


def test_stock_event_supports_write_off_reason() -> None:
    event = StockEvent(
        event_type=StockEventType.WRITE_OFF,
        product_id=1,
        product_sku="SKU-101",
        quantity=2,
        source_warehouse_id=1,
        reason="Брак",
    )

    assert event.event_type == StockEventType.WRITE_OFF
    assert event.reason == "Брак"


def test_seed_data_matches_task_totals() -> None:
    assert len(PRODUCTS) == 3
    assert len(WAREHOUSES) == 2
    assert sum(item["quantity"] for item in INITIAL_STOCK) == 25
    assert sum(
        item["quantity"]
        for item in INITIAL_STOCK
        if item["warehouse"] == "Север"
    ) == 15
    assert sum(
        item["quantity"]
        for item in INITIAL_STOCK
        if item["warehouse"] == "Юг"
    ) == 10
