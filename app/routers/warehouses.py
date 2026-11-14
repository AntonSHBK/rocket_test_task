from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.warehouse import (
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)
from app.service.warehouse import (
    archive_warehouse,
    create_warehouse,
    list_warehouses,
    rename_warehouse,
    restore_warehouse,
)

router = APIRouter(prefix="/warehouses", tags=["warehouses"])


@router.get("", response_model=list[WarehouseResponse])
async def get_warehouses(
    include_archived: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> list[WarehouseResponse]:
    return await list_warehouses(
        session=session,
        include_archived=include_archived,
    )


@router.post(
    "",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_warehouse(
    data: WarehouseCreate,
    session: AsyncSession = Depends(get_session),
) -> WarehouseResponse:
    return await create_warehouse(session=session, data=data)


@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
async def update_warehouse(
    warehouse_id: int,
    data: WarehouseUpdate,
    session: AsyncSession = Depends(get_session),
) -> WarehouseResponse:
    return await rename_warehouse(
        session=session,
        warehouse_id=warehouse_id,
        data=data,
    )


@router.delete("/{warehouse_id}", response_model=WarehouseResponse)
async def delete_warehouse(
    warehouse_id: int,
    session: AsyncSession = Depends(get_session),
) -> WarehouseResponse:
    return await archive_warehouse(
        session=session,
        warehouse_id=warehouse_id,
    )


@router.post("/{warehouse_id}/restore", response_model=WarehouseResponse)
async def restore_archived_warehouse(
    warehouse_id: int,
    session: AsyncSession = Depends(get_session),
) -> WarehouseResponse:
    return await restore_warehouse(
        session=session,
        warehouse_id=warehouse_id,
    )
