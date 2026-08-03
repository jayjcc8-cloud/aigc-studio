"""Tests for the workflow engine."""

from pathlib import Path
from uuid import uuid4

import pytest
from aigc_audio import DummyTtsProvider
from aigc_core.provider import ProviderConfig
from aigc_core.registry import LlmProviderAdapter, ProviderRegistry
from aigc_core.storage import ProjectStorage
from aigc_generation import DummyVideoProvider
from aigc_workflows import (
    StepStatus,
    WorkflowEngine,
    WorkflowError,
    WorkflowTemplate,
    load_template,
)

TEMPLATE_DIR = Path(__file__).parent.parent / "src" / "aigc_workflows" / "templates"


class FakeChatClient:
    def __init__(self, outputs: list[str] | None = None, fail_times: int = 0) -> None:
        self.outputs = outputs or ["text output"]
        self.fail_times = fail_times
        self.calls = 0

    async def complete(self, *, system: str, user: str) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("llm down")
        return self.outputs[min(self.calls - self.fail_times - 1, len(self.outputs) - 1)]


def make_engine(tmp_path: Path, client: FakeChatClient) -> WorkflowEngine:
    registry = ProviderRegistry()
    registry.register("llm", LlmProviderAdapter("kimi", client))
    registry.register("video", DummyVideoProvider(ProviderConfig(name="dummy")))
    registry.register("tts", DummyTtsProvider(ProviderConfig(name="dummy")))
    storage = ProjectStorage("proj-e2e", workspace_id="ws-test", base_dir=tmp_path)
    return WorkflowEngine(registry, storage)


async def test_full_template_runs_to_completion_with_auto_approve(tmp_path: Path) -> None:
    client = FakeChatClient(["brief-json", "copy-json", "script-json"])
    engine = make_engine(tmp_path, client)
    template = load_template(TEMPLATE_DIR / "product_launch.yaml")

    state = await engine.run(
        template, uuid4(), {"product_docs": "一款帮独立开发者做发布的 AI 工具"}, auto_approve=True
    )

    assert state.status == "completed"
    assert state.context["product_brief"] == "brief-json"
    assert state.context["launch_copy"] == "copy-json"
    assert state.context["video_script"] == "script-json"
    package = Path(state.context["package"])
    assert (package / "01-copy" / "product_brief.md").read_text() == "brief-json"
    assert (package / "01-copy" / "launch_copy.md").read_text() == "copy-json"
    assert (package / "03-video" / "video_script.md").read_text() == "script-json"
    assert (package / "README.md").exists()
    assert engine.storage.state_file("tasks").exists()
    assert engine.storage.state_file("costs").exists()


async def test_pauses_at_approval_gate_and_resumes(tmp_path: Path) -> None:
    client = FakeChatClient(["brief-json", "copy-json", "script-json"])
    engine = make_engine(tmp_path, client)
    template = load_template(TEMPLATE_DIR / "product_launch.yaml")

    state = await engine.run(template, uuid4(), {"product_docs": "docs"}, auto_approve=False)
    assert state.status == "paused"
    assert state.steps[0].status == StepStatus.WAITING_APPROVAL
    assert "brief-json" in engine.pending_approval_text(state)

    engine.approve(state, reviewer="mo", comment="brief ok")
    state = await engine.run(template, uuid4(), {}, auto_approve=False, state=state)
    assert state.status == "paused"
    assert state.steps[1].status == StepStatus.WAITING_APPROVAL


async def test_retry_then_succeed(tmp_path: Path) -> None:
    client = FakeChatClient(["ok"], fail_times=1)
    engine = make_engine(tmp_path, client)
    template = WorkflowTemplate.model_validate(
        {
            "name": "t",
            "steps": [
                {
                    "id": "s1",
                    "type": "llm",
                    "provider": {"capability": "llm", "name": "kimi"},
                    "prompt": "p",
                    "max_retries": 1,
                }
            ],
        }
    )
    state = await engine.run(template, uuid4(), {}, auto_approve=True)
    assert state.status == "completed"
    assert state.steps[0].attempts == 2


async def test_exhausted_retries_raise_workflow_error(tmp_path: Path) -> None:
    client = FakeChatClient(["never"], fail_times=99)
    engine = make_engine(tmp_path, client)
    template = WorkflowTemplate.model_validate(
        {
            "name": "t",
            "steps": [
                {
                    "id": "s1",
                    "type": "llm",
                    "provider": {"capability": "llm", "name": "kimi"},
                    "prompt": "p",
                    "max_retries": 1,
                }
            ],
        }
    )
    with pytest.raises(WorkflowError, match="转人工处理"):
        await engine.run(template, uuid4(), {}, auto_approve=True)


async def test_state_persists_across_engine_instances(tmp_path: Path) -> None:
    client = FakeChatClient(["brief-json", "copy-json", "script-json"])
    engine = make_engine(tmp_path, client)
    template = load_template(TEMPLATE_DIR / "product_launch.yaml")
    await engine.run(template, uuid4(), {"product_docs": "d"}, auto_approve=False)

    engine2 = make_engine(tmp_path, client)
    loaded = engine2.load_state()
    assert loaded is not None
    assert loaded.status == "paused"
    assert loaded.context["product_brief"] == "brief-json"
