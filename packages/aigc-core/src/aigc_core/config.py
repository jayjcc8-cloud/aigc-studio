"""Application configuration loaded from .env and environment variables.

All API keys and provider settings live here.  Used by every package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Top-level application settings — .env driven, single source of truth."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ───────────────────────────────────────────────────────
    app_name: str = "aigc-studio"
    debug: bool = False
    projects_dir: Path = Field(default=Path("projects"))
    assets_dir: Path = Field(default=Path("data/assets"))
    default_video_provider: str = "dummy"
    default_tts_provider: str = "dummy"
    default_music_provider: str = "dummy"
    default_subtitle_provider: str = "dummy"

    # ── LLM（剧本 / 文案 / 分镜 — 所有工作流模板的文本生成前端）──
    llm_base_url: str = "https://api.anthropic.com"
    llm_api_key: str | None = None
    llm_model: str = "claude-sonnet-4-5"
    llm_timeout_seconds: float = 120.0

    # ── 阿里云百炼 DashScope（主视频网关）───────────────
    bailian_api_key: str | None = None
    bailian_base_url: str = "https://dashscope.aliyuncs.com"

    # ── MiniMax（副供应商：Hailuo 视频 + Speech 配音）─────
    minimax_api_key: str | None = None
    minimax_base_url: str = "https://api.minimaxi.com"

    # ── Seedance 2.0（Hero 镜头, 5-10% 流量 —
    seedance_api_key: str | None = None
    seedance_base_url: str = "https://api.seedance2.ai"
    seedance_model: str = "seedance-2-0"
    seedance_max_poll_seconds: float = 600.0

    # ── Kling 3 / 可灵（复杂镜头, 备选, 也可走百炼网关）──────────
    kling_api_key: str | None = None

    # ── TTS 配音 ──────────────────────────────────────
    elevenlabs_api_key: str | None = None
    fish_audio_api_key: str | None = None

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
