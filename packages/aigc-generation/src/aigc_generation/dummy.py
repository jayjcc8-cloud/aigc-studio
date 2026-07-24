"""Dummy video and image providers for local development and smoke tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from aigc_core.config import get_settings
from aigc_core.models import Asset, AssetType, GenerationStatus
from aigc_core.provider import GenerationRequest, GenerationResult, ImageProvider, VideoProvider


def _placeholder_path(asset_type: AssetType, extension: str, project_id: str) -> Path:
    settings = get_settings()
    out_dir = settings.assets_dir / project_id / asset_type.value
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{uuid4().hex}{extension}"


def _write_placeholder(path: Path, content: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class DummyVideoProvider(VideoProvider):
    """Returns a placeholder MP4 without calling a real API."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.asset_type != AssetType.VIDEO:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error_message=f"{self.name} only handles VIDEO requests",
            )
        path = _placeholder_path(AssetType.VIDEO, ".mp4", str(request.project_id))
        _write_placeholder(path)
        asset = Asset(
            project_id=request.project_id,
            asset_type=AssetType.VIDEO,
            name=f"shot-{request.operation}",
            uri=str(path),
            mime_type="video/mp4",
            provider=self.name,
            cost_usd=0.01,
        )
        return GenerationResult(status=GenerationStatus.SUCCESS, asset=asset, cost_usd=0.01)

    async def healthcheck(self) -> bool:
        return True


class DummyImageProvider(ImageProvider):
    """Returns a placeholder PNG without calling a real API."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.asset_type != AssetType.IMAGE:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error_message=f"{self.name} only handles IMAGE requests",
            )
        path = _placeholder_path(AssetType.IMAGE, ".png", str(request.project_id))
        _write_placeholder(path)
        asset = Asset(
            project_id=request.project_id,
            asset_type=AssetType.IMAGE,
            name=f"frame-{request.operation}",
            uri=str(path),
            mime_type="image/png",
            provider=self.name,
            cost_usd=0.005,
        )
        return GenerationResult(status=GenerationStatus.SUCCESS, asset=asset, cost_usd=0.005)

    async def healthcheck(self) -> bool:
        return True
