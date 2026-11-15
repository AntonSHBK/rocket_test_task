const operationsPage = document.querySelector("[data-page='operations']");

if (operationsPage) {
    const api = window.CheckStockAPI;
    const ui = window.CheckStockUI;
    const refreshButton = operationsPage.querySelector("[data-refresh-operations]");
    const updatedAt = operationsPage.querySelector("[data-operations-updated-at]");
    const fbsForm = operationsPage.querySelector("[data-fbs-form]");
    const fbsProduct = operationsPage.querySelector("#fbs-product");
    const fbsWarehouse = operationsPage.querySelector("#fbs-warehouse");
    const fbsQuantity = operationsPage.querySelector("#fbs-quantity");
    const fbsOrderReference = operationsPage.querySelector("#fbs-order-reference");
    const fbsSubmitButton = fbsForm.querySelector("button[type='submit']");
    const fbsStockPreview = operationsPage.querySelector("[data-fbs-stock-preview]");
    const fbsStockAvailable = operationsPage.querySelector("[data-fbs-stock-available]");
    const fbsStockReserved = operationsPage.querySelector("[data-fbs-stock-reserved]");
    const fboForm = operationsPage.querySelector("[data-fbo-form]");
    const fboProduct = operationsPage.querySelector("#fbo-product");
    const fboWarehouse = operationsPage.querySelector("#fbo-warehouse");
    const fboDestination = operationsPage.querySelector("#fbo-destination");
    const fboQuantity = operationsPage.querySelector("#fbo-quantity");
    const fboSubmitButton = fboForm.querySelector("button[type='submit']");
    const fboStockPreview = operationsPage.querySelector("[data-fbo-stock-preview]");
    const fboStockAvailable = operationsPage.querySelector("[data-fbo-stock-available]");
    const fboStockReserved = operationsPage.querySelector("[data-fbo-stock-reserved]");
    const fbsActive = operationsPage.querySelector("[data-fbs-active]");
    const fbsCompleted = operationsPage.querySelector("[data-fbs-completed]");
    const fboActive = operationsPage.querySelector("[data-fbo-active]");
    const fboCompleted = operationsPage.querySelector("[data-fbo-completed]");
    const historyForm = operationsPage.querySelector("[data-history-filter]");
    const historySku = operationsPage.querySelector("#history-sku");
    const historyEventType = operationsPage.querySelector("#history-event-type");
    const historyResetButton = operationsPage.querySelector("[data-reset-history]");
    const historyList = operationsPage.querySelector("[data-history-list]");
    const numberFormatter = new Intl.NumberFormat("ru-RU");
    const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "short",
        timeStyle: "short",
    });
    let fbsKey = createIdempotencyKey("fbs");
    let fboKey = createIdempotencyKey("fbo");
    let inventorySnapshot = [];

    const historyLabels = {
        RECEIPT: "Приход",
        WRITE_OFF: "Списание",
        FBS_RESERVED: "Резерв FBS",
        FBS_RESERVATION_CANCELLED: "Отмена резерва FBS",
        FBS_SHIPPED: "Отправка FBS",
        FBS_DELIVERED: "Доставка FBS",
        TRANSFER_SHIPPED: "Отправка перемещения",
        TRANSFER_RECEIVED: "Приёмка перемещения",
        FBO_SHIPPED: "Отправка FBO",
        FBO_RECEIVED: "Приёмка FBO",
    };

    function createIdempotencyKey(operation) {
        const identifier = window.crypto?.randomUUID?.()
            || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        return `${operation}:web:${identifier}`;
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

    function createActionButton(text, operation, action, identifier, modifier = "") {
        const button = createElement("button", `button button--small ${modifier}`.trim(), text);
        button.type = "button";
        button.dataset.operationAction = action;
        button.dataset.operation = operation;
        button.dataset.id = identifier;
        return button;
    }

    function createStatusBadge(text, modifier = "") {
        return createElement("span", `status-badge ${modifier}`.trim(), text);
    }

    function formatQuantity(value) {
        return numberFormatter.format(Number(value) || 0);
    }

    function formatDate(value) {
        return value ? dateFormatter.format(new Date(value)) : "—";
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

    function renderFormOptions(products, warehouses) {
        const activeWarehouses = warehouses.filter((warehouse) => warehouse.is_active);
        [fbsProduct, fboProduct].forEach((select) => {
            fillSelect(
                select,
                products,
                "Выберите товар",
                "sku",
                (product) => `${product.sku} — ${product.name}`,
            );
        });
        [fbsWarehouse, fboWarehouse].forEach((select) => {
            fillSelect(
                select,
                activeWarehouses,
                "Выберите склад",
                "id",
                (warehouse) => warehouse.name,
            );
        });
    }

    function renderStockPreview(
        productSelect,
        warehouseSelect,
        preview,
        availableElement,
        reservedElement,
    ) {
        if (!productSelect.value || !warehouseSelect.value) {
            preview.hidden = true;
            return;
        }

        const productInventory = inventorySnapshot.find(
            (item) => item.product.sku === productSelect.value,
        );
        const warehouseStock = productInventory?.warehouses.find(
            (stock) => Number(stock.warehouse_id) === Number(warehouseSelect.value),
        );
        availableElement.textContent = formatQuantity(warehouseStock?.available || 0);
        reservedElement.textContent = formatQuantity(warehouseStock?.reserved || 0);
        preview.hidden = false;
    }

    function renderFbsStockPreview() {
        renderStockPreview(
            fbsProduct,
            fbsWarehouse,
            fbsStockPreview,
            fbsStockAvailable,
            fbsStockReserved,
        );
    }

    function renderFboStockPreview() {
        renderStockPreview(
            fboProduct,
            fboWarehouse,
            fboStockPreview,
            fboStockAvailable,
            fboStockReserved,
        );
    }

    function getFbsStatus(status) {
        const statuses = {
            RESERVED: ["В резерве", "status-badge--warning"],
            CANCELLED: ["Отменён", "status-badge--danger"],
            SHIPPED: ["Отправлен", "status-badge--success"],
            DELIVERED: ["Доставлен", "status-badge--success"],
        };
        return statuses[status] || [status, ""];
    }

    function getFboStatus(status) {
        const statuses = {
            CREATED: ["Создано", ""],
            IN_TRANSIT: ["В пути", "status-badge--warning"],
            RECEIVED: ["Принято", "status-badge--success"],
        };
        return statuses[status] || [status, ""];
    }

    function createOperationItem({
        identifier,
        title,
        status,
        statusModifier,
        details,
        actions = [],
    }) {
        const item = createElement("article", "operation-item");
        const main = createElement("div", "operation-item__main");
        const titleRow = createElement("div", "operation-item__title");
        titleRow.append(
            createElement("strong", "", `#${identifier} · ${title}`),
            createStatusBadge(status, statusModifier),
        );
        const detailsRegion = createElement("div", "operation-item__details");
        details.forEach((detail) => detailsRegion.append(createElement("span", "", detail)));
        main.append(titleRow, detailsRegion);
        item.append(main);

        if (actions.length) {
            const actionRegion = createElement("div", "actions operation-item__actions");
            actionRegion.append(...actions);
            item.append(actionRegion);
        }
        return item;
    }

    function renderOperationRegion(region, operations, emptyText, itemBuilder) {
        region.replaceChildren();
        if (!operations.length) {
            region.append(createElement("div", "operation-empty", emptyText));
            return;
        }
        operations.forEach((operation) => region.append(itemBuilder(operation)));
    }

    function createFbsItem(reservation) {
        const [status, statusModifier] = getFbsStatus(reservation.status);
        const details = [
            `${reservation.product.name} · ${formatQuantity(reservation.quantity)} шт.`,
            `Склад: ${reservation.warehouse.name}`,
            reservation.order_reference
                ? `Заказ: ${reservation.order_reference}`
                : `Создано: ${formatDate(reservation.created_at)}`,
        ];
        const actions = [];
        if (reservation.status === "RESERVED") {
            actions.push(
                createActionButton("Отправить", "fbs", "ship", reservation.id),
                createActionButton("Отменить", "fbs", "cancel", reservation.id, "button--danger"),
            );
        } else if (reservation.status === "SHIPPED") {
            actions.push(
                createActionButton("Подтвердить доставку", "fbs", "deliver", reservation.id),
            );
        }
        return createOperationItem({
            identifier: reservation.id,
            title: reservation.product.sku,
            status,
            statusModifier,
            details,
            actions,
        });
    }

    function createFboItem(shipment) {
        const [status, statusModifier] = getFboStatus(shipment.status);
        const details = [
            `${shipment.product.name} · ${formatQuantity(shipment.quantity)} шт.`,
            `${shipment.source_warehouse.name} → ${shipment.destination}`,
            `Создано: ${formatDate(shipment.created_at)}`,
        ];
        const actions = [];
        if (shipment.status === "CREATED") {
            actions.push(createActionButton("Отправить", "fbo", "ship", shipment.id));
        } else if (shipment.status === "IN_TRANSIT") {
            actions.push(createActionButton("Подтвердить приёмку", "fbo", "receive", shipment.id));
        }
        return createOperationItem({
            identifier: shipment.id,
            title: shipment.product.sku,
            status,
            statusModifier,
            details,
            actions,
        });
    }

    function renderFbsReservations(reservations) {
        renderOperationRegion(
            fbsActive,
            reservations.filter((reservation) => ["RESERVED", "SHIPPED"].includes(reservation.status)),
            "Активных операций FBS нет",
            createFbsItem,
        );
        renderOperationRegion(
            fbsCompleted,
            reservations.filter((reservation) => ["CANCELLED", "DELIVERED"].includes(reservation.status)),
            "Завершённых операций FBS нет",
            createFbsItem,
        );
    }

    function renderFboShipments(shipments) {
        renderOperationRegion(
            fboActive,
            shipments.filter((shipment) => shipment.status !== "RECEIVED"),
            "Активных поставок нет",
            createFboItem,
        );
        renderOperationRegion(
            fboCompleted,
            shipments.filter((shipment) => shipment.status === "RECEIVED"),
            "Завершённых поставок нет",
            createFboItem,
        );
    }

    function buildHistoryPath() {
        const parameters = new URLSearchParams({limit: "100"});
        const sku = historySku.value.trim();
        if (sku) {
            parameters.set("sku", sku);
        }
        if (historyEventType.value) {
            parameters.set("event_type", historyEventType.value);
        }
        return `/api/history?${parameters.toString()}`;
    }

    function renderHistory(events) {
        historyList.replaceChildren();
        historyList.setAttribute("aria-busy", "false");
        if (!events.length) {
            historyList.append(createElement("div", "empty-state", "Операции по выбранным фильтрам не найдены"));
            return;
        }

        const container = createElement("div", "table-container history-table-container");
        const table = createElement("table", "table history-table");
        const head = document.createElement("thead");
        const headRow = document.createElement("tr");
        ["Дата", "Операция", "Товар", "Количество", "Направление"].forEach((label) => {
            const heading = createElement("th", "", label);
            heading.scope = "col";
            headRow.append(heading);
        });
        head.append(headRow);

        const body = document.createElement("tbody");
        events.forEach((event) => {
            const row = document.createElement("tr");
            const productCell = createElement("td", "history-product");
            productCell.append(
                createElement("strong", "", event.sku),
                createElement("span", "", event.product_name),
            );
            row.append(
                createElement("td", "", formatDate(event.created_at)),
                createElement("td", "history-event", historyLabels[event.event_type] || event.event_type),
                productCell,
                createElement("td", "", formatQuantity(event.quantity)),
                createElement("td", "history-route", `${event.source || "—"} → ${event.destination || "—"}`),
            );
            body.append(row);
        });

        table.append(head, body);
        container.append(table);
        historyList.append(container);
    }

    function renderLoadError(error) {
        const message = error.message || "Не удалось загрузить данные";
        [fbsActive, fbsCompleted, fboActive, fboCompleted].forEach((region) => {
            region.replaceChildren(createElement("div", "operation-empty operation-error", message));
        });
        historyList.setAttribute("aria-busy", "false");
        historyList.replaceChildren(createElement("div", "empty-state operation-error", message));
    }

    async function loadPageData({notify = false} = {}) {
        ui.setButtonLoading(refreshButton, true, "Обновление...");
        try {
            const [products, warehouses, inventory, reservations, shipments, history] = await Promise.all([
                api.get("/api/products"),
                api.get("/api/warehouses?include_archived=false"),
                api.get("/api/inventory"),
                api.get("/api/fbs/reservations"),
                api.get("/api/fbo/shipments"),
                api.get(buildHistoryPath()),
            ]);
            inventorySnapshot = inventory;
            renderFormOptions(products, warehouses);
            renderFbsStockPreview();
            renderFboStockPreview();
            renderFbsReservations(reservations);
            renderFboShipments(shipments);
            renderHistory(history);
            updatedAt.textContent = `Обновлено ${new Date().toLocaleTimeString("ru-RU", {
                hour: "2-digit",
                minute: "2-digit",
            })}`;
            if (notify) {
                ui.showNotification("Данные обновлены", "success", 2500);
            }
        } catch (error) {
            renderLoadError(error);
            ui.showNotification(error.message || "Не удалось загрузить операции", "error");
        } finally {
            ui.setButtonLoading(refreshButton, false);
        }
    }

    async function loadHistory() {
        historyList.setAttribute("aria-busy", "true");
        historyList.replaceChildren(createElement("div", "loading-state", "Загрузка истории..."));
        try {
            renderHistory(await api.get(buildHistoryPath()));
        } catch (error) {
            historyList.setAttribute("aria-busy", "false");
            historyList.replaceChildren(
                createElement("div", "empty-state operation-error", error.message || "Не удалось загрузить историю"),
            );
            ui.showNotification(error.message || "Не удалось загрузить историю", "error");
        }
    }

    refreshButton.addEventListener("click", () => loadPageData({notify: true}));
    fbsProduct.addEventListener("change", renderFbsStockPreview);
    fbsWarehouse.addEventListener("change", renderFbsStockPreview);
    fboProduct.addEventListener("change", renderFboStockPreview);
    fboWarehouse.addEventListener("change", renderFboStockPreview);

    fbsForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (ui.isButtonLoading(fbsSubmitButton) || !fbsForm.reportValidity()) {
            return;
        }

        const productLabel = fbsProduct.selectedOptions[0]?.textContent || fbsProduct.value;
        const warehouseLabel = fbsWarehouse.selectedOptions[0]?.textContent || fbsWarehouse.value;
        const quantity = Number(fbsQuantity.value);
        const orderReference = fbsOrderReference.value.trim() || "Не указан";
        const confirmed = window.confirm(
            `Создать резерв FBS?\n\nТовар: ${productLabel}\nСклад: ${warehouseLabel}\nКоличество: ${formatQuantity(quantity)} шт.\nЗаказ: ${orderReference}`,
        );
        if (!confirmed) {
            return;
        }

        ui.setButtonLoading(fbsSubmitButton, true, "Создание...");
        try {
            const reservation = await api.post("/api/fbs/reservations", {
                sku: fbsProduct.value,
                warehouse_id: Number(fbsWarehouse.value),
                quantity,
                order_reference: fbsOrderReference.value.trim() || null,
                idempotency_key: fbsKey,
            });
            fbsKey = createIdempotencyKey("fbs");
            fbsQuantity.value = "";
            fbsOrderReference.value = "";
            ui.showNotification(`Резерв FBS #${reservation.id} создан`, "success");
            await loadPageData();
        } catch (error) {
            ui.showNotification(error.message || "Не удалось создать резерв FBS", "error");
        } finally {
            ui.setButtonLoading(fbsSubmitButton, false);
        }
    });

    fboForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (ui.isButtonLoading(fboSubmitButton) || !fboForm.reportValidity()) {
            return;
        }

        const productLabel = fboProduct.selectedOptions[0]?.textContent || fboProduct.value;
        const warehouseLabel = fboWarehouse.selectedOptions[0]?.textContent || fboWarehouse.value;
        const destination = fboDestination.value.trim();
        const quantity = Number(fboQuantity.value);
        const confirmed = window.confirm(
            `Создать поставку FBO?\n\nТовар: ${productLabel}\nСклад: ${warehouseLabel}\nКоличество: ${formatQuantity(quantity)} шт.\nМаркетплейс: ${destination}`,
        );
        if (!confirmed) {
            return;
        }

        ui.setButtonLoading(fboSubmitButton, true, "Создание...");
        try {
            const shipment = await api.post("/api/fbo/shipments", {
                sku: fboProduct.value,
                source_warehouse_id: Number(fboWarehouse.value),
                destination,
                quantity,
                idempotency_key: fboKey,
            });
            fboKey = createIdempotencyKey("fbo");
            fboDestination.value = "";
            fboQuantity.value = "";
            ui.showNotification(`Поставка FBO #${shipment.id} создана`, "success");
            await loadPageData();
        } catch (error) {
            ui.showNotification(error.message || "Не удалось создать поставку FBO", "error");
        } finally {
            ui.setButtonLoading(fboSubmitButton, false);
        }
    });

    operationsPage.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-operation-action]");
        if (!button || ui.isButtonLoading(button)) {
            return;
        }

        const operation = button.dataset.operation;
        const action = button.dataset.operationAction;
        const identifier = Number(button.dataset.id);
        const confirmationMessages = {
            "fbs:ship": `Отправить резерв FBS #${identifier}? Товар будет списан со склада и перейдёт в путь к клиенту.`,
            "fbs:cancel": `Отменить резерв FBS #${identifier}? Зарезервированный товар станет доступен.`,
            "fbs:deliver": `Подтвердить доставку заказа FBS #${identifier} клиенту?`,
            "fbo:ship": `Отправить поставку FBO #${identifier}? Товар будет списан со склада и перейдёт в путь.`,
            "fbo:receive": `Подтвердить приёмку поставки FBO #${identifier} маркетплейсом?`,
        };
        const operationKey = `${operation}:${action}`;
        const confirmationMessage = confirmationMessages[operationKey];
        if (!confirmationMessage || !window.confirm(confirmationMessage)) {
            return;
        }

        const paths = {
            "fbs:ship": `/api/fbs/reservations/${identifier}/ship`,
            "fbs:cancel": `/api/fbs/reservations/${identifier}/cancel`,
            "fbs:deliver": `/api/fbs/reservations/${identifier}/deliver`,
            "fbo:ship": `/api/fbo/shipments/${identifier}/ship`,
            "fbo:receive": `/api/fbo/shipments/${identifier}/receive`,
        };
        const path = paths[operationKey];
        if (!path) {
            return;
        }

        const loadingTexts = {
            ship: "Отправка...",
            cancel: "Отмена...",
            deliver: "Подтверждение...",
            receive: "Приёмка...",
        };
        ui.setButtonLoading(button, true, loadingTexts[action]);
        try {
            await api.post(path);
            const messages = {
                "fbs:ship": `Резерв FBS #${identifier} отправлен`,
                "fbs:cancel": `Резерв FBS #${identifier} отменён`,
                "fbs:deliver": `Заказ FBS #${identifier} доставлен`,
                "fbo:ship": `Поставка FBO #${identifier} отправлена`,
                "fbo:receive": `Поставка FBO #${identifier} принята`,
            };
            ui.showNotification(messages[operationKey], "success");
            await loadPageData();
        } catch (error) {
            ui.showNotification(error.message || "Не удалось выполнить операцию", "error");
            ui.setButtonLoading(button, false);
        }
    });

    historyForm.addEventListener("submit", (event) => {
        event.preventDefault();
        loadHistory();
    });

    historyResetButton.addEventListener("click", () => {
        historyForm.reset();
        loadHistory();
    });

    operationsPage.setAttribute("data-ready", "true");
    loadPageData();
}
