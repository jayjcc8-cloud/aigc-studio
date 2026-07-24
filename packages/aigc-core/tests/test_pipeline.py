"""Smoke test: run one shot through the full dummy pipeline."""

from pathlib import Path

import pytest
from aigc_audio import DummyMusicProvider, DummySubtitleProvider, DummyTtsProvider
from aigc_core.models import AssetType, Platform, Project, Scene, Shot, Story
from aigc_core.pipeline import Pipeline
from aigc_core.provider import ProviderConfig
from aigc_generation import DummyImageProvider, DummyVideoProvider


def make_pipeline() -> Pipeline:
    return Pipeline(
        image_provider=DummyImageProvider(ProviderConfig(name="dummy-image")),
        video_provider=DummyVideoProvider(ProviderConfig(name="dummy-video")),
        tts_provider=DummyTtsProvider(ProviderConfig(name="dummy-tts")),
        music_provider=DummyMusicProvider(ProviderConfig(name="dummy-music")),
        subtitle_provider=DummySubtitleProvider(ProviderConfig(name="dummy-subtitle")),
    )


@pytest.fixture
def project() -> Project:
    scene = Scene(index=0, title="Opening", location="city street", mood="tense")
    shot = Shot(
        scene_id=scene.id,
        index=0,
        prompt="cinematic shot of a rainy neon street at night",
        dialogue="我们终于见面了。",
        audio_mood="calm-mandarin-female",
    )
    story = Story(
        title="雨夜",
        hook="一个陌生人递来一把伞",
        theme="urban suspense",
        target_platforms=[Platform.DOUYIN, Platform.YOUTUBE_SHORTS],
        scenes=[scene],
        shots=[shot],
    )
    return Project(title="雨夜 第1集", story=story)


async def test_pipeline_generates_all_asset_types(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, project: Project
) -> None:
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path))
    result = await make_pipeline().generate_project_assets(project)

    types = {a.asset_type for a in result.assets}
    assert {
        AssetType.IMAGE,
        AssetType.VIDEO,
        AssetType.AUDIO,
        AssetType.MUSIC,
        AssetType.SUBTITLE,
    } <= types

    for asset in result.assets:
        assert Path(asset.uri).exists(), f"missing placeholder file: {asset.uri}"

    assert result.total_cost() > 0


async def test_pipeline_without_story_is_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path))
    project = Project(title="empty")
    result = await make_pipeline().generate_project_assets(project)
    assert result.assets == []
