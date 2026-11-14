import asyncio

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, close_database
from app.models import (
    Inventory,
    Product,
    StockEvent,
    StockEventType,
    Warehouse,
)
from app.settings import settings
from app.utils.logging import get_process_logger

PRODUCTS = (
    {"sku": "SKU-101", "name": "Органайзер"},
    {"sku": "SKU-102", "name": "Контейнер"},
    {"sku": "SKU-103", "name": "Корзина"},
)

WAREHOUSES = (
    {"name": "Север"},
    {"name": "Юг"},
)

INITIAL_STOCK = (
    {"sku": "SKU-101", "warehouse": "Север", "quantity": 10},
    {"sku": "SKU-101", "warehouse": "Юг", "quantity": 6},
    {"sku": "SKU-102", "warehouse": "Север", "quantity": 5},
    {"sku": "SKU-102", "warehouse": "Юг", "quantity": 0},
    {"sku": "SKU-103", "warehouse": "Север", "quantity": 0},
    {"sku": "SKU-103", "warehouse": "Юг", "quantity": 4},
)

logger = get_process_logger(
    process_name="seed",
    log_dir=settings.log_dir,
    log_level=settings.log_level,
)


async def load_seed_data(session: AsyncSession) -> None:
    await session.execute(
        insert(Product)
        .values(list(PRODUCTS))
        .on_conflict_do_nothing(index_elements=[Product.sku])
    )
    await session.execute(
        insert(Warehouse)
        .values(list(WAREHOUSES))
        .on_conflict_do_nothing(index_elements=[Warehouse.name])
    )

    product_rows = await session.execute(
        select(Product.sku, Product.id).where(
            Product.sku.in_([product["sku"] for product in PRODUCTS])
        )
    )
    warehouse_rows = await session.execute(
        select(Warehouse.name, Warehouse.id).where(
            Warehouse.name.in_([warehouse["name"] for warehouse in WAREHOUSES])
        )
    )

    product_ids = dict(product_rows.all())
    warehouse_ids = dict(warehouse_rows.all())

    inventory_rows = [
        {
            "product_id": product_ids[item["sku"]],
            "warehouse_id": warehouse_ids[item["warehouse"]],
            "physical_quantity": item["quantity"],
            "reserved_quantity": 0,
        }
        for item in INITIAL_STOCK
    ]
    await session.execute(
        insert(Inventory)
        .values(inventory_rows)
        .on_conflict_do_nothing(
            index_elements=[Inventory.product_id, Inventory.warehouse_id]
        )
    )

    stock_event_rows = [
        {
            "event_type": StockEventType.RECEIPT,
            "product_id": product_ids[item["sku"]],
            "product_sku": item["sku"],
            "quantity": item["quantity"],
            "destination_warehouse_id": warehouse_ids[item["warehouse"]],
            "source_label": "Поставка",
            "destination_label": item["warehouse"],
            "reference_type": "seed",
            "idempotency_key": f"seed:{item['sku']}:{item['warehouse']}",
        }
        for item in INITIAL_STOCK
        if item["quantity"] > 0
    ]
    await session.execute(
        insert(StockEvent)
        .values(stock_event_rows)
        .on_conflict_do_nothing(index_elements=[StockEvent.idempotency_key])
    )


async def seed_database() -> None:
    async with async_session_factory() as session:
        async with session.begin():
            await load_seed_data(session)
    logger.info("Test data loaded")


async def main() -> None:
    try:
        await seed_database()
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
