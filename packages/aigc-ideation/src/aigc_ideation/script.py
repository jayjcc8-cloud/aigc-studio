"""Structured short-drama script generation from an LLM chat client."""

from __future__ import annotations

import json
from typing import Any

from aigc_core.models import (
    Character,
    ModelTier,
    Platform,
    Scene,
    Shot,
    ShotType,
    Story,
)
from pydantic import BaseModel, Field, ValidationError

from aigc_ideation.llm import ChatClient
from aigc_ideation.prompts import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt


class ScriptError(RuntimeError):
    """Raised when a valid script cannot be produced within the retry budget."""


class CharacterDraft(BaseModel):
    name: str
    age: int | None = None
    personality: str = ""
    appearance: str = ""
    voice_description: str = ""


class SceneDraft(BaseModel):
    index: int
    title: str = ""
    location: str = ""
    time_of_day: str = ""
    mood: str = ""
    description: str = ""


class ShotDraft(BaseModel):
    scene_index: int
    index: int
    shot_type: ShotType = ShotType.MEDIUM
    description: str = ""
    duration_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    prompt: str = ""
    negative_prompt: str = ""
    dialogue: str = ""
    narration: str = ""
    audio_mood: str = ""
    camera_direction: str = ""
    transition: str = "cut"
    model_tier: ModelTier = ModelTier.DRAFT
    max_attempts: int = Field(default=2, ge=1, le=5)
    budget_cny: float | None = Field(default=None, ge=0)


class StoryDraft(BaseModel):
    """LLM-facing script schema; converted to the core Story aggregate locally."""

    title: str
    hook: str = ""
    theme: str = ""
    characters: list[CharacterDraft] = Field(default_factory=list)
    scenes: list[SceneDraft] = Field(default_factory=list)
    shots: list[ShotDraft] = Field(default_factory=list)

    def to_story(self, platforms: list[Platform]) -> Story:
        """Convert the draft into the core Story, wiring scene/shot UUIDs."""
        characters = [
            Character(
                name=c.name,
                age=c.age,
                personality=c.personality,
                appearance=c.appearance,
                voice_description=c.voice_description,
            )
            for c in self.characters
        ]
        scenes = [
            Scene(
                index=s.index,
                title=s.title,
                location=s.location,
                time_of_day=s.time_of_day,
                mood=s.mood,
                description=s.description,
            )
            for s in self.scenes
        ]
        scene_by_index = {s.index: s for s in scenes}

        shots: list[Shot] = []
        for draft in self.shots:
            scene = scene_by_index.get(draft.scene_index)
            if scene is None:
                raise ScriptError(
                    f"shot {draft.index} references unknown scene_index " f"{draft.scene_index}"
                )
            shot = Shot(
                scene_id=scene.id,
                index=draft.index,
                shot_type=draft.shot_type,
                description=draft.description,
                duration_seconds=draft.duration_seconds,
                prompt=draft.prompt,
                negative_prompt=draft.negative_prompt,
                dialogue=draft.dialogue,
                narration=draft.narration,
                audio_mood=draft.audio_mood,
                camera_direction=draft.camera_direction,
                transition=draft.transition,
                model_tier=draft.model_tier,
                max_attempts=draft.max_attempts,
                budget_cny=draft.budget_cny,
            )
            scene.shot_ids.append(shot.id)
            shots.append(shot)

        return Story(
            title=self.title,
            hook=self.hook,
            theme=self.theme,
            target_platforms=platforms,
            characters=characters,
            scenes=scenes,
            shots=shots,
        )


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from raw LLM output, tolerating fences."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ScriptError("LLM output contains no JSON object")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ScriptError(f"invalid JSON in LLM output: {exc}") from exc
    if not isinstance(data, dict):
        raise ScriptError("LLM output JSON is not an object")
    return data


class ScriptGenerator:
    """Generates a validated Story from a creative brief via a chat client."""

    def __init__(self, client: ChatClient, max_retries: int = 2) -> None:
        self.client = client
        self.max_retries = max_retries

    async def generate(
        self,
        *,
        idea: str,
        platforms: list[Platform],
        total_duration_seconds: float = 30.0,
        episode_hint: str = "",
    ) -> Story:
        """Generate a script, retrying with error feedback on invalid output."""
        user = build_user_prompt(
            idea=idea,
            platforms=platforms,
            total_duration_seconds=total_duration_seconds,
            episode_hint=episode_hint,
        )
        last_error = ""
        for attempt in range(self.max_retries + 1):
            raw = await self.client.complete(system=SYSTEM_PROMPT, user=user)
            try:
                draft = StoryDraft.model_validate(_extract_json(raw))
                return draft.to_story(platforms)
            except (ScriptError, ValidationError) as exc:
                last_error = str(exc)
                if attempt >= self.max_retries:
                    break
                user = build_retry_prompt(last_error)
        raise ScriptError(
            f"failed to produce a valid script after {self.max_retries + 1} "
            f"attempts: {last_error}"
        )
