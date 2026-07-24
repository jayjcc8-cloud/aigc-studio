"""Core domain models for the AIGC short-drama studio."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Platform(StrEnum):
    """Distribution platforms supported by the studio."""

    DOUYIN = "douyin"
    KUAISHOU = "kuaishou"
    XIAOHONGSHU = "xiaohongshu"
    BILIBILI = "bilibili"
    YOUTUBE = "youtube"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM = "instagram"
    INSTAGRAM_REELS = "instagram_reels"
    TIKTOK = "tiktok"


class AssetType(StrEnum):
    """Types of creative assets produced by the pipeline."""

    SCRIPT = "script"
    STORYBOARD = "storyboard"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    MUSIC = "music"
    SFX = "sfx"
    SUBTITLE = "subtitle"


class ShotType(StrEnum):
    """Common shot types used in short-drama storyboards."""

    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"
    POV = "pov"
    AERIAL = "aerial"
    INSERT = "insert"


class ProjectStatus(StrEnum):
    """High-level status of a short-drama project."""

    DRAFT = "draft"
    SCRIPT_REVIEW = "script_review"
    STORYBOARD_REVIEW = "storyboard_review"
    PRODUCTION = "production"
    EDITING = "editing"
    FINAL_REVIEW = "final_review"
    EXPORTED = "exported"
    PUBLISHED = "published"


class ReviewGate(StrEnum):
    """Named checkpoints where humans approve or reject work."""

    SCRIPT = "script"
    STORYBOARD = "storyboard"
    FINAL = "final"


class ReviewStatus(StrEnum):
    """Outcome of a review checkpoint."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class GenerationStatus(StrEnum):
    """Status of a provider generation call."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class Character(BaseModel):
    """A character appearing in the short drama."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    name: str
    age: int | None = None
    personality: str = ""
    appearance: str = ""
    voice_description: str = ""
    reference_asset_ids: list[UUID] = Field(default_factory=list)


class Shot(BaseModel):
    """A single camera shot in a scene."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    scene_id: UUID
    index: int
    shot_type: ShotType = ShotType.MEDIUM
    description: str = ""
    duration_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    prompt: str = ""
    negative_prompt: str = ""
    reference_asset_ids: list[UUID] = Field(default_factory=list)
    dialogue: str = ""
    narration: str = ""
    audio_mood: str = ""
    camera_direction: str = ""
    transition: str = "cut"


class Scene(BaseModel):
    """A narrative scene containing one or more shots."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    index: int
    title: str = ""
    location: str = ""
    time_of_day: str = ""
    mood: str = ""
    description: str = ""
    shot_ids: list[UUID] = Field(default_factory=list)


class Story(BaseModel):
    """Structured short-drama script."""

    model_config = ConfigDict(use_enum_values=True)

    title: str
    hook: str = ""
    theme: str = ""
    target_platforms: list[Platform] = Field(default_factory=list)
    characters: list[Character] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)


class Asset(BaseModel):
    """A generated or imported creative asset."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    asset_type: AssetType
    name: str
    uri: str = ""
    mime_type: str = ""
    provider: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = 0.0
    status: GenerationStatus = GenerationStatus.SUCCESS
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewDecision(BaseModel):
    """Human approval or rejection at a review gate."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    gate: ReviewGate
    reviewer: str = ""
    status: ReviewStatus = ReviewStatus.PENDING
    comment: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Project(BaseModel):
    """Root aggregate for one short-drama episode or series entry."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    target_platforms: list[Platform] = Field(default_factory=list)
    story: Story | None = None
    assets: list[Asset] = Field(default_factory=list)
    review_decisions: list[ReviewDecision] = Field(default_factory=list)
    cost_budget_usd: float | None = None
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def add_decision(self, decision: ReviewDecision) -> None:
        """Record a new review decision, replacing any prior one for the same gate."""
        self.review_decisions = [d for d in self.review_decisions if d.gate != decision.gate]
        self.review_decisions.append(decision)
        self.updated_at = datetime.utcnow()

    def total_cost(self) -> float:
        """Return the total recorded cost of generated assets."""
        return sum(asset.cost_usd for asset in self.assets)
