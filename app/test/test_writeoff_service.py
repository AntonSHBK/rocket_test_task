import logging
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.main import app
from app.models import Inventory, StockEvent, StockEventType
from app.schemas.writeoff import WriteOffCreate
from app.models import Product, Warehouse
from app.service.writeoff import (
    _validate_existing_write_off,
    apply_write_off,
    write_off_stock,
)
from app.utils.exceptions import IdempotencyConflictError, InsufficientStockError


class FakeTransaction:
    def __init__(self) -> None:
        self.exception_type: type[BaseException] | None = None

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        self.exception_type = exception_type


class FakeSession:
    def __init__(self, scalar_results: list[object]) -> None:
        self.scalar = AsyncMock(side_effect=scalar_results)
        self.flush = AsyncMock()
        self.transaction = FakeTransaction()

    def begin(self) -> FakeTransaction:
        return self.transaction


def build_context() -> tuple[Product, Warehouse, Inventory]:
    product = Product(id=1, sku="SKU-101", name="Тестовый товар")
    warehouse = Warehouse(id=2, name="Основной склад", is_active=True)
    inventory = Inventory(
        product_id=product.id,
        warehouse_id=warehouse.id,
        physical_quantity=10,
        reserved_quantity=3,
    )
    return product, warehouse, inventory


def build_event(data: WriteOffCreate, event_id: int = 10) -> StockEvent:
    return StockEvent(
        id=event_id,
        event_type=StockEventType.WRITE_OFF,
        product_id=1,
        product_sku=data.sku,
        source_warehouse_id=data.warehouse_id,
        quantity=data.quantity,
        reason=data.reason,
        idempotency_key=data.idempotency_key,
    )


def build_write_off_data(**overrides: object) -> WriteOffCreate:
    values = {
        "sku": "SKU-101",
        "warehouse_id": 1,
        "quantity": 4,
        "reason": "Повреждение упаковки",
        "idempotency_key": "write-off-key",
        **overrides,
    }
    return WriteOffCreate.model_validate(values)


def test_write_off_reason_is_normalized() -> None:
    data = build_write_off_data(reason="  Повреждение   упаковки  ")

    assert data.reason == "Повреждение упаковки"


def test_write_off_requires_positive_quantity_and_reason() -> None:
    with pytest.raises(ValidationError):
        build_write_off_data(quantity=0)

    with pytest.raises(ValidationError):
        build_write_off_data(reason="   ")


def test_write_off_decreases_only_physical_quantity() -> None:
    inventory = Inventory(physical_quantity=10, reserved_quantity=3)

    apply_write_off(inventory, quantity=4)

    assert inventory.physical_quantity == 6
    assert inventory.reserved_quantity == 3
    assert inventory.available_quantity == 3


def test_write_off_rejects_reserved_stock() -> None:
    inventory = Inventory(physical_quantity=10, reserved_quantity=3)

    with pytest.raises(ValueError, match="exceeds available stock"):
        apply_write_off(inventory, quantity=8)

    assert inventory.physical_quantity == 10
    assert inventory.reserved_quantity == 3


def test_existing_write_off_accepts_same_payload() -> None:
    data = build_write_off_data()
    event = StockEvent(
        event_type=StockEventType.WRITE_OFF,
        product_sku=data.sku,
        product_id=1,
        source_warehouse_id=data.warehouse_id,
        quantity=data.quantity,
        reason=data.reason,
        idempotency_key=data.idempotency_key,
    )

    _validate_existing_write_off(event, data)


def test_existing_write_off_rejects_changed_payload() -> None:
    data = build_write_off_data()
    event = StockEvent(
        event_type=StockEventType.WRITE_OFF,
        product_sku=data.sku,
        product_id=1,
        source_warehouse_id=data.warehouse_id,
        quantity=data.quantity,
        reason=data.reason,
        idempotency_key=data.idempotency_key,
    )

    with pytest.raises(IdempotencyConflictError):
        _validate_existing_write_off(event, build_write_off_data(quantity=5))


def test_write_off_route_is_registered() -> None:
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    assert ("/api/write-offs", "POST") in routes


@pytest.mark.asyncio
async def test_write_off_service_successfully_decreases_available_stock(
    caplog: pytest.LogCaptureFixture,
) -> None:
    data = build_write_off_data()
    product, warehouse, inventory = build_context()
    event = build_event(data)
    session = FakeSession([None, product, warehouse, event.id, event])

    caplog.set_level(logging.INFO, logger="api")
    with patch(
        "app.service.writeoff.ensure_available_stock",
        new=AsyncMock(return_value=inventory),
    ) as ensure_available_stock:
        response = await write_off_stock(session, data)  # type: ignore[arg-type]

    assert response.created is True
    assert response.stock.physical == 6
    assert response.stock.reserved == 3
    assert response.stock.available == 3
    assert inventory.physical_quantity == 6
    ensure_available_stock.assert_awaited_once_with(
        session=session,
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=data.quantity,
        lock=True,
    )
    session.flush.assert_awaited_once()
    assert session.transaction.exception_type is None
    assert "Stock written off" in caplog.text


@pytest.mark.asyncio
async def test_repeated_write_off_returns_existing_result_without_decrement() -> None:
    data = build_write_off_data()
    product, warehouse, inventory = build_context()
    event = build_event(data)
    session = FakeSession([event, product, warehouse, inventory])

    with patch(
        "app.service.writeoff.ensure_available_stock",
        new=AsyncMock(),
    ) as ensure_available_stock:
        response = await write_off_stock(session, data)  # type: ignore[arg-type]

    assert response.created is False
    assert response.event_id == event.id
    assert inventory.physical_quantity == 10
    ensure_available_stock.assert_not_awaited()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_insufficient_write_off_rolls_back_without_decrement() -> None:
    data = build_write_off_data(quantity=8)
    product, warehouse, inventory = build_context()
    session = FakeSession([None, product, warehouse, 10])
    error = InsufficientStockError(
        warehouse_name=warehouse.name,
        requested=data.quantity,
        available=inventory.available_quantity,
        other_warehouses=[],
    )

    with patch(
        "app.service.writeoff.ensure_available_stock",
        new=AsyncMock(side_effect=error),
    ):
        with pytest.raises(InsufficientStockError):
            await write_off_stock(session, data)  # type: ignore[arg-type]

    assert inventory.physical_quantity == 10
    assert inventory.reserved_quantity == 3
    assert session.transaction.exception_type is InsufficientStockError
    session.flush.assert_not_awaited()
