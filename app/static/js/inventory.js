const inventoryPage = document.querySelector("[data-page='inventory']");

if (inventoryPage) {
    const api = window.CheckStockAPI;
    const ui = window.CheckStockUI;
    const tableRegion = inventoryPage.querySelector("[data-inventory-table]");
    const refreshButton = inventoryPage.querySelector("[data-refresh-inventory]");
    const receiptForm = inventoryPage.querySelector("[data-receipt-form]");
    const productSelect = inventoryPage.querySelector("#receipt-product");
    const warehouseSelect = inventoryPage.querySelector("#receipt-warehouse");
    const quantityInput = inventoryPage.querySelector("#receipt-quantity");
    const submitButton = receiptForm.querySelector("button[type='submit']");
    const writeOffForm = inventoryPage.querySelector("[data-write-off-form]");
    const writeOffProductSelect = inventoryPage.querySelector("#write-off-product");
    const writeOffWarehouseSelect = inventoryPage.querySelector("#write-off-warehouse");
    const writeOffQuantityInput = inventoryPage.querySelector("#write-off-quantity");
    const writeOffReasonInput = inventoryPage.querySelector("#write-off-reason");
    const writeOffSubmitButton = writeOffForm.querySelector("button[type='submit']");
    const writeOffStockPreview = inventoryPage.querySelector("[data-write-off-stock-preview]");
    const writeOffAvailable = inventoryPage.querySelector("[data-write-off-stock-available]");
    const writeOffReserved = inventoryPage.querySelector("[data-write-off-stock-reserved]");
    const updatedAt = inventoryPage.querySelector("[data-updated-at]");
    const warehouseFilter = inventoryPage.querySelector("[data-warehouse-filter]");
    const warehouseFilterToggle = inventoryPage.querySelector("[data-warehouse-filter-toggle]");
    const warehouseFilterLabel = inventoryPage.querySelector("[data-warehouse-filter-label]");
    const warehouseFilterMenu = inventoryPage.querySelector("[data-warehouse-filter-menu]");
    const warehouseFilterAll = inventoryPage.querySelector("[data-warehouse-filter-all]");
    const warehouseFilterActive = inventoryPage.querySelector("[data-warehouse-filter-active]");
    const warehouseFilterList = inventoryPage.querySelector("[data-warehouse-filter-list]");
    const numberFormatter = new Intl.NumberFormat("ru-RU");
    let receiptKey = createReceiptKey();
    let writeOffKey = createWriteOffKey();
    let currentInventory = [];
    let inventoryWarehouses = [];
    let selectedWarehouseIds = new Set();
    let warehouseFilterMode = "active";

    function createReceiptKey() {
        const identifier = window.crypto?.randomUUID?.()
            || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        return `receipt:web:${identifier}`;
    }

    function createWriteOffKey() {
        const identifier = window.crypto?.randomUUID?.()
            || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        return `write-off:web:${identifier}`;
    }

    function createElement(tagName, className = "", text = null) {
        const element = document.createElement(tagName);
        if (className) {
            element.className = className;
        }
        if (text !== null) {
            element.textContent = String(text);
        }
        return element;
    }

    function formatQuantity(value) {
        return numberFormatter.format(Number(value) || 0);
    }

    function setText(selector, value) {
        const element = inventoryPage.querySelector(selector);
        if (element) {
            element.textContent = formatQuantity(value);
        }
    }

    function calculateSummary(inventory) {
        return inventory.reduce(
            (summary, item) => {
                const selectedTotals = calculateSelectedWarehouseTotals(item);
                summary.physical += selectedTotals.physical;
                summary.reserved += selectedTotals.reserved;
                summary.available += selectedTotals.available;
                summary.betweenWarehouses += item.in_transit.between_warehouses;
                summary.toMarketplace += item.in_transit.to_marketplace;
                summary.toCustomer += item.in_transit.to_customer;
                summary.inTransit += item.in_transit.total;
                return summary;
            },
            {
                physical: 0,
                reserved: 0,
                available: 0,
                betweenWarehouses: 0,
                toMarketplace: 0,
                toCustomer: 0,
                inTransit: 0,
            },
        );
    }

    function renderSummary(inventory) {
        const summary = calculateSummary(inventory);
        setText("[data-summary-physical]", summary.physical);
        setText("[data-summary-reserved]", summary.reserved);
        setText("[data-summary-available]", summary.available);
        setText("[data-summary-transit]", summary.inTransit);
        setText("[data-transit-warehouses]", summary.betweenWarehouses);
        setText("[data-transit-fbo]", summary.toMarketplace);
        setText("[data-transit-fbs]", summary.toCustomer);
    }

    function getWarehouses(inventory) {
        const warehouses = new Map();
        inventory.forEach((item) => {
            item.warehouses.forEach((warehouse) => {
                warehouses.set(warehouse.warehouse_id, warehouse);
            });
        });
        return [...warehouses.values()].sort(
            (left, right) => left.warehouse_id - right.warehouse_id,
        );
    }

    function getWarehouseIds(warehouses) {
        return warehouses.map((warehouse) => Number(warehouse.warehouse_id));
    }

    function selectionMatches(warehouseIds) {
        return selectedWarehouseIds.size === warehouseIds.length
            && warehouseIds.every((warehouseId) => selectedWarehouseIds.has(warehouseId));
    }

    function syncWarehouseSelection() {
        const availableIds = new Set(getWarehouseIds(inventoryWarehouses));
        if (warehouseFilterMode === "all") {
            selectedWarehouseIds = new Set(availableIds);
            return;
        }
        if (warehouseFilterMode === "active") {
            selectedWarehouseIds = new Set(
                getWarehouseIds(inventoryWarehouses.filter((warehouse) => warehouse.is_active)),
            );
            return;
        }
        selectedWarehouseIds = new Set(
            [...selectedWarehouseIds].filter((warehouseId) => availableIds.has(warehouseId)),
        );
    }

    function updateWarehouseFilterMode() {
        const allIds = getWarehouseIds(inventoryWarehouses);
        const activeIds = getWarehouseIds(
            inventoryWarehouses.filter((warehouse) => warehouse.is_active),
        );
        if (selectionMatches(allIds)) {
            warehouseFilterMode = "all";
        } else if (selectionMatches(activeIds)) {
            warehouseFilterMode = "active";
        } else {
            warehouseFilterMode = "custom";
        }
    }

    function renderWarehouseFilter() {
        const allIds = getWarehouseIds(inventoryWarehouses);
        const activeIds = getWarehouseIds(
            inventoryWarehouses.filter((warehouse) => warehouse.is_active),
        );
        const selectedActiveCount = activeIds.filter(
            (warehouseId) => selectedWarehouseIds.has(warehouseId),
        ).length;

        warehouseFilterAll.checked = selectionMatches(allIds);
        warehouseFilterAll.indeterminate = selectedWarehouseIds.size > 0
            && !warehouseFilterAll.checked;
        warehouseFilterActive.checked = selectionMatches(activeIds);
        warehouseFilterActive.indeterminate = selectedActiveCount > 0
            && !warehouseFilterActive.checked;
        warehouseFilterToggle.disabled = inventoryWarehouses.length === 0;

        if (warehouseFilterAll.checked) {
            warehouseFilterLabel.textContent = "Склады: все";
        } else if (warehouseFilterActive.checked) {
            warehouseFilterLabel.textContent = "Склады: актуальные";
        } else {
            warehouseFilterLabel.textContent = `Склады: ${selectedWarehouseIds.size} из ${allIds.length}`;
        }

        warehouseFilterList.replaceChildren();
        inventoryWarehouses.forEach((warehouse) => {
            const label = createElement("label", "warehouse-filter__option");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = warehouse.warehouse_id;
            checkbox.checked = selectedWarehouseIds.has(Number(warehouse.warehouse_id));
            checkbox.dataset.warehouseFilterItem = "";
            label.append(
                checkbox,
                createElement("span", "", warehouse.warehouse_name),
                createElement(
                    "span",
                    "warehouse-filter__state",
                    warehouse.is_active ? "" : "Архив",
                ),
            );
            warehouseFilterList.append(label);
        });
    }

    function setWarehouseFilterOpen(isOpen) {
        warehouseFilterMenu.hidden = !isOpen;
        warehouseFilterToggle.setAttribute("aria-expanded", String(isOpen));
    }

    function applyWarehouseFilter() {
        updateWarehouseFilterMode();
        renderWarehouseFilter();
        renderSummary(currentInventory);
        renderInventoryTable();
    }

    function appendStockMetrics(cell, stock) {
        const metrics = createElement("div", "stock-metrics");
        const values = [
            ["Физически", stock.physical, ""],
            ["В резерве", stock.reserved, ""],
            ["Доступно", stock.available, "stock-metric--available"],
        ];

        values.forEach(([label, value, modifier]) => {
            const row = createElement("span", `stock-metric ${modifier}`.trim());
            row.append(
                createElement("span", "", label),
                createElement("strong", "", formatQuantity(value)),
            );
            metrics.append(row);
        });
        cell.append(metrics);
    }

    function appendTransitMetrics(cell, transit) {
        const metrics = createElement("div", "stock-metrics transit-metrics");
        metrics.append(createElement("strong", "transit-total", formatQuantity(transit.total)));

        const values = [
            ["Между складами", transit.between_warehouses],
            ["FBO", transit.to_marketplace],
            ["FBS", transit.to_customer],
        ];
        values.forEach(([label, value]) => {
            const row = createElement("span", "stock-metric");
            row.append(
                createElement("span", "", label),
                createElement("strong", "", formatQuantity(value)),
            );
            metrics.append(row);
        });
        cell.append(metrics);
    }

    function calculateSelectedWarehouseTotals(item) {
        return item.warehouses.reduce(
            (totals, stock) => {
                if (!selectedWarehouseIds.has(Number(stock.warehouse_id))) {
                    return totals;
                }
                totals.physical += Number(stock.physical) || 0;
                totals.reserved += Number(stock.reserved) || 0;
                totals.available += Number(stock.available) || 0;
                return totals;
            },
            {physical: 0, reserved: 0, available: 0},
        );
    }

    function renderInventoryTable() {
        tableRegion.replaceChildren();
        tableRegion.setAttribute("aria-busy", "false");

        if (!currentInventory.length) {
            tableRegion.append(createElement("div", "empty-state", "Товары пока не добавлены"));
            return;
        }

        const warehouses = inventoryWarehouses.filter(
            (warehouse) => selectedWarehouseIds.has(Number(warehouse.warehouse_id)),
        );
        const container = createElement("div", "table-container inventory-table-container");
        const table = createElement("table", "table inventory-table");
        const head = document.createElement("thead");
        const headRow = document.createElement("tr");
        const productHeading = createElement("th", "product-cell", "Товар");
        productHeading.scope = "col";
        headRow.append(productHeading);

        warehouses.forEach((warehouse) => {
            const heading = createElement("th", "warehouse-heading");
            heading.scope = "col";
            heading.append(createElement("span", "warehouse-heading__name", warehouse.warehouse_name));
            if (!warehouse.is_active) {
                heading.append(createElement("span", "warehouse-state", "Архивный склад"));
            }
            headRow.append(heading);
        });

        const totalsHeading = createElement("th", "", "Всего на складах");
        totalsHeading.scope = "col";
        const transitHeading = createElement("th", "", "В пути");
        transitHeading.scope = "col";
        headRow.append(totalsHeading, transitHeading);
        head.append(headRow);

        const body = document.createElement("tbody");
        currentInventory.forEach((item) => {
            const row = document.createElement("tr");
            const productCell = createElement("td", "product-cell");
            productCell.append(
                createElement("span", "product-name", item.product.name),
                createElement("span", "product-sku", item.product.sku),
            );
            row.append(productCell);

            const stockByWarehouse = new Map(
                item.warehouses.map((stock) => [stock.warehouse_id, stock]),
            );
            warehouses.forEach((warehouse) => {
                const stock = stockByWarehouse.get(warehouse.warehouse_id) || {
                    physical: 0,
                    reserved: 0,
                    available: 0,
                };
                const cell = document.createElement("td");
                appendStockMetrics(cell, stock);
                row.append(cell);
            });

            const totalsCell = document.createElement("td");
            appendStockMetrics(totalsCell, calculateSelectedWarehouseTotals(item));
            const transitCell = document.createElement("td");
            appendTransitMetrics(transitCell, item.in_transit);
            row.append(totalsCell, transitCell);
            body.append(row);
        });

        table.append(head, body);
        container.append(table);
        tableRegion.append(container);
    }

    function fillSelect(select, items, placeholder, valueKey, labelBuilder) {
        const selectedValue = select.value;
        select.replaceChildren(createElement("option", "", placeholder));
        select.firstElementChild.value = "";

        items.forEach((item) => {
            const option = createElement("option", "", labelBuilder(item));
            option.value = item[valueKey];
            select.append(option);
        });

        if ([...select.options].some((option) => option.value === selectedValue)) {
            select.value = selectedValue;
        }
    }

    function renderFormOptions(products, warehouses) {
        fillSelect(
            productSelect,
            products,
            "Выберите товар",
            "sku",
            (product) => `${product.sku} — ${product.name}`,
        );
        fillSelect(
            warehouseSelect,
            warehouses,
            "Выберите склад",
            "id",
            (warehouse) => warehouse.name,
        );
        fillSelect(
            writeOffProductSelect,
            products,
            "Выберите товар",
            "sku",
            (product) => `${product.sku} — ${product.name}`,
        );
        fillSelect(
            writeOffWarehouseSelect,
            warehouses,
            "Выберите склад",
            "id",
            (warehouse) => warehouse.name,
        );
        renderWriteOffStockPreview();
    }

    function renderWriteOffStockPreview() {
        const sku = writeOffProductSelect.value;
        const warehouseId = Number(writeOffWarehouseSelect.value);
        if (!sku || !warehouseId) {
            writeOffStockPreview.hidden = true;
            writeOffAvailable.textContent = "0";
            writeOffReserved.textContent = "0";
            writeOffQuantityInput.removeAttribute("max");
            return;
        }

        const productStock = currentInventory.find((item) => item.product.sku === sku);
        const warehouseStock = productStock?.warehouses.find(
            (stock) => Number(stock.warehouse_id) === warehouseId,
        );
        const available = Number(warehouseStock?.available) || 0;
        const reserved = Number(warehouseStock?.reserved) || 0;
        writeOffAvailable.textContent = formatQuantity(available);
        writeOffReserved.textContent = formatQuantity(reserved);
        writeOffQuantityInput.max = String(available);
        writeOffStockPreview.hidden = false;
    }

    function renderLoadError(error) {
        tableRegion.setAttribute("aria-busy", "false");
        tableRegion.replaceChildren(
            createElement(
                "div",
                "empty-state inventory-error",
                error.message || "Не удалось загрузить остатки",
            ),
        );
    }

    async function loadInventory({notify = false} = {}) {
        ui.setButtonLoading(refreshButton, true, "Обновление...");
        try {
            const [inventory, products, warehouses] = await Promise.all([
                api.get("/api/inventory"),
                api.get("/api/products"),
                api.get("/api/warehouses?include_archived=false"),
            ]);
            currentInventory = inventory;
            inventoryWarehouses = getWarehouses(inventory);
            syncWarehouseSelection();
            renderSummary(inventory);
            renderWarehouseFilter();
            renderInventoryTable();
            renderFormOptions(products, warehouses);
            updatedAt.textContent = `Обновлено ${new Date().toLocaleTimeString("ru-RU", {
                hour: "2-digit",
                minute: "2-digit",
            })}`;
            if (notify) {
                ui.showNotification("Данные обновлены", "success", 2500);
            }
        } catch (error) {
            renderLoadError(error);
            ui.showNotification(error.message || "Не удалось загрузить данные", "error");
        } finally {
            ui.setButtonLoading(refreshButton, false);
        }
    }

    refreshButton.addEventListener("click", () => loadInventory({notify: true}));

    writeOffProductSelect.addEventListener("change", renderWriteOffStockPreview);
    writeOffWarehouseSelect.addEventListener("change", renderWriteOffStockPreview);

    warehouseFilterToggle.addEventListener("click", () => {
        setWarehouseFilterOpen(warehouseFilterMenu.hidden);
    });

    warehouseFilterAll.addEventListener("change", () => {
        warehouseFilterMode = warehouseFilterAll.checked ? "all" : "custom";
        selectedWarehouseIds = warehouseFilterAll.checked
            ? new Set(getWarehouseIds(inventoryWarehouses))
            : new Set();
        applyWarehouseFilter();
    });

    warehouseFilterActive.addEventListener("change", () => {
        const activeIds = getWarehouseIds(
            inventoryWarehouses.filter((warehouse) => warehouse.is_active),
        );
        warehouseFilterMode = warehouseFilterActive.checked ? "active" : "custom";
        selectedWarehouseIds = warehouseFilterActive.checked
            ? new Set(activeIds)
            : new Set(
                [...selectedWarehouseIds].filter((warehouseId) => !activeIds.includes(warehouseId)),
            );
        applyWarehouseFilter();
    });

    warehouseFilterList.addEventListener("change", (event) => {
        const checkbox = event.target.closest("input[data-warehouse-filter-item]");
        if (!checkbox) {
            return;
        }
        const warehouseId = Number(checkbox.value);
        if (checkbox.checked) {
            selectedWarehouseIds.add(warehouseId);
        } else {
            selectedWarehouseIds.delete(warehouseId);
        }
        warehouseFilterMode = "custom";
        applyWarehouseFilter();
    });

    document.addEventListener("click", (event) => {
        if (!warehouseFilter.contains(event.target)) {
            setWarehouseFilterOpen(false);
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !warehouseFilterMenu.hidden) {
            setWarehouseFilterOpen(false);
            warehouseFilterToggle.focus();
        }
    });

    receiptForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (ui.isButtonLoading(submitButton) || !receiptForm.reportValidity()) {
            return;
        }

        const quantity = Number(quantityInput.value);
        const productLabel = productSelect.selectedOptions[0]?.textContent || productSelect.value;
        const warehouseLabel = warehouseSelect.selectedOptions[0]?.textContent || warehouseSelect.value;
        const confirmed = window.confirm(
            `Оформить приход?\n\nТовар: ${productLabel}\nСклад: ${warehouseLabel}\nКоличество: ${formatQuantity(quantity)} шт.`,
        );
        if (!confirmed) {
            return;
        }

        ui.setButtonLoading(submitButton, true, "Сохранение...");
        try {
            const receipt = await api.post("/api/receipts", {
                sku: productSelect.value,
                warehouse_id: Number(warehouseSelect.value),
                quantity,
                idempotency_key: receiptKey,
            });
            const resultMessage = receipt.created
                ? `Приход ${receipt.product.sku} на ${receipt.received_quantity} шт. оформлен`
                : "Этот приход уже был оформлен ранее";
            ui.showNotification(resultMessage, receipt.created ? "success" : "info");
            receiptKey = createReceiptKey();
            quantityInput.value = "";
            await loadInventory();
        } catch (error) {
            ui.showNotification(error.message || "Не удалось оформить приход", "error");
        } finally {
            ui.setButtonLoading(submitButton, false);
        }
    });

    writeOffForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (ui.isButtonLoading(writeOffSubmitButton) || !writeOffForm.reportValidity()) {
            return;
        }

        const quantity = Number(writeOffQuantityInput.value);
        const reason = writeOffReasonInput.value.trim();
        const productLabel = writeOffProductSelect.selectedOptions[0]?.textContent
            || writeOffProductSelect.value;
        const warehouseLabel = writeOffWarehouseSelect.selectedOptions[0]?.textContent
            || writeOffWarehouseSelect.value;
        const confirmed = window.confirm(
            `Оформить списание?\n\nТовар: ${productLabel}\nСклад: ${warehouseLabel}\nКоличество: ${formatQuantity(quantity)} шт.\nПричина: ${reason}`,
        );
        if (!confirmed) {
            return;
        }

        ui.setButtonLoading(writeOffSubmitButton, true, "Списание...");
        try {
            const writeOff = await api.post("/api/write-offs", {
                sku: writeOffProductSelect.value,
                warehouse_id: Number(writeOffWarehouseSelect.value),
                quantity,
                reason,
                idempotency_key: writeOffKey,
            });
            const resultMessage = writeOff.created
                ? `Списано ${writeOff.written_off_quantity} шт. товара ${writeOff.product.sku}`
                : "Это списание уже было оформлено ранее";
            ui.showNotification(resultMessage, writeOff.created ? "success" : "info");
            writeOffKey = createWriteOffKey();
            writeOffQuantityInput.value = "";
            writeOffReasonInput.value = "";
            await loadInventory();
        } catch (error) {
            ui.showNotification(error.message || "Не удалось оформить списание", "error");
        } finally {
            ui.setButtonLoading(writeOffSubmitButton, false);
        }
    });

    inventoryPage.setAttribute("data-ready", "true");
    loadInventory();
}
