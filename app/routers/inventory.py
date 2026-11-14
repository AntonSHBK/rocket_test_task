from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.inventory import ProductInventoryResponse
from app.service.inventory import get_inventory_snapshot

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[ProductInventoryResponse])
async def get_inventory(
    session: AsyncSession = Depends(get_session),
) -> list[ProductInventoryResponse]:
    return await get_inventory_snapshot(session)
