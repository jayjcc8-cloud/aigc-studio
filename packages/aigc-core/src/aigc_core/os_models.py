"""Studio OS data layer: generic models shared by all workflow templates.

See ADR 006. Design rule: ContentItem is a generic shell with a typed payload,
so new business workflows plug in without schema migration.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ProjectType(StrEnum):
    """Business category of a project (one per workflow template)."""

    PRODUCT_LAUNCH = "product_launch"
    VIDEO_LOCALIZATION = "video_localization"
    GAME_MARKETING = "game_marketing"
    KNOWLEDGE_CONTENT = "knowledge_content"
    ORIGINAL_IP = "original_ip"
    AI_DRAMA = "ai_drama"
    CUSTOM = "custom"


class Workspace(BaseModel):
    """A studio or client space; isolates projects and assets."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    workspace_type: str = "studio"  # studio | client
    default_language: str = "zh"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeBase(BaseModel):
    """Long-lived project context: brand voice, IP canon, prohibitions."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    name: str
    knowledge_type: str = ""  # product_info | brand_voice | glossary | canon | prohibition
    content: str = ""
    version: int = 1
    source_asset_id: UUID | None = None
    status: str = "active"  # active | archived
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContentItem(BaseModel):
    """A unit of content to produce or manage.

    Generic shell + typed payload: e.g. content_type="drama_script" wraps the
    drama workflow's Story document; "product_brief" wraps a product summary.
    """

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    parent_id: UUID | None = None
    content_type: str
    title: str = ""
    content: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    language: str = "zh"
    status: str = "draft"  # draft | in_review | approved | rejected
    sort_order: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskStatus(StrEnum):
    """Unified async task states (per transformation spec)."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_PROVIDER = "waiting_provider"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """A unit of work executed by the workflow engine."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    content_item_id: UUID | None = None
    task_type: str
    provider: str = ""
    model: str = ""
    status: TaskStatus = TaskStatus.QUEUED
    priority: int = 0
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    estimated_cost_cny: float = 0.0
    actual_cost_cny: float = 0.0
    retry_count: int = 0
    error_message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None


class GenerationRecord(BaseModel):
    """Full record of one model generation call, including failures."""

    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    provider: str = ""
    model: str = ""
    model_version: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_cny: float = 0.0
    result_asset_id: UUID | None = None
    quality_score: float | None = None
    accepted: bool | None = None
    error_message: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VersionRecord(BaseModel):
    """Version history for content items and assets."""

    id: UUID = Field(default_factory=uuid4)
    entity_type: str  # content_item | asset
    entity_id: UUID
    version_number: int
    change_summary: str = ""
    created_by: str = "system"  # system | human reviewer name
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalStatus(StrEnum):
    """Human approval outcomes."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUIRED = "revision_required"


class Approval(BaseModel):
    """Human approval record for any entity (supersedes ReviewDecision)."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    entity_type: str  # content_item | asset | export
    entity_id: UUID
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer: str = ""
    comment: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExportRecord(BaseModel):
    """A final deliverable export."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    export_type: str = ""  # launch_package | episode | social_set
    platform: str = ""
    language: str = "zh"
    aspect_ratio: str = ""
    resolution: str = ""
    file_asset_id: UUID | None = None
    path: str = ""
    status: str = "completed"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CostType(StrEnum):
    """Cost categories for project-level P&L."""

    LLM = "llm"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    STORAGE = "storage"
    SERVER = "server"
    LICENSED_ASSET = "licensed_asset"
    MANUAL_WORK = "manual_work"
    OTHER = "other"


class CostRecord(BaseModel):
    """One cost entry; aggregates into project-level P&L."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    task_id: UUID | None = None
    cost_type: CostType = CostType.OTHER
    provider: str = ""
    amount_cny: float = 0.0
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
