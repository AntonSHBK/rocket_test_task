from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.product import ProductResponse
from app.service.inventory import list_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
async def get_products(
    session: AsyncSession = Depends(get_session),
) -> list[ProductResponse]:
    products = await list_products(session)
    return [ProductResponse.model_validate(product) for product in products]
