from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from .env and bundled tariff config."""

    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    SMTP_SERVER: str
    SMTP_PORT: int = 465
    EMAIL_LOGIN: str
    EMAIL_PASSWORD: str
    EMAIL_TO: str
    tariff_config: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        env_file_encoding = "utf-8"


def load_settings() -> Settings:
    settings = Settings()
    config_path = Path(__file__).resolve().parent / "config" / "config.yaml"
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as fh:
            settings.tariff_config = yaml.safe_load(fh)
    return settings


settings = load_settings()

__all__ = ["Settings", "settings"]
