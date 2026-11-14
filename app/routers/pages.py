from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template"

templates = Jinja2Templates(directory=TEMPLATE_DIR)
router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse, name="inventory_page")
async def inventory_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={"active_page": "inventory"},
    )


@router.get(
    "/warehouses",
    response_class=HTMLResponse,
    name="warehouses_page",
)
async def warehouses_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="warehouses.html",
        context={"active_page": "warehouses"},
    )


@router.get(
    "/operations",
    response_class=HTMLResponse,
    name="operations_page",
)
async def operations_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="operations.html",
        context={"active_page": "operations"},
    )
