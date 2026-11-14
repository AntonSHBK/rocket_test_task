from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "CheckStock"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_dir: Path = Field(default=BASE_DIR / "logs", validation_alias="LOG_DIR")
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / "docker" / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        return self.database_url.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
