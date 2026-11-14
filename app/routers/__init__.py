from fastapi import APIRouter

from app.routers.fbo import router as fbo_router
from app.routers.fbs import router as fbs_router
from app.routers.health import router as health_router
from app.routers.history import router as history_router
from app.routers.inventory import router as inventory_router
from app.routers.pages import router as pages_router
from app.routers.products import router as products_router
from app.routers.receipts import router as receipts_router
from app.routers.transfers import router as transfers_router
from app.routers.warehouses import router as warehouses_router
from app.routers.writeoffs import router as writeoffs_router

router = APIRouter()
router.include_router(pages_router)
router.include_router(health_router)

api_router = APIRouter(prefix="/api")
api_router.include_router(fbo_router)
api_router.include_router(fbs_router)
api_router.include_router(history_router)
api_router.include_router(products_router)
api_router.include_router(inventory_router)
api_router.include_router(receipts_router)
api_router.include_router(transfers_router)
api_router.include_router(warehouses_router)
api_router.include_router(writeoffs_router)

router.include_router(api_router)
