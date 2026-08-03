"""Abstract provider interfaces for AI generation capabilities.

The pipeline depends on these abstractions, not on concrete APIs. This makes it
easy to swap Seedance for Kling, ElevenLabs for a local TTS model, etc., without
changing business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from aigc_core.models import Asset, AssetType, GenerationStatus


class ProviderConfig(BaseModel):
    """Base configuration shared by all providers."""

    name: str
    enabled: bool = True
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 2
    extra: dict[str, Any] = Field(default_factory=dict)


class GenerationRequest(BaseModel):
    """A provider-agnostic request to generate an asset."""

    project_id: UUID
    operation: str
    asset_type: AssetType
    prompt: str = ""
    negative_prompt: str = ""
    reference_asset_ids: list[UUID] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class GenerationResult(BaseModel):
    """Result of a provider generation call."""

    status: GenerationStatus = GenerationStatus.SUCCESS
    asset: Asset | None = None
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    error_message: str = ""
    raw_response: dict[str, Any] | None = None


class BaseProvider(ABC):
    """Common interface for all generation providers."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate an asset from the request."""
        raise NotImplementedError

    @abstractmethod
    async def healthcheck(self) -> bool:
        """Return True if the provider is reachable and usable."""
        raise NotImplementedError

    def estimate_cost(self, _request: GenerationRequest) -> float:
        """Estimate the CNY cost of a request before submitting it."""
        return 0.0


class VideoProvider(BaseProvider):
    """Generate motion video clips (text-to-video or image-to-video)."""

    pass


class ImageProvider(BaseProvider):
    """Generate still images for storyboards, characters, or reference frames."""

    pass


class TtsProvider(BaseProvider):
    """Generate spoken dialogue or narration from text."""

    pass


class MusicProvider(BaseProvider):
    """Generate or retrieve background music."""

    pass


class SfxProvider(BaseProvider):
    """Generate or retrieve sound effects."""

    pass


class SubtitleProvider(BaseProvider):
    """Generate timed subtitle files from scripts and audio."""

    pass
