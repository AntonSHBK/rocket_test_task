import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

logger = logging.getLogger("api")


class ApplicationError(Exception):
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class DatabaseUnavailableError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            message="Database is unavailable",
            error_code="DATABASE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ProductNotFoundError(ApplicationError):
    def __init__(self, identifier: str) -> None:
        super().__init__(
            message=f"Product {identifier} was not found",
            error_code="PRODUCT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class WarehouseNotFoundError(ApplicationError):
    def __init__(self, warehouse_id: int) -> None:
        super().__init__(
            message=f"Warehouse {warehouse_id} was not found",
            error_code="WAREHOUSE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class WarehouseInactiveError(ApplicationError):
    def __init__(self, warehouse_id: int) -> None:
        super().__init__(
            message=f"Warehouse {warehouse_id} is inactive",
            error_code="WAREHOUSE_INACTIVE",
            status_code=status.HTTP_409_CONFLICT,
        )


class WarehouseAlreadyExistsError(ApplicationError):
    def __init__(self, name: str) -> None:
        super().__init__(
            message=f"Warehouse {name} already exists",
            error_code="WAREHOUSE_ALREADY_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
        )


class InsufficientStockError(ApplicationError):
    def __init__(
        self,
        warehouse_name: str,
        requested: int,
        available: int,
        other_warehouses: list[dict[str, Any]],
    ) -> None:
        super().__init__(
            message=f"Insufficient stock at warehouse {warehouse_name}",
            error_code="INSUFFICIENT_STOCK",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "requested": requested,
                "available": available,
                "other_warehouses": other_warehouses,
            },
        )


class IdempotencyConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            message="Idempotency key is already used for another operation",
            error_code="IDEMPOTENCY_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
        )


class TransferNotFoundError(ApplicationError):
    def __init__(self, transfer_id: int) -> None:
        super().__init__(
            message=f"Transfer {transfer_id} was not found",
            error_code="TRANSFER_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InvalidTransferStateError(ApplicationError):
    def __init__(self, current_status: str, expected_status: str) -> None:
        super().__init__(
            message=(
                f"Transfer status is {current_status}; "
                f"expected {expected_status}"
            ),
            error_code="INVALID_TRANSFER_STATE",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "current_status": current_status,
                "expected_status": expected_status,
            },
        )


class ReservationNotFoundError(ApplicationError):
    def __init__(self, reservation_id: int) -> None:
        super().__init__(
            message=f"FBS reservation {reservation_id} was not found",
            error_code="RESERVATION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InvalidReservationStateError(ApplicationError):
    def __init__(self, current_status: str, operation: str) -> None:
        super().__init__(
            message=(
                f"Cannot {operation} reservation with status {current_status}"
            ),
            error_code="INVALID_RESERVATION_STATE",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "current_status": current_status,
                "operation": operation,
            },
        )


class ShipmentNotFoundError(ApplicationError):
    def __init__(self, shipment_id: int) -> None:
        super().__init__(
            message=f"FBO shipment {shipment_id} was not found",
            error_code="SHIPMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InvalidShipmentStateError(ApplicationError):
    def __init__(self, current_status: str, expected_status: str) -> None:
        super().__init__(
            message=(
                f"Shipment status is {current_status}; "
                f"expected {expected_status}"
            ),
            error_code="INVALID_SHIPMENT_STATE",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "current_status": current_status,
                "expected_status": expected_status,
            },
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def handle_application_error(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        logger.warning(
            "%s %s: %s",
            request.method,
            request.url.path,
            exc.message,
        )
        error = {
            "code": exc.error_code,
            "message": exc.message,
            **exc.details,
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": jsonable_encoder(error)},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "%s %s: request validation failed",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder({
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            }),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "%s %s: unhandled exception",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Internal server error",
                }
            },
        )
