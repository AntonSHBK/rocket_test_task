import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Inventory, Warehouse
from app.schemas.warehouse import (
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)
from app.utils.exceptions import (
    WarehouseAlreadyExistsError,
    WarehouseInactiveError,
    WarehouseNotFoundError,
)

logger = logging.getLogger("api")


def build_warehouse_response(
    warehouse: Warehouse,
    physical_quantity: int = 0,
    reserved_quantity: int = 0,
) -> WarehouseResponse:
    return WarehouseResponse(
        id=warehouse.id,
        name=warehouse.name,
        is_active=warehouse.is_active,
        archived_at=warehouse.archived_at,
        physical_quantity=physical_quantity,
        reserved_quantity=reserved_quantity,
        available_quantity=physical_quantity - reserved_quantity,
    )


def mark_warehouse_archived(
    warehouse: Warehouse,
    archived_at: datetime | None = None,
) -> None:
    if not warehouse.is_active:
        return

    warehouse.is_active = False
    warehouse.archived_at = archived_at or datetime.now(UTC)


def mark_warehouse_active(warehouse: Warehouse) -> None:
    if warehouse.is_active:
        return

    warehouse.is_active = True
    warehouse.archived_at = None


def _inventory_totals_subquery():
    return (
        select(
            Inventory.warehouse_id.label("warehouse_id"),
            func.sum(Inventory.physical_quantity).label("physical_quantity"),
            func.sum(Inventory.reserved_quantity).label("reserved_quantity"),
        )
        .group_by(Inventory.warehouse_id)
        .subquery()
    )


async def _ensure_name_available(
    session: AsyncSession,
    name: str,
    excluded_warehouse_id: int | None = None,
) -> None:
    query = select(Warehouse.id).where(func.lower(Warehouse.name) == name.lower())
    if excluded_warehouse_id is not None:
        query = query.where(Warehouse.id != excluded_warehouse_id)

    if await session.scalar(query) is not None:
        raise WarehouseAlreadyExistsError(name)


async def _get_warehouse_totals(
    session: AsyncSession,
    warehouse_id: int,
) -> tuple[int, int]:
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(Inventory.physical_quantity), 0),
                func.coalesce(func.sum(Inventory.reserved_quantity), 0),
            ).where(Inventory.warehouse_id == warehouse_id)
        )
    ).one()
    return int(row[0]), int(row[1])


async def list_warehouses(
    session: AsyncSession,
    include_archived: bool = True,
) -> list[WarehouseResponse]:
    totals = _inventory_totals_subquery()
    query = (
        select(
            Warehouse,
            func.coalesce(totals.c.physical_quantity, 0),
            func.coalesce(totals.c.reserved_quantity, 0),
        )
        .outerjoin(totals, totals.c.warehouse_id == Warehouse.id)
        .order_by(Warehouse.id)
    )
    if not include_archived:
        query = query.where(Warehouse.is_active.is_(True))

    rows = (await session.execute(query)).all()
    return [
        build_warehouse_response(
            warehouse=warehouse,
            physical_quantity=int(physical_quantity),
            reserved_quantity=int(reserved_quantity),
        )
        for warehouse, physical_quantity, reserved_quantity in rows
    ]


async def create_warehouse(
    session: AsyncSession,
    data: WarehouseCreate,
) -> WarehouseResponse:
    try:
        async with session.begin():
            await _ensure_name_available(session, data.name)
            warehouse = Warehouse(name=data.name)
            session.add(warehouse)
            await session.flush()
            response = build_warehouse_response(warehouse)
    except IntegrityError as exc:
        raise WarehouseAlreadyExistsError(data.name) from exc

    logger.info(
        "Warehouse created: warehouse_id=%s warehouse=%s",
        response.id,
        response.name,
    )
    return response


async def rename_warehouse(
    session: AsyncSession,
    warehouse_id: int,
    data: WarehouseUpdate,
) -> WarehouseResponse:
    try:
        async with session.begin():
            warehouse = await session.scalar(
                select(Warehouse)
                .where(Warehouse.id == warehouse_id)
                .with_for_update()
            )
            if warehouse is None:
                raise WarehouseNotFoundError(warehouse_id)
            if not warehouse.is_active:
                raise WarehouseInactiveError(warehouse_id)

            previous_name = warehouse.name
            await _ensure_name_available(
                session,
                data.name,
                excluded_warehouse_id=warehouse_id,
            )
            warehouse.name = data.name
            await session.flush()
            physical, reserved = await _get_warehouse_totals(session, warehouse.id)
            response = build_warehouse_response(warehouse, physical, reserved)
    except IntegrityError as exc:
        raise WarehouseAlreadyExistsError(data.name) from exc

    logger.info(
        "Warehouse renamed: warehouse_id=%s previous_name=%s warehouse=%s",
        response.id,
        previous_name,
        response.name,
    )
    return response


async def archive_warehouse(
    session: AsyncSession,
    warehouse_id: int,
) -> WarehouseResponse:
    async with session.begin():
        warehouse = await session.scalar(
            select(Warehouse)
            .where(Warehouse.id == warehouse_id)
            .with_for_update()
        )
        if warehouse is None:
            raise WarehouseNotFoundError(warehouse_id)

        archived = warehouse.is_active
        mark_warehouse_archived(warehouse)
        await session.flush()
        physical, reserved = await _get_warehouse_totals(session, warehouse.id)
        response = build_warehouse_response(warehouse, physical, reserved)

    logger.info(
        "Warehouse archived: warehouse_id=%s warehouse=%s physical=%s "
        "reserved=%s changed=%s",
        response.id,
        response.name,
        response.physical_quantity,
        response.reserved_quantity,
        archived,
    )
    return response


async def restore_warehouse(
    session: AsyncSession,
    warehouse_id: int,
) -> WarehouseResponse:
    async with session.begin():
        warehouse = await session.scalar(
            select(Warehouse)
            .where(Warehouse.id == warehouse_id)
            .with_for_update()
        )
        if warehouse is None:
            raise WarehouseNotFoundError(warehouse_id)

        restored = not warehouse.is_active
        mark_warehouse_active(warehouse)
        await session.flush()
        physical, reserved = await _get_warehouse_totals(session, warehouse.id)
        response = build_warehouse_response(warehouse, physical, reserved)

    logger.info(
        "Warehouse restored: warehouse_id=%s warehouse=%s physical=%s "
        "reserved=%s changed=%s",
        response.id,
        response.name,
        response.physical_quantity,
        response.reserved_quantity,
        restored,
    )
    return response
