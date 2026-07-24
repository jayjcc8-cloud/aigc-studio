"""Seedance 2.0 video generation provider (async task + polling).

Implements the seedance2.ai-style API contract:

- ``POST {base_url}/v1/videos/generations`` -> ``{"taskId": ..., "credits": ...}``
- ``GET  {base_url}/v1/tasks/{task_id}``    -> status: queued/generating/completed/failed

The base URL is configurable so the same provider can target compatible
gateways. Video URLs expire quickly, so results are downloaded immediately
into the local assets directory.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import uuid4

import httpx
from aigc_core.config import get_settings
from aigc_core.models import Asset, AssetType, GenerationStatus
from aigc_core.provider import GenerationRequest, GenerationResult, VideoProvider
from pydantic import BaseModel, Field


class SeedanceError(RuntimeError):
    """Raised on Seedance API failures."""


class SeedanceConfig(BaseModel):
    """Configuration for the Seedance provider."""

    name: str = "seedance"
    base_url: str = "https://api.seedance2.ai"
    api_key: str
    model: str = "seedance-2-0"
    timeout_seconds: float = 60.0
    poll_interval_seconds: float = 10.0
    max_poll_seconds: float = 600.0
    default_duration: int = Field(default=5, ge=4, le=15)
    default_resolution: str = "720p"
    default_aspect_ratio: str = "9:16"


class SeedanceVideoProvider(VideoProvider):
    """Generate short video clips via the Seedance async task API."""

    def __init__(
        self,
        config: SeedanceConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # Bridge into the core ProviderConfig expected by BaseProvider.
        from aigc_core.provider import ProviderConfig

        super().__init__(
            ProviderConfig(
                name=config.name,
                api_key=config.api_key,
                base_url=config.base_url,
                timeout_seconds=config.timeout_seconds,
            )
        )
        self.seedance_config = config
        self._transport = transport

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.asset_type != AssetType.VIDEO:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error_message=f"{self.name} only handles VIDEO requests",
            )

        started = time.monotonic()
        try:
            task = await self._submit(request)
            task_id = task["taskId"]
            credits = task.get("credits", 0)
            video_url = await self._poll_until_done(task_id)
            path = await self._download(video_url, str(request.project_id))
        except SeedanceError as exc:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error_message=str(exc),
                latency_seconds=time.monotonic() - started,
            )

        latency = time.monotonic() - started
        asset = Asset(
            project_id=request.project_id,
            asset_type=AssetType.VIDEO,
            name=f"seedance-{request.operation}",
            uri=str(path),
            mime_type="video/mp4",
            provider=self.name,
            metadata={
                "task_id": task_id,
                "credits": credits,
                "model": self.seedance_config.model,
                "prompt": request.prompt,
            },
        )
        return GenerationResult(
            status=GenerationStatus.SUCCESS,
            asset=asset,
            latency_seconds=latency,
            raw_response={"task_id": task_id, "credits": credits},
        )

    async def healthcheck(self) -> bool:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"{self.seedance_config.base_url.rstrip('/')}/v1/tasks/healthcheck"
                )
            return response.status_code in (200, 401, 404)
        except httpx.HTTPError:
            return False

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.seedance_config.timeout_seconds,
            transport=self._transport,
            headers={
                "Authorization": f"Bearer {self.seedance_config.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def _submit(self, request: GenerationRequest) -> dict[str, Any]:
        cfg = self.seedance_config
        params = request.params
        image_url = params.get("image_url")
        payload: dict[str, Any] = {
            "model": cfg.model,
            "input": {
                "prompt": request.prompt,
                "generation_type": "image-to-video" if image_url else "text-to-video",
                "duration": int(params.get("duration", cfg.default_duration)),
                "aspect_ratio": params.get("aspect_ratio", cfg.default_aspect_ratio),
                "resolution": params.get("resolution", cfg.default_resolution),
                "generate_audio": bool(params.get("generate_audio", False)),
                "watermark": False,
                "return_last_frame": True,
                "seed": int(params.get("seed", -1)),
            },
        }
        if image_url:
            payload["input"]["image_urls"] = [image_url]

        async with self._client() as client:
            try:
                response = await client.post(
                    f"{cfg.base_url.rstrip('/')}/v1/videos/generations", json=payload
                )
            except httpx.HTTPError as exc:
                raise SeedanceError(f"submit failed: {exc}") from exc
        if response.status_code != 200:
            raise SeedanceError(f"submit returned {response.status_code}: {response.text[:500]}")
        data: dict[str, Any] = response.json()
        if "taskId" not in data:
            raise SeedanceError(f"submit response missing taskId: {data!r:.300}")
        return data

    async def _poll_until_done(self, task_id: str) -> str:
        cfg = self.seedance_config
        deadline = time.monotonic() + cfg.max_poll_seconds
        url = f"{cfg.base_url.rstrip('/')}/v1/tasks/{task_id}"
        async with self._client() as client:
            while time.monotonic() < deadline:
                try:
                    response = await client.get(url)
                except httpx.HTTPError as exc:
                    raise SeedanceError(f"poll failed: {exc}") from exc
                if response.status_code != 200:
                    raise SeedanceError(
                        f"poll returned {response.status_code}: {response.text[:300]}"
                    )
                data = response.json()
                status = data.get("status")
                if status == "completed":
                    results = (data.get("data") or {}).get("results") or []
                    if not results:
                        raise SeedanceError(f"task {task_id} completed without results")
                    video_url = results[0].get("url") or results[0].get("video_url")
                    if not video_url:
                        raise SeedanceError(
                            f"task {task_id} result missing url: {results[0]!r:.300}"
                        )
                    return str(video_url)
                if status == "failed":
                    reason = (data.get("data") or {}).get("error") or data.get("error")
                    raise SeedanceError(f"task {task_id} failed: {reason}")
                await asyncio.sleep(cfg.poll_interval_seconds)
        raise SeedanceError(f"task {task_id} timed out after {cfg.max_poll_seconds:.0f}s")

    async def _download(self, video_url: str, project_id: str) -> Any:
        settings = get_settings()
        out_dir = settings.assets_dir / project_id / AssetType.VIDEO.value
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{uuid4().hex}.mp4"
        async with self._client() as client:
            try:
                response = await client.get(video_url)
            except httpx.HTTPError as exc:
                raise SeedanceError(f"download failed: {exc}") from exc
        if response.status_code != 200:
            raise SeedanceError(f"download returned {response.status_code}")
        path.write_bytes(response.content)
        return path
