from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.fbs import FBSReservationCreate, FBSReservationResponse
from app.service.fbs import (
    cancel_reservation,
    create_reservation,
    list_reservations,
    ship_reservation,
)

router = APIRouter(prefix="/fbs/reservations", tags=["fbs"])


@router.get("", response_model=list[FBSReservationResponse])
async def get_reservations(
    session: AsyncSession = Depends(get_session),
) -> list[FBSReservationResponse]:
    return await list_reservations(session)


@router.post(
    "",
    response_model=FBSReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_reservation(
    data: FBSReservationCreate,
    session: AsyncSession = Depends(get_session),
) -> FBSReservationResponse:
    return await create_reservation(session=session, data=data)


@router.post("/{reservation_id}/cancel", response_model=FBSReservationResponse)
async def cancel_fbs_reservation(
    reservation_id: int,
    session: AsyncSession = Depends(get_session),
) -> FBSReservationResponse:
    return await cancel_reservation(
        session=session,
        reservation_id=reservation_id,
    )


@router.post("/{reservation_id}/ship", response_model=FBSReservationResponse)
async def ship_fbs_reservation(
    reservation_id: int,
    session: AsyncSession = Depends(get_session),
) -> FBSReservationResponse:
    return await ship_reservation(
        session=session,
        reservation_id=reservation_id,
    )
