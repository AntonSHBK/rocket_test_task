const warehousesPage = document.querySelector("[data-page='warehouses']");

if (warehousesPage) {
    const api = window.CheckStockAPI;
    const ui = window.CheckStockUI;
    const refreshButton = warehousesPage.querySelector("[data-refresh-warehouses]");
    const updatedAt = warehousesPage.querySelector("[data-warehouses-updated-at]");
    const warehouseForm = warehousesPage.querySelector("[data-warehouse-create-form]");
    const warehouseNameInput = warehousesPage.querySelector("#warehouse-name");
    const warehouseSubmitButton = warehouseForm.querySelector("button[type='submit']");
    const warehouseList = warehousesPage.querySelector("[data-warehouse-list]");
    const warehouseArchiveControls = warehousesPage.querySelector("[data-warehouse-archive-controls]");
    const warehouseArchiveToggle = warehousesPage.querySelector("[data-toggle-warehouse-archive]");
    const transferForm = warehousesPage.querySelector("[data-transfer-form]");
    const productSelect = warehousesPage.querySelector("#transfer-product");
    const sourceSelect = warehousesPage.querySelector("#transfer-source");
    const destinationSelect = warehousesPage.querySelector("#transfer-destination");
    const quantityInput = warehousesPage.querySelector("#transfer-quantity");
    const transferSubmitButton = transferForm.querySelector("button[type='submit']");
    const transferList = warehousesPage.querySelector("[data-transfer-list]");
    const numberFormatter = new Intl.NumberFormat("ru-RU");
    const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "short",
        timeStyle: "short",
    });
    let transferKey = createTransferKey();
    let currentWarehouses = [];
    let showArchivedWarehouses = false;

    function createTransferKey() {
        const identifier = window.crypto?.randomUUID?.()
            || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        return `transfer:web:${identifier}`;
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

    function createButton(text, action, identifier, modifier = "button--secondary") {
        const button = createElement("button", `button button--small ${modifier}`.trim(), text);
        button.type = "button";
        button.dataset.action = action;
        button.dataset.id = identifier;
        return button;
    }

    function formatQuantity(value) {
        return numberFormatter.format(Number(value) || 0);
    }

    function formatDate(value) {
        return value ? dateFormatter.format(new Date(value)) : "—";
    }

    function createStatusBadge(text, modifier = "") {
        return createElement("span", `status-badge ${modifier}`.trim(), text);
    }

    function renderWarehouseStock(warehouse) {
        const stock = createElement("div", "warehouse-stock");
        const values = [
            ["Физически", warehouse.physical_quantity],
            ["В резерве", warehouse.reserved_quantity],
            ["Доступно", warehouse.available_quantity],
        ];
        values.forEach(([label, value]) => {
            const item = createElement("div", "warehouse-stock__item");
            item.append(
                createElement("span", "", label),
                createElement("strong", "", formatQuantity(value)),
            );
            stock.append(item);
        });
        return stock;
    }

    function renderWarehouses(warehouses) {
        currentWarehouses = warehouses;
        warehouseList.replaceChildren();
        warehouseList.setAttribute("aria-busy", "false");

        const activeWarehouses = warehouses.filter((warehouse) => warehouse.is_active);
        const archivedWarehouses = warehouses.filter((warehouse) => !warehouse.is_active);
        const visibleWarehouses = showArchivedWarehouses
            ? [...activeWarehouses, ...archivedWarehouses]
            : activeWarehouses;

        warehouseArchiveControls.hidden = archivedWarehouses.length === 0;
        warehouseArchiveToggle.setAttribute("aria-expanded", String(showArchivedWarehouses));
        warehouseArchiveToggle.textContent = showArchivedWarehouses
            ? "Скрыть архив"
            : `Показать архив (${archivedWarehouses.length})`;

        if (!visibleWarehouses.length) {
            const message = archivedWarehouses.length
                ? "Активных складов нет"
                : "Склады пока не созданы";
            warehouseList.append(createElement("div", "empty-state", message));
            return;
        }

        const container = createElement("div", "table-container warehouse-table-container");
        const table = createElement("table", "table warehouse-table");
        const head = document.createElement("thead");
        const headRow = document.createElement("tr");
        ["Склад", "Статус", "Остатки", "Действия"].forEach((label) => {
            const heading = createElement("th", "", label);
            heading.scope = "col";
            headRow.append(heading);
        });
        head.append(headRow);

        const body = document.createElement("tbody");
        visibleWarehouses.forEach((warehouse) => {
            const row = document.createElement("tr");
            if (!warehouse.is_active) {
                row.className = "warehouse-row--archived";
            }

            const nameCell = document.createElement("td");
            nameCell.append(createElement("span", "warehouse-name", warehouse.name));

            const statusCell = document.createElement("td");
            statusCell.append(
                warehouse.is_active
                    ? createStatusBadge("Активен", "status-badge--success")
                    : createStatusBadge("Архив", "status-badge--danger"),
            );

            const stockCell = document.createElement("td");
            stockCell.append(renderWarehouseStock(warehouse));

            const actionsCell = createElement("td", "warehouse-actions");
            if (warehouse.is_active) {
                const actions = createElement("div", "actions");
                const renameButton = createButton("Переименовать", "rename-warehouse", warehouse.id);
                const archiveButton = createButton(
                    "В архив",
                    "archive-warehouse",
                    warehouse.id,
                    "button--danger",
                );
                renameButton.dataset.name = warehouse.name;
                archiveButton.dataset.name = warehouse.name;
                archiveButton.dataset.physical = warehouse.physical_quantity;
                archiveButton.dataset.reserved = warehouse.reserved_quantity;
                actions.append(
                    renameButton,
                    archiveButton,
                );
                actionsCell.append(actions);
            } else {
                const actions = createElement("div", "actions");
                actions.append(
                    createButton("Разархивировать", "restore-warehouse", warehouse.id),
                );
                actionsCell.append(actions);
            }

            row.append(nameCell, statusCell, stockCell, actionsCell);
            body.append(row);
        });

        table.append(head, body);
        container.append(table);
        warehouseList.append(container);
    }

    function fillSelect(select, items, placeholder, valueKey, labelBuilder) {
        const selectedValue = select.value;
        const placeholderOption = createElement("option", "", placeholder);
        placeholderOption.value = "";
        select.replaceChildren(placeholderOption);

        items.forEach((item) => {
            const option = createElement("option", "", labelBuilder(item));
            option.value = item[valueKey];
            select.append(option);
        });

        if ([...select.options].some((option) => option.value === selectedValue)) {
            select.value = selectedValue;
        }
    }

    function renderTransferFormOptions(products, warehouses) {
        const activeWarehouses = warehouses.filter((warehouse) => warehouse.is_active);
        fillSelect(
            productSelect,
            products,
            "Выберите товар",
            "sku",
            (product) => `${product.sku} — ${product.name}`,
        );
        fillSelect(
            sourceSelect,
            activeWarehouses,
            "Выберите склад",
            "id",
            (warehouse) => warehouse.name,
        );
        fillSelect(
            destinationSelect,
            activeWarehouses,
            "Выберите склад",
            "id",
            (warehouse) => warehouse.name,
        );
    }

    function getTransferStatus(status) {
        const statuses = {
            CREATED: ["Создано", ""],
            IN_TRANSIT: ["В пути", "status-badge--warning"],
            RECEIVED: ["Принято", "status-badge--success"],
        };
        return statuses[status] || [status, ""];
    }

    function renderTransfers(transfers) {
        transferList.replaceChildren();
        transferList.setAttribute("aria-busy", "false");

        if (!transfers.length) {
            transferList.append(createElement("div", "empty-state", "Перемещений пока нет"));
            return;
        }

        const container = createElement("div", "table-container transfer-table-container");
        const table = createElement("table", "table transfer-table");
        const head = document.createElement("thead");
        const headRow = document.createElement("tr");
        ["Перемещение", "Товар", "Маршрут", "Количество", "Статус", "Действия"].forEach((label) => {
            const heading = createElement("th", "", label);
            heading.scope = "col";
            headRow.append(heading);
        });
        head.append(headRow);

        const body = document.createElement("tbody");
        transfers.forEach((transfer) => {
            const row = document.createElement("tr");
            const idCell = document.createElement("td");
            idCell.append(
                createElement("strong", "", `#${transfer.id}`),
                createElement("div", "transfer-meta", formatDate(transfer.created_at)),
            );

            const productCell = createElement("td", "transfer-product");
            productCell.append(
                createElement("strong", "", transfer.product.sku),
                createElement("span", "", transfer.product.name),
            );

            const routeCell = document.createElement("td");
            const route = createElement("div", "transfer-route");
            route.append(
                createElement("span", "", transfer.source_warehouse.name),
                createElement("span", "transfer-route__arrow", "→"),
                createElement("span", "", transfer.destination_warehouse.name),
            );
            routeCell.append(route);

            const quantityCell = createElement("td", "", formatQuantity(transfer.quantity));
            const [statusLabel, statusModifier] = getTransferStatus(transfer.status);
            const statusCell = document.createElement("td");
            statusCell.append(createStatusBadge(statusLabel, statusModifier));

            const actionsCell = createElement("td", "transfer-actions");
            const actions = createElement("div", "actions");
            if (transfer.status === "CREATED") {
                actions.append(createButton("Отправить", "ship-transfer", transfer.id, ""));
            } else if (transfer.status === "IN_TRANSIT") {
                actions.append(createButton("Подтвердить приёмку", "receive-transfer", transfer.id, ""));
            } else {
                actions.append(createElement("span", "transfer-meta", `Принято ${formatDate(transfer.received_at)}`));
            }
            actionsCell.append(actions);

            row.append(idCell, productCell, routeCell, quantityCell, statusCell, actionsCell);
            body.append(row);
        });

        table.append(head, body);
        container.append(table);
        transferList.append(container);
    }

    function renderLoadError(error) {
        const message = error.message || "Не удалось загрузить данные";
        [warehouseList, transferList].forEach((region) => {
            region.setAttribute("aria-busy", "false");
            region.replaceChildren(createElement("div", "empty-state transfer-error", message));
        });
    }

    async function loadPageData({notify = false} = {}) {
        ui.setButtonLoading(refreshButton, true, "Обновление...");
        try {
            const [warehouses, products, transfers] = await Promise.all([
                api.get("/api/warehouses?include_archived=true"),
                api.get("/api/products"),
                api.get("/api/transfers"),
            ]);
            renderWarehouses(warehouses);
            renderTransferFormOptions(products, warehouses);
            renderTransfers(transfers);
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

    refreshButton.addEventListener("click", () => loadPageData({notify: true}));

    warehouseArchiveToggle.addEventListener("click", () => {
        showArchivedWarehouses = !showArchivedWarehouses;
        renderWarehouses(currentWarehouses);
    });

    warehouseForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (ui.isButtonLoading(warehouseSubmitButton) || !warehouseForm.reportValidity()) {
            return;
        }

        const warehouseName = warehouseNameInput.value.trim();
        const confirmed = window.confirm(
            `Создать склад?\n\nНазвание: ${warehouseName}`,
        );
        if (!confirmed) {
            return;
        }

        ui.setButtonLoading(warehouseSubmitButton, true, "Создание...");
        try {
            const warehouse = await api.post("/api/warehouses", {
                name: warehouseName,
            });
            warehouseForm.reset();
            ui.showNotification(`Склад «${warehouse.name}» создан`, "success");
            await loadPageData();
        } catch (error) {
            ui.showNotification(error.message || "Не удалось создать склад", "error");
        } finally {
            ui.setButtonLoading(warehouseSubmitButton, false);
        }
    });

    warehouseList.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button || ui.isButtonLoading(button)) {
            return;
        }

        const warehouseId = Number(button.dataset.id);
        if (button.dataset.action === "rename-warehouse") {
            const name = window.prompt("Новое название склада", button.dataset.name);
            if (name === null || !name.trim() || name.trim() === button.dataset.name) {
                return;
            }

            ui.setButtonLoading(button, true, "Сохранение...");
            try {
                const warehouse = await api.patch(`/api/warehouses/${warehouseId}`, {name});
                ui.showNotification(`Склад переименован в «${warehouse.name}»`, "success");
                await loadPageData();
            } catch (error) {
                ui.showNotification(error.message || "Не удалось переименовать склад", "error");
                ui.setButtonLoading(button, false);
            }
            return;
        }

        if (button.dataset.action === "archive-warehouse") {
            const physicalQuantity = Number(button.dataset.physical) || 0;
            const reservedQuantity = Number(button.dataset.reserved) || 0;
            const warning = physicalQuantity > 0
                ? `На складе «${button.dataset.name}» находится ${formatQuantity(physicalQuantity)} шт. товара, из них ${formatQuantity(reservedQuantity)} шт. зарезервировано.\n\nПосле архивации новые операции со складом будут запрещены, но остатки и история сохранятся.\n\nПодтвердить архивацию?`
                : `Архивировать склад «${button.dataset.name}»? Остатки и история будут сохранены.`;
            const confirmed = window.confirm(
                warning,
            );
            if (!confirmed) {
                return;
            }

            ui.setButtonLoading(button, true, "Архивация...");
            try {
                const warehouse = await api.remove(`/api/warehouses/${warehouseId}`);
                ui.showNotification(`Склад «${warehouse.name}» перемещён в архив`, "success");
                await loadPageData();
            } catch (error) {
                ui.showNotification(error.message || "Не удалось архивировать склад", "error");
                ui.setButtonLoading(button, false);
            }
            return;
        }

        if (button.dataset.action === "restore-warehouse") {
            ui.setButtonLoading(button, true, "Восстановление...");
            try {
                const warehouse = await api.post(`/api/warehouses/${warehouseId}/restore`);
                ui.showNotification(`Склад «${warehouse.name}» разархивирован`, "success");
                await loadPageData();
            } catch (error) {
                ui.showNotification(error.message || "Не удалось разархивировать склад", "error");
                ui.setButtonLoading(button, false);
            }
        }
    });

    transferForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (ui.isButtonLoading(transferSubmitButton) || !transferForm.reportValidity()) {
            return;
        }
        if (sourceSelect.value === destinationSelect.value) {
            ui.showNotification("Склады отправления и назначения должны различаться", "warning");
            destinationSelect.focus();
            return;
        }

        const productLabel = productSelect.selectedOptions[0]?.textContent || productSelect.value;
        const sourceLabel = sourceSelect.selectedOptions[0]?.textContent || sourceSelect.value;
        const destinationLabel = destinationSelect.selectedOptions[0]?.textContent || destinationSelect.value;
        const quantity = Number(quantityInput.value);
        const confirmed = window.confirm(
            `Создать перемещение?\n\nТовар: ${productLabel}\nСо склада: ${sourceLabel}\nНа склад: ${destinationLabel}\nКоличество: ${formatQuantity(quantity)} шт.`,
        );
        if (!confirmed) {
            return;
        }

        ui.setButtonLoading(transferSubmitButton, true, "Создание...");
        try {
            const transfer = await api.post("/api/transfers", {
                sku: productSelect.value,
                source_warehouse_id: Number(sourceSelect.value),
                destination_warehouse_id: Number(destinationSelect.value),
                quantity,
                idempotency_key: transferKey,
            });
            transferKey = createTransferKey();
            quantityInput.value = "";
            ui.showNotification(`Перемещение #${transfer.id} создано`, "success");
            await loadPageData();
        } catch (error) {
            ui.showNotification(error.message || "Не удалось создать перемещение", "error");
        } finally {
            ui.setButtonLoading(transferSubmitButton, false);
        }
    });

    transferList.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button || ui.isButtonLoading(button)) {
            return;
        }

        const transferId = Number(button.dataset.id);
        const isShipment = button.dataset.action === "ship-transfer";
        const action = isShipment ? "ship" : "receive";
        const loadingText = isShipment ? "Отправка..." : "Приёмка...";
        ui.setButtonLoading(button, true, loadingText);
        try {
            const transfer = await api.post(`/api/transfers/${transferId}/${action}`);
            const message = isShipment
                ? `Перемещение #${transfer.id} отправлено`
                : `Перемещение #${transfer.id} принято`;
            ui.showNotification(message, "success");
            await loadPageData();
        } catch (error) {
            ui.showNotification(error.message || "Не удалось изменить статус перемещения", "error");
            ui.setButtonLoading(button, false);
        }
    });

    warehousesPage.setAttribute("data-ready", "true");
    loadPageData();
}
