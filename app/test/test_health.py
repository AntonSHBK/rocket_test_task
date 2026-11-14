from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_session
from app.main import app


class AvailableDatabaseSession:
    async def execute(self, statement: object) -> None:
        return None


class UnavailableDatabaseSession:
    async def execute(self, statement: object) -> None:
        raise SQLAlchemyError


def test_health_returns_ok_when_database_is_available() -> None:
    async def override_session() -> AsyncGenerator[AvailableDatabaseSession, None]:
        yield AvailableDatabaseSession()

    app.dependency_overrides[get_session] = override_session

    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "available"}


def test_health_returns_service_unavailable_when_database_is_unavailable() -> None:
    async def override_session() -> AsyncGenerator[UnavailableDatabaseSession, None]:
        yield UnavailableDatabaseSession()

    app.dependency_overrides[get_session] = override_session

    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "Database is unavailable",
        }
    }
