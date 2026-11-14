document.documentElement.classList.add("js-enabled");

const navigationToggle = document.querySelector("[data-navigation-toggle]");
const navigation = document.querySelector("#main-navigation");
const notificationRegion = document.querySelector("[data-notification-region]");
const notificationTypes = new Set(["success", "warning", "error", "info"]);

function closeNavigation() {
    if (!navigationToggle || !navigation) {
        return;
    }

    navigation.classList.remove("is-open");
    navigationToggle.setAttribute("aria-expanded", "false");
}

function showNotification(message, type = "success", duration = 5000) {
    if (!notificationRegion || !message) {
        return null;
    }

    const resolvedType = notificationTypes.has(type) ? type : "info";
    const notification = document.createElement("div");
    const messageElement = document.createElement("p");
    const closeButton = document.createElement("button");

    notification.className = `notification notification--${resolvedType}`;
    notification.setAttribute("role", resolvedType === "error" ? "alert" : "status");
    messageElement.className = "notification__message";
    messageElement.textContent = String(message);
    closeButton.className = "notification__close";
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Закрыть уведомление");
    closeButton.textContent = "×";
    closeButton.addEventListener("click", () => notification.remove());

    notification.append(messageElement, closeButton);
    notificationRegion.append(notification);

    if (duration > 0) {
        window.setTimeout(() => notification.remove(), duration);
    }

    return notification;
}

function clearNotifications() {
    notificationRegion?.replaceChildren();
}

function setButtonLoading(button, isLoading, loadingText = "Загрузка...") {
    if (!button) {
        return;
    }

    if (isLoading) {
        button.dataset.originalText = button.textContent;
        button.textContent = loadingText;
        button.disabled = true;
        button.classList.add("is-loading");
        return;
    }

    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
    button.classList.remove("is-loading");
    delete button.dataset.originalText;
}

function isButtonLoading(button) {
    return !button || button.disabled || button.classList.contains("is-loading");
}

navigationToggle?.addEventListener("click", () => {
    const isOpen = navigation?.classList.toggle("is-open") ?? false;
    navigationToggle.setAttribute("aria-expanded", String(isOpen));
});

navigation?.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
        closeNavigation();
    }
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeNavigation();
    }
});

window.CheckStockUI = Object.freeze({
    clearNotifications,
    isButtonLoading,
    setButtonLoading,
    showNotification,
});
