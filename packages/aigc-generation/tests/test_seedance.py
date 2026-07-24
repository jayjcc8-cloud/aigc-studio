"""Tests for the Seedance video provider (mocked transport)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from aigc_core.models import AssetType, GenerationStatus
from aigc_core.provider import GenerationRequest
from aigc_generation import SeedanceConfig, SeedanceVideoProvider

Handler = Callable[[httpx.Request], httpx.Response]


def make_provider(handler: Handler, **overrides: Any) -> SeedanceVideoProvider:
    config = SeedanceConfig(api_key="sk_test_key", poll_interval_seconds=0.01, **overrides)
    return SeedanceVideoProvider(config, transport=httpx.MockTransport(handler))


def ok_handler(state: dict[str, Any]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/videos/generations":
            state["payload"] = json.loads(request.content)
            return httpx.Response(200, json={"taskId": "task-1", "credits": 60})
        if request.url.path == "/v1/tasks/task-1":
            state["polls"] = state.get("polls", 0) + 1
            if state["polls"] < 2:
                return httpx.Response(200, json={"status": "generating"})
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "data": {"results": [{"url": "https://cdn.example.com/v.mp4"}]},
                },
            )
        if request.url.host == "cdn.example.com":
            return httpx.Response(200, content=b"\x00\x01fake-mp4-bytes")
        return httpx.Response(404)

    return handler


async def test_generate_text_to_video_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path))
    state: dict[str, Any] = {}
    provider = make_provider(ok_handler(state))
    request = GenerationRequest(
        project_id=uuid4(),
        operation="shot-0",
        asset_type=AssetType.VIDEO,
        prompt="cinematic rain street",
        params={"duration": 5, "aspect_ratio": "9:16"},
    )
    result = await provider.generate(request)

    assert result.status == GenerationStatus.SUCCESS
    assert result.asset is not None
    assert result.asset.uri.endswith(".mp4")
    assert result.asset.metadata["credits"] == 60
    assert Path(result.asset.uri).read_bytes() == b"\x00\x01fake-mp4-bytes"
    payload = state["payload"]
    assert payload["input"]["generation_type"] == "text-to-video"
    assert payload["input"]["aspect_ratio"] == "9:16"
    assert payload["input"]["watermark"] is False
    assert state["polls"] == 2


async def test_generate_image_to_video_sets_type_and_urls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path))
    state: dict[str, Any] = {}
    provider = make_provider(ok_handler(state))
    request = GenerationRequest(
        project_id=uuid4(),
        operation="shot-1",
        asset_type=AssetType.VIDEO,
        prompt="woman takes umbrella",
        params={"image_url": "https://img.example.com/ref.png"},
    )
    result = await provider.generate(request)

    assert result.status == GenerationStatus.SUCCESS
    payload = state["payload"]
    assert payload["input"]["generation_type"] == "image-to-video"
    assert payload["input"]["image_urls"] == ["https://img.example.com/ref.png"]


async def test_generate_rejects_non_video() -> None:
    provider = make_provider(ok_handler({}))
    request = GenerationRequest(
        project_id=uuid4(),
        operation="x",
        asset_type=AssetType.AUDIO,
    )
    result = await provider.generate(request)
    assert result.status == GenerationStatus.FAILED


async def test_submit_http_error_returns_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    provider = make_provider(handler)
    request = GenerationRequest(
        project_id=uuid4(),
        operation="x",
        asset_type=AssetType.VIDEO,
        prompt="p",
    )
    result = await provider.generate(request)
    assert result.status == GenerationStatus.FAILED
    assert "401" in result.error_message


async def test_task_failed_returns_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/videos/generations":
            return httpx.Response(200, json={"taskId": "task-9"})
        return httpx.Response(200, json={"status": "failed", "data": {"error": "content blocked"}})

    provider = make_provider(handler)
    request = GenerationRequest(
        project_id=uuid4(),
        operation="x",
        asset_type=AssetType.VIDEO,
        prompt="p",
    )
    result = await provider.generate(request)
    assert result.status == GenerationStatus.FAILED
    assert "content blocked" in result.error_message
