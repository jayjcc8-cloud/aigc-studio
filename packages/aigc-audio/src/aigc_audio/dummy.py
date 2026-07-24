"""Dummy audio providers for dialogue, music, and sound effects."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from aigc_core.config import get_settings
from aigc_core.models import Asset, AssetType, GenerationStatus
from aigc_core.provider import (
    GenerationRequest,
    GenerationResult,
    MusicProvider,
    SfxProvider,
    SubtitleProvider,
    TtsProvider,
)


def _placeholder_path(asset_type: AssetType, extension: str, project_id: str) -> Path:
    settings = get_settings()
    out_dir = settings.assets_dir / project_id / asset_type.value
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{uuid4().hex}{extension}"


def _write_placeholder(path: Path, content: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class DummyTtsProvider(TtsProvider):
    """Returns a placeholder WAV for spoken dialogue."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.asset_type != AssetType.AUDIO:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error_message=f"{self.name} only handles AUDIO requests",
            )
        path = _placeholder_path(AssetType.AUDIO, ".wav", str(request.project_id))
        _write_placeholder(path)
        asset = Asset(
            project_id=request.project_id,
            asset_type=AssetType.AUDIO,
            name=f"dialogue-{request.operation}",
            uri=str(path),
            mime_type="audio/wav",
            provider=self.name,
            cost_usd=0.002,
        )
        return GenerationResult(status=GenerationStatus.SUCCESS, asset=asset, cost_usd=0.002)

    async def healthcheck(self) -> bool:
        return True


class DummyMusicProvider(MusicProvider):
    """Returns a placeholder MP3 for background music."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.asset_type != AssetType.MUSIC:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error_message=f"{self.name} only handles MUSIC requests",
            )
        path = _placeholder_path(AssetType.MUSIC, ".mp3", str(request.project_id))
        _write_placeholder(path)
        asset = Asset(
            project_id=request.project_id,
            asset_type=AssetType.MUSIC,
            name=f"music-{request.operation}",
            uri=str(path),
            mime_type="audio/mp3",
            provider=self.name,
            cost_usd=0.005,
        )
        return GenerationResult(status=GenerationStatus.SUCCESS, asset=asset, cost_usd=0.005)

    async def healthcheck(self) -> bool:
        return True


class DummySfxProvider(SfxProvider):
    """Returns a placeholder WAV for a sound effect."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.asset_type != AssetType.SFX:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error_message=f"{self.name} only handles SFX requests",
            )
        path = _placeholder_path(AssetType.SFX, ".wav", str(request.project_id))
        _write_placeholder(path)
        asset = Asset(
            project_id=request.project_id,
            asset_type=AssetType.SFX,
            name=f"sfx-{request.operation}",
            uri=str(path),
            mime_type="audio/wav",
            provider=self.name,
            cost_usd=0.001,
        )
        return GenerationResult(status=GenerationStatus.SUCCESS, asset=asset, cost_usd=0.001)

    async def healthcheck(self) -> bool:
        return True


class DummySubtitleProvider(SubtitleProvider):
    """Returns a placeholder SRT file."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.asset_type != AssetType.SUBTITLE:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error_message=f"{self.name} only handles SUBTITLE requests",
            )
        path = _placeholder_path(AssetType.SUBTITLE, ".srt", str(request.project_id))
        _write_placeholder(path, b"1\n00:00:00,000 --> 00:00:05,000\nPlaceholder subtitle\n")
        asset = Asset(
            project_id=request.project_id,
            asset_type=AssetType.SUBTITLE,
            name=f"subtitles-{request.operation}",
            uri=str(path),
            mime_type="text/plain",
            provider=self.name,
            cost_usd=0.0,
        )
        return GenerationResult(status=GenerationStatus.SUCCESS, asset=asset, cost_usd=0.0)

    async def healthcheck(self) -> bool:
        return True
