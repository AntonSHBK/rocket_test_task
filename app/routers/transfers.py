from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.transfer import TransferCreate, TransferResponse
from app.service.transfer import (
    create_transfer,
    list_transfers,
    receive_transfer,
    ship_transfer,
)

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("", response_model=list[TransferResponse])
async def get_transfers(
    session: AsyncSession = Depends(get_session),
) -> list[TransferResponse]:
    return await list_transfers(session)


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_transfer(
    data: TransferCreate,
    session: AsyncSession = Depends(get_session),
) -> TransferResponse:
    return await create_transfer(session=session, data=data)


@router.post("/{transfer_id}/ship", response_model=TransferResponse)
async def send_transfer(
    transfer_id: int,
    session: AsyncSession = Depends(get_session),
) -> TransferResponse:
    return await ship_transfer(session=session, transfer_id=transfer_id)


@router.post("/{transfer_id}/receive", response_model=TransferResponse)
async def confirm_transfer_receipt(
    transfer_id: int,
    session: AsyncSession = Depends(get_session),
) -> TransferResponse:
    return await receive_transfer(session=session, transfer_id=transfer_id)
