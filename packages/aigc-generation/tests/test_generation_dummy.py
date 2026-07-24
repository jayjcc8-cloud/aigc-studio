"""Tests for dummy video/image providers."""

from uuid import uuid4

from aigc_core.models import AssetType, GenerationStatus
from aigc_core.provider import GenerationRequest, ProviderConfig
from aigc_generation import DummyImageProvider, DummyVideoProvider


async def test_dummy_video_provider_generates_video(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path))
    provider = DummyVideoProvider(ProviderConfig(name="dummy-video"))
    request = GenerationRequest(
        project_id=uuid4(),
        operation="test-clip",
        asset_type=AssetType.VIDEO,
        prompt="test",
    )
    result = await provider.generate(request)
    assert result.status == GenerationStatus.SUCCESS
    assert result.asset is not None
    assert result.asset.asset_type == AssetType.VIDEO
    assert result.asset.uri.endswith(".mp4")
    assert result.cost_usd > 0


async def test_dummy_video_provider_rejects_wrong_type() -> None:
    provider = DummyVideoProvider(ProviderConfig(name="dummy-video"))
    request = GenerationRequest(
        project_id=uuid4(),
        operation="wrong",
        asset_type=AssetType.AUDIO,
    )
    result = await provider.generate(request)
    assert result.status == GenerationStatus.FAILED
    assert result.asset is None


async def test_dummy_image_provider_healthcheck() -> None:
    provider = DummyImageProvider(ProviderConfig(name="dummy-image"))
    assert await provider.healthcheck() is True
