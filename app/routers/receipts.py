from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.inventory import ReceiptCreate, ReceiptResponse
from app.service.inventory import receive_stock

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("", response_model=ReceiptResponse)
async def create_receipt(
    receipt: ReceiptCreate,
    session: AsyncSession = Depends(get_session),
) -> ReceiptResponse:
    return await receive_stock(session=session, receipt=receipt)
