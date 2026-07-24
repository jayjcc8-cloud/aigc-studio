"""Minimal end-to-end pipeline skeleton for smoke tests and local development."""

from __future__ import annotations

from aigc_core.config import get_settings
from aigc_core.models import AssetType, GenerationStatus, Project
from aigc_core.provider import (
    BaseProvider,
    GenerationRequest,
    GenerationResult,
    ImageProvider,
    MusicProvider,
    SubtitleProvider,
    TtsProvider,
    VideoProvider,
)


class Pipeline:
    """Orchestrates asset generation for a single project.

    This class is intentionally simple. In production it will be replaced by a
    DAG-based orchestrator (Prefect/Airflow) with retries, cost tracking and
    multi-provider fallback.
    """

    def __init__(
        self,
        image_provider: ImageProvider,
        video_provider: VideoProvider,
        tts_provider: TtsProvider,
        music_provider: MusicProvider,
        subtitle_provider: SubtitleProvider,
    ) -> None:
        self.image_provider = image_provider
        self.video_provider = video_provider
        self.tts_provider = tts_provider
        self.music_provider = music_provider
        self.subtitle_provider = subtitle_provider
        self.settings = get_settings()

    async def _run_provider(
        self, provider: BaseProvider, request: GenerationRequest
    ) -> GenerationResult:
        result = await provider.generate(request)
        if result.status == GenerationStatus.FAILED:
            raise RuntimeError(result.error_message or f"{provider.name} failed")
        return result

    async def generate_project_assets(self, project: Project) -> Project:
        """Generate storyboard, video, audio, music, and subtitle assets."""
        story = project.story
        if story is None:
            return project

        for shot in story.shots:
            image_result = await self._run_provider(
                self.image_provider,
                GenerationRequest(
                    project_id=project.id,
                    operation=f"shot-{shot.index}-frame",
                    asset_type=AssetType.IMAGE,
                    prompt=shot.prompt,
                    negative_prompt=shot.negative_prompt,
                    reference_asset_ids=shot.reference_asset_ids,
                    params={"duration": shot.duration_seconds},
                ),
            )
            if image_result.asset:
                project.assets.append(image_result.asset)
                shot.reference_asset_ids.append(image_result.asset.id)

            video_result = await self._run_provider(
                self.video_provider,
                GenerationRequest(
                    project_id=project.id,
                    operation=f"shot-{shot.index}-clip",
                    asset_type=AssetType.VIDEO,
                    prompt=shot.prompt,
                    negative_prompt=shot.negative_prompt,
                    reference_asset_ids=shot.reference_asset_ids,
                    params={"duration": shot.duration_seconds},
                ),
            )
            if video_result.asset:
                project.assets.append(video_result.asset)

            if shot.dialogue:
                tts_result = await self._run_provider(
                    self.tts_provider,
                    GenerationRequest(
                        project_id=project.id,
                        operation=f"shot-{shot.index}-dialogue",
                        asset_type=AssetType.AUDIO,
                        prompt=shot.dialogue,
                        params={"voice": shot.audio_mood or "default"},
                    ),
                )
                if tts_result.asset:
                    project.assets.append(tts_result.asset)

        music_result = await self._run_provider(
            self.music_provider,
            GenerationRequest(
                project_id=project.id,
                operation="main-music",
                asset_type=AssetType.MUSIC,
                prompt=story.theme or "cinematic short-drama score",
            ),
        )
        if music_result.asset:
            project.assets.append(music_result.asset)

        subtitle_result = await self._run_provider(
            self.subtitle_provider,
            GenerationRequest(
                project_id=project.id,
                operation="subtitles",
                asset_type=AssetType.SUBTITLE,
                prompt="\n".join(shot.dialogue for shot in story.shots if shot.dialogue),
            ),
        )
        if subtitle_result.asset:
            project.assets.append(subtitle_result.asset)

        return project
