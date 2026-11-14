from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.main import app
from app.models import Inventory, Warehouse
from app.schemas.warehouse import WarehouseCreate
from app.service.warehouse import (
    build_warehouse_response,
    mark_warehouse_active,
    mark_warehouse_archived,
)


def test_warehouse_name_is_normalized() -> None:
    data = WarehouseCreate(name="  Новый   склад  ")

    assert data.name == "Новый склад"


def test_warehouse_name_must_not_be_blank() -> None:
    with pytest.raises(ValidationError):
        WarehouseCreate(name="   ")


def test_warehouse_response_calculates_available_quantity() -> None:
    warehouse = Warehouse(id=1, name="Север", is_active=True)

    response = build_warehouse_response(
        warehouse=warehouse,
        physical_quantity=15,
        reserved_quantity=4,
    )

    assert response.physical_quantity == 15
    assert response.reserved_quantity == 4
    assert response.available_quantity == 11


def test_archiving_preserves_inventory() -> None:
    inventory = Inventory(
        product_id=1,
        warehouse_id=1,
        physical_quantity=10,
        reserved_quantity=3,
    )
    warehouse = Warehouse(
        id=1,
        name="Север",
        is_active=True,
        inventories=[inventory],
    )
    archived_at = datetime.now(UTC)

    mark_warehouse_archived(warehouse, archived_at)

    assert warehouse.is_active is False
    assert warehouse.archived_at == archived_at
    assert warehouse.inventories == [inventory]
    assert inventory.physical_quantity == 10
    assert inventory.reserved_quantity == 3


def test_repeated_archiving_keeps_original_archive_time() -> None:
    first_archive_time = datetime.now(UTC)
    warehouse = Warehouse(
        id=1,
        name="Север",
        is_active=True,
    )
    mark_warehouse_archived(warehouse, first_archive_time)

    mark_warehouse_archived(warehouse, first_archive_time + timedelta(days=1))

    assert warehouse.archived_at == first_archive_time


def test_restoring_warehouse_preserves_inventory() -> None:
    inventory = Inventory(
        product_id=1,
        warehouse_id=1,
        physical_quantity=10,
        reserved_quantity=3,
    )
    warehouse = Warehouse(
        id=1,
        name="Север",
        is_active=False,
        archived_at=datetime.now(UTC),
        inventories=[inventory],
    )

    mark_warehouse_active(warehouse)

    assert warehouse.is_active is True
    assert warehouse.archived_at is None
    assert warehouse.inventories == [inventory]
    assert inventory.physical_quantity == 10
    assert inventory.reserved_quantity == 3


def test_warehouse_routes_are_registered() -> None:
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if route.path.startswith("/api/warehouses")
    }

    assert ("/api/warehouses", "GET") in routes
    assert ("/api/warehouses", "POST") in routes
    assert ("/api/warehouses/{warehouse_id}", "PATCH") in routes
    assert ("/api/warehouses/{warehouse_id}", "DELETE") in routes
    assert ("/api/warehouses/{warehouse_id}/restore", "POST") in routes
