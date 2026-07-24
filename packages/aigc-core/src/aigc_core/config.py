"""Application configuration loaded from environment variables and YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Top-level application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "aigc-studio"
    debug: bool = False
    projects_dir: Path = Field(default=Path("projects"))
    assets_dir: Path = Field(default=Path("data/assets"))
    default_video_provider: str = "dummy"
    default_tts_provider: str = "dummy"
    default_music_provider: str = "dummy"
    default_subtitle_provider: str = "dummy"

    # LLM (script generation). Env vars: LLM_BASE_URL / LLM_API_KEY / LLM_MODEL.
    llm_base_url: str = "https://api.anthropic.com"
    llm_api_key: str | None = None
    llm_model: str = "claude-sonnet-4-5"
    llm_timeout_seconds: float = 120.0

    # Seedance video generation. Env vars: SEEDANCE_API_KEY / SEEDANCE_BASE_URL / ...
    seedance_api_key: str | None = None
    seedance_base_url: str = "https://api.seedance2.ai"
    seedance_model: str = "seedance-2-0"
    seedance_max_poll_seconds: float = 600.0

    @classmethod
    def from_yaml(cls, path: Path) -> AppSettings:
        """Load settings from a YAML file and merge with environment variables."""
        data: dict[str, Any] = {}
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        return cls(**data)


def get_settings() -> AppSettings:
    """Return the global settings object."""
    return AppSettings()
