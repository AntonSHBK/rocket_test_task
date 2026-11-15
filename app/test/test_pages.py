from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    ("path", "page", "heading", "stylesheet", "script"),
    [
        ("/", "inventory", "Остатки", "inventory.css", "inventory.js"),
        (
            "/warehouses",
            "warehouses",
            "Склады и перемещения",
            "warehouses.css",
            "warehouses.js",
        ),
        (
            "/operations",
            "operations",
            "Операции",
            "operations.css",
            "operations.js",
        ),
    ],
)
def test_page_is_rendered_with_own_assets(
    client: TestClient,
    path: str,
    page: str,
    heading: str,
    stylesheet: str,
    script: str,
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert f"<h1>{heading}</h1>" in response.text
    assert f'data-active-page="{page}"' in response.text
    assert response.text.count('aria-current="page"') == 1
    assert "<header" in response.text
    assert "<footer" in response.text
    assert "data-notification-region" in response.text
    assert "/static/css/components.css" in response.text
    assert f"/static/css/{stylesheet}" in response.text
    assert f"/static/js/{script}" in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/static/css/base.css",
        "/static/css/components.css",
        "/static/css/inventory.css",
        "/static/css/warehouses.css",
        "/static/css/operations.css",
        "/static/js/api.js",
        "/static/js/common.js",
        "/static/js/inventory.js",
        "/static/js/warehouses.js",
        "/static/js/operations.js",
    ],
)
def test_static_asset_is_available(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200


def test_inventory_page_contains_stock_and_receipt_controls(
    client: TestClient,
) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'data-inventory-table' in response.text
    assert 'data-summary-physical' in response.text
    assert 'data-transit-warehouses' in response.text
    assert 'data-transit-fbo' in response.text
    assert 'data-transit-fbs' in response.text
    assert 'data-receipt-form' in response.text
    assert 'id="receipt-product"' in response.text
    assert 'id="receipt-warehouse"' in response.text
    assert 'id="receipt-quantity"' in response.text
    assert 'data-write-off-form' in response.text
    assert 'id="write-off-product"' in response.text
    assert 'id="write-off-warehouse"' in response.text
    assert 'id="write-off-quantity"' in response.text
    assert 'id="write-off-reason"' in response.text
    assert 'data-write-off-stock-available' in response.text
    assert 'data-write-off-stock-reserved' in response.text
    assert 'data-warehouse-filter-toggle' in response.text
    assert 'data-warehouse-filter-all' in response.text
    assert 'data-warehouse-filter-active' in response.text
    assert 'data-warehouse-filter-list' in response.text
    assert '/static/js/api.js' in response.text


def test_inventory_script_supports_warehouse_selection_presets(
    client: TestClient,
) -> None:
    response = client.get("/static/js/inventory.js")

    assert response.status_code == 200
    assert 'let warehouseFilterMode = "active"' in response.text
    assert 'warehouseFilterMode = "all"' in response.text
    assert 'warehouseFilterMode = "active"' in response.text
    assert "selectedWarehouseIds" in response.text
    assert "renderInventoryTable();" in response.text


def test_inventory_table_totals_use_selected_warehouses(
    client: TestClient,
) -> None:
    response = client.get("/static/js/inventory.js")

    assert response.status_code == 200
    assert "function calculateSelectedWarehouseTotals(item)" in response.text
    assert "selectedWarehouseIds.has(Number(stock.warehouse_id))" in response.text
    assert "appendStockMetrics(totalsCell, calculateSelectedWarehouseTotals(item))" in response.text


def test_inventory_summary_uses_selected_warehouses(
    client: TestClient,
) -> None:
    page_response = client.get("/")
    script_response = client.get("/static/js/inventory.js")

    assert page_response.status_code == 200
    assert "Склады: актуальные" in page_response.text
    assert script_response.status_code == 200
    assert "const selectedTotals = calculateSelectedWarehouseTotals(item)" in script_response.text
    assert "renderSummary(currentInventory);" in script_response.text


def test_inventory_receipt_requires_confirmation(
    client: TestClient,
) -> None:
    response = client.get("/static/js/inventory.js")

    assert response.status_code == 200
    assert "const confirmed = window.confirm(" in response.text
    assert "Оформить приход?" in response.text
    assert "Количество:" in response.text
    assert "if (!confirmed)" in response.text


def test_inventory_write_off_uses_api_confirmation_and_refresh(
    client: TestClient,
) -> None:
    response = client.get("/static/js/inventory.js")

    assert response.status_code == 200
    assert 'api.post("/api/write-offs"' in response.text
    assert "Оформить списание?" in response.text
    assert "Причина:" in response.text
    assert "createWriteOffKey()" in response.text
    assert "renderWriteOffStockPreview()" in response.text
    assert "writeOffQuantityInput.max = String(available)" in response.text
    assert "await loadInventory();" in response.text


def test_warehouses_page_contains_management_and_transfer_controls(
    client: TestClient,
) -> None:
    response = client.get("/warehouses")

    assert response.status_code == 200
    assert 'data-warehouse-create-form' in response.text
    assert 'data-warehouse-list' in response.text
    assert 'data-warehouse-archive-controls' in response.text
    assert 'data-toggle-warehouse-archive' in response.text
    assert 'data-transfer-form' in response.text
    assert 'data-transfer-list' in response.text
    assert 'id="transfer-product"' in response.text
    assert 'id="transfer-source"' in response.text
    assert 'id="transfer-destination"' in response.text
    assert 'id="transfer-quantity"' in response.text


def test_warehouse_script_warns_about_stock_and_supports_restore(
    client: TestClient,
) -> None:
    response = client.get("/static/js/warehouses.js")

    assert response.status_code == 200
    assert "physicalQuantity > 0" in response.text
    assert "Подтвердить архивацию?" in response.text
    assert '"restore-warehouse"' in response.text
    assert "/restore`" in response.text


def test_warehouse_list_hides_and_reveals_archived_warehouses(
    client: TestClient,
) -> None:
    response = client.get("/static/js/warehouses.js")

    assert response.status_code == 200
    assert "let showArchivedWarehouses = false" in response.text
    assert "const activeWarehouses = warehouses.filter" in response.text
    assert "const archivedWarehouses = warehouses.filter" in response.text
    assert '"Скрыть архив"' in response.text
    assert "`Показать архив (${archivedWarehouses.length})`" in response.text
    assert "showArchivedWarehouses = !showArchivedWarehouses" in response.text


def test_warehouse_list_does_not_render_internal_ids(
    client: TestClient,
) -> None:
    response = client.get("/static/js/warehouses.js")

    assert response.status_code == 200
    assert '"warehouse-id"' not in response.text
    assert "`ID ${warehouse.id}`" not in response.text


def test_warehouse_table_headers_and_cells_are_centered(
    client: TestClient,
) -> None:
    response = client.get("/static/css/warehouses.css")

    assert response.status_code == 200
    assert ".warehouse-table th" in response.text
    assert ".warehouse-table td" in response.text
    assert "text-align: center" in response.text
    assert "vertical-align: middle" in response.text


def test_warehouse_stock_and_actions_are_centered(
    client: TestClient,
) -> None:
    response = client.get("/static/css/warehouses.css")

    assert response.status_code == 200
    assert "justify-items: center" in response.text
    assert ".warehouse-actions .actions" in response.text
    assert "justify-content: center" in response.text


def test_warehouse_and_transfer_creation_require_confirmation(
    client: TestClient,
) -> None:
    response = client.get("/static/js/warehouses.js")

    assert response.status_code == 200
    assert "Создать склад?" in response.text
    assert "Название:" in response.text
    assert "Создать перемещение?" in response.text
    assert "Со склада:" in response.text
    assert "На склад:" in response.text
    assert response.text.count("const confirmed = window.confirm(") >= 3


def test_api_client_supports_warehouse_mutation_methods(
    client: TestClient,
) -> None:
    response = client.get("/static/js/api.js")

    assert response.status_code == 200
    assert "patch(path, body)" in response.text
    assert "remove(path)" in response.text


def test_api_client_handles_insufficient_stock_details(
    client: TestClient,
) -> None:
    response = client.get("/static/js/api.js")

    assert response.status_code == 200
    assert 'error?.code === "INSUFFICIENT_STOCK"' in response.text
    assert "Недостаточно товара на выбранном складе" in response.text
    assert "other_warehouses" in response.text


def test_common_ui_exposes_repeated_action_guard(
    client: TestClient,
) -> None:
    response = client.get("/static/js/common.js")

    assert response.status_code == 200
    assert "function isButtonLoading(button)" in response.text
    assert "isButtonLoading," in response.text


def test_operations_page_contains_fbs_fbo_and_history_controls(
    client: TestClient,
) -> None:
    response = client.get("/operations")

    assert response.status_code == 200
    assert 'data-fbs-form' in response.text
    assert 'data-fbs-stock-preview' in response.text
    assert 'data-fbs-stock-available' in response.text
    assert 'data-fbs-stock-reserved' in response.text
    assert 'data-fbo-form' in response.text
    assert 'data-fbo-stock-preview' in response.text
    assert 'data-fbo-stock-available' in response.text
    assert 'data-fbo-stock-reserved' in response.text
    assert 'data-fbs-active' in response.text
    assert 'data-fbs-completed' in response.text
    assert 'data-fbo-active' in response.text
    assert 'data-fbo-completed' in response.text
    assert 'data-history-filter' in response.text
    assert 'data-history-list' in response.text
    assert 'id="history-sku"' in response.text
    assert 'id="history-event-type"' in response.text


def test_operations_script_loads_inventory_for_fbs_stock_preview(
    client: TestClient,
) -> None:
    response = client.get("/static/js/operations.js")

    assert response.status_code == 200
    assert 'api.get("/api/inventory")' in response.text
    assert "function renderFbsStockPreview()" in response.text
    assert "warehouseStock?.available" in response.text
    assert "warehouseStock?.reserved" in response.text
    assert "function renderFboStockPreview()" in response.text


def test_operations_history_displays_write_off_in_russian(
    client: TestClient,
) -> None:
    page_response = client.get("/operations")
    script_response = client.get("/static/js/operations.js")

    assert page_response.status_code == 200
    assert '<option value="WRITE_OFF">Списание</option>' in page_response.text
    assert script_response.status_code == 200
    assert 'WRITE_OFF: "Списание"' in script_response.text
    assert '"Основание"' not in script_response.text
    assert "history-reference" not in script_response.text


def test_operations_supports_fbs_delivery_confirmation(
    client: TestClient,
) -> None:
    page_response = client.get("/operations")
    script_response = client.get("/static/js/operations.js")

    assert page_response.status_code == 200
    assert '<option value="FBS_DELIVERED">Доставка FBS</option>' in page_response.text
    assert script_response.status_code == 200
    assert 'FBS_DELIVERED: "Доставка FBS"' in script_response.text
    assert 'DELIVERED: ["Доставлен"' in script_response.text
    assert 'createActionButton("Подтвердить доставку", "fbs", "deliver"' in script_response.text
    assert '"fbs:deliver": `/api/fbs/reservations/${identifier}/deliver`' in script_response.text
    assert '["RESERVED", "SHIPPED"].includes(reservation.status)' in script_response.text
    assert '["CANCELLED", "DELIVERED"].includes(reservation.status)' in script_response.text


def test_operations_creation_requires_confirmation(
    client: TestClient,
) -> None:
    response = client.get("/static/js/operations.js")

    assert response.status_code == 200
    assert "Создать резерв FBS?" in response.text
    assert "Заказ: ${orderReference}" in response.text
    assert "Создать поставку FBO?" in response.text
    assert "Маркетплейс: ${destination}" in response.text


def test_operations_status_transitions_require_confirmation(
    client: TestClient,
) -> None:
    response = client.get("/static/js/operations.js")

    assert response.status_code == 200
    assert '"fbs:ship": `Отправить резерв FBS' in response.text
    assert '"fbs:cancel": `Отменить резерв FBS' in response.text
    assert '"fbs:deliver": `Подтвердить доставку заказа FBS' in response.text
    assert '"fbo:ship": `Отправить поставку FBO' in response.text
    assert '"fbo:receive": `Подтвердить приёмку поставки FBO' in response.text
    assert "!window.confirm(confirmationMessage)" in response.text
