from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.writeoff import WriteOffCreate, WriteOffResponse
from app.service.writeoff import write_off_stock

router = APIRouter(prefix="/write-offs", tags=["write-offs"])


@router.post(
    "",
    response_model=WriteOffResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_write_off(
    data: WriteOffCreate,
    session: AsyncSession = Depends(get_session),
) -> WriteOffResponse:
    return await write_off_stock(session=session, data=data)
