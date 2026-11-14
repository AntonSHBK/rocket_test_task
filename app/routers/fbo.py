from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.fbo import FBOShipmentCreate, FBOShipmentResponse
from app.service.fbo import (
    create_fbo_shipment,
    list_fbo_shipments,
    receive_fbo_shipment,
    ship_fbo_shipment,
)

router = APIRouter(prefix="/fbo/shipments", tags=["fbo"])


@router.get("", response_model=list[FBOShipmentResponse])
async def get_fbo_shipments(
    session: AsyncSession = Depends(get_session),
) -> list[FBOShipmentResponse]:
    return await list_fbo_shipments(session)


@router.post(
    "",
    response_model=FBOShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_fbo_shipment(
    data: FBOShipmentCreate,
    session: AsyncSession = Depends(get_session),
) -> FBOShipmentResponse:
    return await create_fbo_shipment(session=session, data=data)


@router.post("/{shipment_id}/ship", response_model=FBOShipmentResponse)
async def send_fbo_shipment(
    shipment_id: int,
    session: AsyncSession = Depends(get_session),
) -> FBOShipmentResponse:
    return await ship_fbo_shipment(session=session, shipment_id=shipment_id)


@router.post("/{shipment_id}/receive", response_model=FBOShipmentResponse)
async def confirm_fbo_shipment(
    shipment_id: int,
    session: AsyncSession = Depends(get_session),
) -> FBOShipmentResponse:
    return await receive_fbo_shipment(session=session, shipment_id=shipment_id)
