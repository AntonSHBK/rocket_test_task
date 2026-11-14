class CheckStockApiError extends Error {
    constructor(message, status = 0, payload = null) {
        super(message);
        this.name = "CheckStockApiError";
        this.status = status;
        this.payload = payload;
        this.code = payload?.error?.code || null;
        this.details = payload?.error || {};
    }
}

const apiErrorMessages = Object.freeze({
    DATABASE_UNAVAILABLE: "База данных временно недоступна",
    PRODUCT_NOT_FOUND: "Товар не найден",
    WAREHOUSE_NOT_FOUND: "Склад не найден",
    WAREHOUSE_INACTIVE: "Выбранный склад находится в архиве",
    WAREHOUSE_ALREADY_EXISTS: "Склад с таким названием уже существует",
    IDEMPOTENCY_CONFLICT: "Операция с этим ключом уже была отправлена с другими данными",
    TRANSFER_NOT_FOUND: "Перемещение не найдено",
    INVALID_TRANSFER_STATE: "Статус перемещения уже изменён. Обновите данные",
    RESERVATION_NOT_FOUND: "Резерв FBS не найден",
    INVALID_RESERVATION_STATE: "Действие недоступно для текущего статуса резерва",
    SHIPMENT_NOT_FOUND: "Поставка FBO не найдена",
    INVALID_SHIPMENT_STATE: "Статус поставки уже изменён. Обновите данные",
    VALIDATION_ERROR: "Проверьте заполнение полей",
    INTERNAL_SERVER_ERROR: "Внутренняя ошибка сервера",
});

function getInsufficientStockMessage(error) {
    const requested = Number(error.requested) || 0;
    const available = Number(error.available) || 0;
    const alternatives = Array.isArray(error.other_warehouses)
        ? error.other_warehouses
        : [];
    let message = `Недостаточно товара на выбранном складе: требуется ${requested}, доступно ${available}`;

    if (alternatives.length) {
        const warehouseList = alternatives
            .map((warehouse) => `${warehouse.name} — ${warehouse.available} шт.`)
            .join(", ");
        message += `. На других складах: ${warehouseList}`;
    }
    return message;
}

function getApiErrorMessage(payload, status) {
    const error = payload?.error;
    if (error?.code === "INSUFFICIENT_STOCK") {
        return getInsufficientStockMessage(error);
    }
    return apiErrorMessages[error?.code]
        || error?.message
        || `Ошибка запроса: ${status}`;
}

async function request(path, options = {}) {
    const requestOptions = {
        ...options,
        headers: {
            Accept: "application/json",
            ...options.headers,
        },
    };

    if (options.body && typeof options.body !== "string") {
        requestOptions.body = JSON.stringify(options.body);
        requestOptions.headers["Content-Type"] = "application/json";
    }

    let response;
    try {
        response = await fetch(path, requestOptions);
    } catch (error) {
        throw new CheckStockApiError("Не удалось подключиться к серверу", 0, error);
    }

    const contentType = response.headers.get("content-type") || "";
    let payload = null;
    if (contentType.includes("application/json")) {
        try {
            payload = await response.json();
        } catch (error) {
            throw new CheckStockApiError("Сервер вернул некорректный ответ", response.status, error);
        }
    }

    if (!response.ok) {
        const message = getApiErrorMessage(payload, response.status);
        throw new CheckStockApiError(message, response.status, payload);
    }

    return payload;
}

window.CheckStockAPI = Object.freeze({
    CheckStockApiError,
    get(path) {
        return request(path);
    },
    post(path, body) {
        return request(path, {method: "POST", body});
    },
    patch(path, body) {
        return request(path, {method: "PATCH", body});
    },
    remove(path) {
        return request(path, {method: "DELETE"});
    },
    request,
});
