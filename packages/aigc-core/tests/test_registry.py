"""Tests for the provider registry and storage layout."""

from pathlib import Path

import pytest
from aigc_core.models import AssetType, GenerationStatus
from aigc_core.provider import GenerationRequest, ProviderConfig
from aigc_core.registry import LlmProviderAdapter, ProviderRegistry
from aigc_core.storage import ProjectStorage
from aigc_generation import DummyVideoProvider


def test_registry_get_and_names() -> None:
    registry = ProviderRegistry()
    registry.register("video", DummyVideoProvider(ProviderConfig(name="dummy")))
    assert registry.names("video") == ["dummy"]
    assert registry.get("video", "dummy").name == "dummy"


def test_registry_missing_provider_error_lists_available() -> None:
    registry = ProviderRegistry()
    registry.register("video", DummyVideoProvider(ProviderConfig(name="dummy")))
    with pytest.raises(KeyError, match="no provider registered"):
        registry.get("video", "seedance")


class EchoChatClient:
    async def complete(self, *, system: str, user: str) -> str:
        return f"{system}|{user}"


async def test_llm_adapter_returns_text_in_raw_response() -> None:
    adapter = LlmProviderAdapter("kimi", EchoChatClient())
    result = await adapter.generate(
        GenerationRequest(
            project_id=__import__("uuid").uuid4(),
            operation="brief",
            asset_type=AssetType.SCRIPT,
            prompt="user prompt",
            params={"system": "sys"},
        )
    )
    assert result.status == GenerationStatus.SUCCESS
    assert result.raw_response == {"text": "sys|user prompt"}
    assert result.asset is None


async def test_llm_adapter_maps_errors_to_failed() -> None:
    class BoomClient:
        async def complete(self, *, system: str, user: str) -> str:
            raise RuntimeError("api down")

    adapter = LlmProviderAdapter("kimi", BoomClient())
    result = await adapter.generate(
        GenerationRequest(
            project_id=__import__("uuid").uuid4(),
            operation="brief",
            asset_type=AssetType.SCRIPT,
            prompt="p",
        )
    )
    assert result.status == GenerationStatus.FAILED
    assert "api down" in result.error_message


def test_storage_layout(tmp_path: Path) -> None:
    storage = ProjectStorage("proj-1", workspace_id="ws-1", base_dir=tmp_path)
    assert storage.dir("generated") == tmp_path / "ws-1" / "proj-1" / "generated"
    path = storage.new_file("exports", ".zip", name="package")
    assert path.parent.name == "exports"
    assert storage.state_file("tasks").name == "tasks.json"
    with pytest.raises(ValueError, match="unknown storage kind"):
        storage.dir("nowhere")
