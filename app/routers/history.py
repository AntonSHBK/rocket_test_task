from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import StockEventType
from app.schemas.history import StockEventResponse
from app.service.history import list_stock_events

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[StockEventResponse])
async def get_stock_history(
    event_type: StockEventType | None = Query(default=None),
    sku: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[StockEventResponse]:
    return await list_stock_events(
        session=session,
        event_type=event_type,
        sku=sku,
        limit=limit,
        offset=offset,
    )
