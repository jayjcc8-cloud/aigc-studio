"""Tests for dummy audio providers."""

from pathlib import Path
from uuid import uuid4

import pytest
from aigc_audio import (
    DummyMusicProvider,
    DummySfxProvider,
    DummySubtitleProvider,
    DummyTtsProvider,
)
from aigc_core.models import AssetType, GenerationStatus
from aigc_core.provider import BaseProvider, GenerationRequest, ProviderConfig


@pytest.mark.parametrize(
    ("provider_cls", "asset_type", "extension"),
    [
        (DummyTtsProvider, AssetType.AUDIO, ".wav"),
        (DummyMusicProvider, AssetType.MUSIC, ".mp3"),
        (DummySfxProvider, AssetType.SFX, ".wav"),
        (DummySubtitleProvider, AssetType.SUBTITLE, ".srt"),
    ],
)
async def test_dummy_audio_providers_generate(
    provider_cls: type[BaseProvider],
    asset_type: AssetType,
    extension: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path))
    provider = provider_cls(ProviderConfig(name=f"dummy-{asset_type}"))
    request = GenerationRequest(
        project_id=uuid4(),
        operation="test",
        asset_type=asset_type,
        prompt="hello",
    )
    result = await provider.generate(request)
    assert result.status == GenerationStatus.SUCCESS
    assert result.asset is not None
    assert result.asset.uri.endswith(extension)
    assert Path(result.asset.uri).exists()
