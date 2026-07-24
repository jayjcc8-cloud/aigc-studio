"""Tests for core domain models."""

from uuid import uuid4

import pytest
from aigc_core.models import (
    Character,
    Platform,
    Project,
    ProjectStatus,
    ReviewDecision,
    ReviewGate,
    ReviewStatus,
    Shot,
    ShotType,
    Story,
)


def test_create_project_defaults() -> None:
    project = Project(title="Test Drama")
    assert project.status == ProjectStatus.DRAFT
    assert project.version == 1
    assert project.cost_budget_usd is None


def test_story_serializes_platforms() -> None:
    story = Story(
        title="Hooked",
        target_platforms=[Platform.DOUYIN, Platform.YOUTUBE_SHORTS],
    )
    data = story.model_dump()
    assert data["target_platforms"] == ["douyin", "youtube_shorts"]


def test_shot_duration_bounds() -> None:
    with pytest.raises(ValueError):
        Shot(scene_id=uuid4(), index=1, duration_seconds=0.5)


def test_review_decision_replaces_same_gate() -> None:
    project = Project(title="Review Test")
    d1 = ReviewDecision(gate=ReviewGate.SCRIPT, status=ReviewStatus.PENDING)
    d2 = ReviewDecision(gate=ReviewGate.SCRIPT, status=ReviewStatus.APPROVED)
    project.add_decision(d1)
    project.add_decision(d2)
    assert len(project.review_decisions) == 1
    assert project.review_decisions[0].status == ReviewStatus.APPROVED


def test_character_reference_assets() -> None:
    char = Character(name="Alice", appearance="long black hair")
    assert char.name == "Alice"
    assert char.reference_asset_ids == []


def test_shot_type_enum() -> None:
    shot = Shot(scene_id=uuid4(), index=0, shot_type=ShotType.AERIAL)
    assert shot.shot_type == "aerial"
