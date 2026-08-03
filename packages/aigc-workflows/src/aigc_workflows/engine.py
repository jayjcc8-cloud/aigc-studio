"""YAML-driven workflow engine for AIGC Studio OS.

A workflow template declares linear steps. Each step is one of:

- ``llm``: call an LLM provider, store the text output in context
- ``provider``: call an asset provider (video/tts/image/...), store the asset
- ``export``: write the standard export package from context

Every step records Task + GenerationRecord + CostRecord JSON state, so costs,
retries and adopted versions are always auditable (ADR 006).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from aigc_core.models import GenerationStatus
from aigc_core.os_models import (
    Approval,
    ApprovalStatus,
    CostRecord,
    CostType,
    GenerationRecord,
    Task,
    TaskStatus,
)
from aigc_core.provider import GenerationRequest
from aigc_core.registry import ProviderRegistry
from aigc_core.storage import ProjectStorage
from pydantic import BaseModel, Field


class WorkflowError(RuntimeError):
    """Raised when a workflow cannot proceed without human intervention."""


class StepType(StrEnum):
    LLM = "llm"
    PROVIDER = "provider"
    EXPORT = "export"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StepSpec(BaseModel):
    """One step declaration in a workflow template."""

    id: str
    type: StepType
    provider: dict[str, str] = Field(default_factory=dict)  # {capability, name}
    prompt: str = ""
    system: str = ""
    output_key: str = ""
    asset_type: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = False
    budget_cny: float | None = None
    max_retries: int = 1


class StepState(BaseModel):
    id: str
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    error: str = ""


class WorkflowTemplate(BaseModel):
    name: str
    description: str = ""
    steps: list[StepSpec]


class WorkflowState(BaseModel):
    """Persisted run state; enables pause/resume across CLI invocations."""

    template_name: str
    project_id: UUID
    context: dict[str, Any] = Field(default_factory=dict)
    steps: list[StepState]
    current_index: int = 0
    status: str = "running"  # running | paused | completed | failed


def load_template(path: Path) -> WorkflowTemplate:
    """Load a workflow template from a YAML file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return WorkflowTemplate.model_validate(data)


def _render(template: str, context: dict[str, Any]) -> str:
    """Render {placeholders} from context; missing keys render as empty."""
    return template.format_map(defaultdict(str, context))


class WorkflowEngine:
    """Executes workflow templates against a provider registry."""

    def __init__(self, registry: ProviderRegistry, storage: ProjectStorage) -> None:
        self.registry = registry
        self.storage = storage

    # ---------- public API ----------

    async def run(
        self,
        template: WorkflowTemplate,
        project_id: UUID,
        context: dict[str, Any] | None = None,
        *,
        auto_approve: bool = False,
        state: WorkflowState | None = None,
    ) -> WorkflowState:
        """Run (or resume) a workflow until completion, failure, or an
        approval gate pauses it."""
        if state is None:
            state = WorkflowState(
                template_name=template.name,
                project_id=project_id,
                context=context or {},
                steps=[StepState(id=s.id) for s in template.steps],
            )

        for index in range(state.current_index, len(template.steps)):
            spec = template.steps[index]
            step_state = state.steps[index]
            if step_state.status == StepStatus.SUCCEEDED:
                continue
            if step_state.status == StepStatus.WAITING_APPROVAL and not auto_approve:
                state.status = "paused"
                state.current_index = index
                self._save_state(state)
                return state

            state.current_index = index
            step_state.status = StepStatus.RUNNING
            try:
                await self._execute_step(spec, step_state, state, project_id)
            except WorkflowError as exc:
                step_state.status = StepStatus.FAILED
                step_state.error = str(exc)
                state.status = "failed"
                self._save_state(state)
                raise

            if spec.approval_required and not auto_approve:
                step_state.status = StepStatus.WAITING_APPROVAL
                self._record_approval(spec, state)
                state.status = "paused"
                state.current_index = index
                self._save_state(state)
                return state

            step_state.status = StepStatus.SUCCEEDED
            state.current_index = index + 1
            self._save_state(state)

        state.status = "completed"
        self._save_state(state)
        return state

    def approve(self, state: WorkflowState, reviewer: str = "", comment: str = "") -> None:
        """Mark the current waiting step as approved and update the approval record."""
        step = state.steps[state.current_index]
        if step.status != StepStatus.WAITING_APPROVAL:
            raise WorkflowError(
                f"step {step.id} is not waiting for approval (status={step.status})"
            )
        # Update the pending approval record with reviewer info.
        self._resolve_approval(state, reviewer, comment)
        step.status = StepStatus.SUCCEEDED
        state.current_index += 1
        state.status = "running"
        self._save_state(state)

    def pending_approval_text(self, state: WorkflowState) -> str:
        """Return the output awaiting human review, for CLI display."""
        step = state.steps[state.current_index]
        key = step.id
        return str(state.context.get(f"__text__{key}", ""))

    # ---------- step execution ----------

    async def _execute_step(
        self,
        spec: StepSpec,
        step_state: StepState,
        state: WorkflowState,
        project_id: UUID,
    ) -> None:
        if spec.type == StepType.EXPORT:
            self._execute_export(spec, state, project_id)
            return

        task = Task(
            project_id=project_id,
            task_type=spec.id,
            provider=spec.provider.get("name", ""),
            status=TaskStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        last_error = ""
        for attempt in range(spec.max_retries + 1):
            step_state.attempts = attempt + 1
            task.retry_count = attempt
            result = await self._call_provider(spec, state, project_id)
            if result.status == GenerationStatus.SUCCESS:
                task.status = TaskStatus.SUCCEEDED
                task.finished_at = datetime.utcnow()
                self._append_json("tasks", task)
                self._persist_step_records(task, spec, result)
                self._store_output(spec, result, state)
                return
            last_error = result.error_message
            self._append_json("tasks", task)
            self._persist_step_records(task, spec, result)

        task.status = TaskStatus.FAILED
        task.error_message = last_error
        task.finished_at = datetime.utcnow()
        self._append_json("tasks", task)
        raise WorkflowError(
            f"step {spec.id!r} failed after {spec.max_retries + 1} attempts: "
            f"{last_error}. 转人工处理。"
        )

    async def _call_provider(self, spec: StepSpec, state: WorkflowState, project_id: UUID):  # type: ignore[no-untyped-def]
        from aigc_core.models import AssetType

        provider = self.registry.get(spec.provider["capability"], spec.provider["name"])
        params = dict(spec.params)
        if spec.system:
            params["system"] = _render(spec.system, state.context)
        asset_type = (
            AssetType(spec.asset_type)
            if spec.asset_type
            else (AssetType.SCRIPT if spec.type == StepType.LLM else AssetType.VIDEO)
        )
        request = GenerationRequest(
            project_id=project_id,
            operation=spec.id,
            asset_type=asset_type,
            prompt=_render(spec.prompt, state.context),
            params=params,
        )
        return await provider.generate(request)

    def _store_output(self, spec: StepSpec, result: Any, state: WorkflowState) -> None:
        key = spec.output_key or spec.id
        if result.raw_response and "text" in result.raw_response:
            state.context[key] = result.raw_response["text"]
            state.context[f"__text__{spec.id}"] = result.raw_response["text"]
        if result.asset is not None:
            state.context[key] = result.asset.uri

    # ---------- export ----------

    def _execute_export(self, spec: StepSpec, state: WorkflowState, project_id: UUID) -> None:
        package_dir = self.storage.dir("exports") / spec.params.get("package_name", "package")
        sections = spec.params.get(
            "sections",
            [
                "01-copy",
                "02-images",
                "03-video",
                "04-subtitles",
                "05-audio",
                "06-launch-posts",
                "07-license-records",
            ],
        )
        for section in sections:
            (package_dir / section).mkdir(parents=True, exist_ok=True)

        # Write every text output declared in `files` to its target section.
        for rel_path, context_key in spec.params.get("files", {}).items():
            text = str(state.context.get(context_key, ""))
            target = package_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

        readme = package_dir / "README.md"
        lines = [
            f"# 交付包：{state.template_name}",
            "",
            f"- 项目 ID：{project_id}",
            f"- 生成时间：{datetime.utcnow().isoformat(timespec='seconds')}Z",
            f"- 状态：{'待终审' if state.status != 'completed' else '已完成'}",
            "",
            "本内容包含 AI 生成素材，发布前请按《人工智能生成合成内容标识办法》"
            "添加显式标识并核对 07-license-records 中的授权记录。",
        ]
        readme.write_text("\n".join(lines), encoding="utf-8")
        state.context[spec.output_key or spec.id] = str(package_dir)

    # ---------- persistence ----------

    def _persist_step_records(self, task: Task, spec: StepSpec, result: Any) -> None:
        generation = GenerationRecord(
            task_id=task.id,
            provider=spec.provider.get("name", ""),
            prompt=task.input_payload.get("prompt", ""),
            cost_cny=result.cost_usd,
            result_asset_id=result.asset.id if result.asset else None,
            error_message=result.error_message,
        )
        self._append_json("generations", generation)
        cost = CostRecord(
            project_id=task.project_id,
            task_id=task.id,
            cost_type=CostType.LLM if spec.type == StepType.LLM else CostType.VIDEO,
            provider=spec.provider.get("name", ""),
            amount_cny=result.cost_usd,
            description=f"step:{spec.id} attempt:{task.retry_count + 1}",
        )
        self._append_json("costs", cost)

    def _record_approval(self, spec: StepSpec, state: WorkflowState) -> None:
        approval = Approval(
            project_id=state.project_id,
            entity_type="workflow_step",
            entity_id=state.project_id,  # step identified via comment below
            status=ApprovalStatus.PENDING,
            comment=f"step:{spec.id}",
        )
        self._append_json("approvals", approval)

    def _resolve_approval(self, state: WorkflowState, reviewer: str, comment: str) -> None:
        """Record the resolution of a pending approval."""
        approval = Approval(
            project_id=state.project_id,
            entity_type="workflow_step",
            entity_id=state.project_id,
            status=ApprovalStatus.APPROVED,
            reviewer=reviewer,
            comment=comment,
        )
        self._append_json("approvals", approval)

    def _append_json(self, name: str, record: BaseModel) -> None:
        path = self.storage.state_file(name)
        records: list[dict[str, Any]] = []
        if path.exists():
            records = json.loads(path.read_text(encoding="utf-8"))
        records.append(record.model_dump(mode="json"))
        path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _save_state(self, state: WorkflowState) -> None:
        path = self.storage.state_file("workflow")
        path.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def load_state(self) -> WorkflowState | None:
        """Load persisted workflow state, if any."""
        path = self.storage.state_file("workflow")
        if not path.exists():
            return None
        return WorkflowState.model_validate_json(path.read_text(encoding="utf-8"))
