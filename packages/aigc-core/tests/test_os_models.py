"""Tests for the Studio OS data layer."""

from uuid import uuid4

from aigc_core.os_models import (
    Approval,
    ApprovalStatus,
    ContentItem,
    CostRecord,
    CostType,
    GenerationRecord,
    KnowledgeBase,
    ProjectType,
    Task,
    TaskStatus,
    Workspace,
)


def test_content_item_wraps_typed_payload() -> None:
    item = ContentItem(
        project_id=uuid4(),
        content_type="drama_script",
        title="雨夜 第1集",
        payload={"story": {"title": "雨夜黑伞"}},
    )
    assert item.status == "draft"
    assert item.payload["story"]["title"] == "雨夜黑伞"


def test_task_defaults_and_status_flow() -> None:
    task = Task(project_id=uuid4(), task_type="generate_video")
    assert task.status == TaskStatus.QUEUED
    task.status = TaskStatus.WAITING_PROVIDER
    assert task.status == "waiting_provider"


def test_generation_record_keeps_failures() -> None:
    gen = GenerationRecord(task_id=uuid4(), provider="seedance", error_message="boom")
    assert gen.accepted is None
    assert gen.error_message == "boom"


def test_approval_supersedes_review_decision() -> None:
    approval = Approval(
        project_id=uuid4(),
        entity_type="content_item",
        entity_id=uuid4(),
        status=ApprovalStatus.REVISION_REQUIRED,
        comment="产品卖点第 2 条夸大，请修改",
    )
    assert approval.status == "revision_required"


def test_knowledge_base_and_workspace() -> None:
    ws = Workspace(name="studio-main")
    kb = KnowledgeBase(
        project_id=uuid4(), name="品牌语气", knowledge_type="brand_voice", content="专业、克制"
    )
    assert ws.default_language == "zh"
    assert kb.version == 1


def test_cost_record_types() -> None:
    cost = CostRecord(project_id=uuid4(), cost_type=CostType.VIDEO, amount_cny=0.9, provider="wan")
    assert cost.cost_type == "video"
    assert ProjectType.PRODUCT_LAUNCH.value == "product_launch"
