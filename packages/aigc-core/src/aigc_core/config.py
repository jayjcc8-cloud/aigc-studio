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
