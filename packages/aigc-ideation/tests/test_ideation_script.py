"""Tests for structured script generation."""

import json
from typing import Any

import pytest
from aigc_core.models import Platform
from aigc_ideation import ScriptError, ScriptGenerator

VALID_DRAFT: dict[str, Any] = {
    "title": "雨夜",
    "hook": "陌生人递来一把黑伞",
    "theme": "urban suspense",
    "characters": [
        {
            "name": "林晚",
            "age": 26,
            "personality": "冷静敏锐",
            "appearance": "young Chinese woman, short black hair, beige trench coat",
            "voice_description": "冷静女声",
        }
    ],
    "scenes": [
        {
            "index": 0,
            "title": "雨夜街头",
            "location": "市中心街道",
            "time_of_day": "夜晚",
            "mood": "悬疑",
            "description": "大雨中的霓虹街道",
        }
    ],
    "shots": [
        {
            "scene_index": 0,
            "index": 0,
            "shot_type": "wide",
            "description": "全景雨夜街道",
            "duration_seconds": 5,
            "prompt": "cinematic wide shot, rainy neon street at night, dolly in",
            "negative_prompt": "blurry, low quality",
            "dialogue": "",
            "narration": "这座城市的雨，从不无缘无故地下。",
            "audio_mood": "tense-mandarin-female",
            "camera_direction": "dolly in",
            "transition": "cut",
        },
        {
            "scene_index": 0,
            "index": 1,
            "shot_type": "close_up",
            "description": "林晚接过黑伞",
            "duration_seconds": 6,
            "prompt": "close up, young Chinese woman takes a black umbrella from a stranger",
            "negative_prompt": "deformed hands",
            "dialogue": "我们不认识吧？",
            "narration": "",
            "audio_mood": "calm-mandarin-female",
            "camera_direction": "static",
            "transition": "cut",
        },
    ],
}


class FakeChatClient:
    """Chat client returning a queue of canned responses."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    async def complete(self, *, system: str, user: str) -> str:
        self.calls.append(user)
        if not self.responses:
            raise AssertionError("no more canned responses")
        return self.responses.pop(0)


async def test_generate_returns_wired_story() -> None:
    client = FakeChatClient([json.dumps(VALID_DRAFT, ensure_ascii=False)])
    generator = ScriptGenerator(client)
    story = await generator.generate(
        idea="雨夜神秘人", platforms=[Platform.DOUYIN, Platform.YOUTUBE_SHORTS]
    )

    assert story.title == "雨夜"
    assert story.target_platforms == ["douyin", "youtube_shorts"]
    assert len(story.shots) == 2
    scene = story.scenes[0]
    assert all(shot.scene_id == scene.id for shot in story.shots)
    assert scene.shot_ids == [shot.id for shot in story.shots]
    assert story.characters[0].name == "林晚"


async def test_generate_strips_markdown_fence() -> None:
    fenced = "```json\n" + json.dumps(VALID_DRAFT, ensure_ascii=False) + "\n```"
    client = FakeChatClient([fenced])
    story = await ScriptGenerator(client).generate(idea="雨夜神秘人", platforms=[Platform.DOUYIN])
    assert story.title == "雨夜"


async def test_generate_retries_on_invalid_output() -> None:
    client = FakeChatClient(["这不是JSON", json.dumps(VALID_DRAFT, ensure_ascii=False)])
    story = await ScriptGenerator(client).generate(idea="雨夜神秘人", platforms=[Platform.DOUYIN])
    assert story.title == "雨夜"
    assert len(client.calls) == 2
    assert "无法通过校验" in client.calls[1]


async def test_generate_raises_after_retry_budget() -> None:
    client = FakeChatClient(["bad"] * 5)
    generator = ScriptGenerator(client, max_retries=1)
    with pytest.raises(ScriptError, match="failed to produce"):
        await generator.generate(idea="x", platforms=[Platform.DOUYIN])
    assert len(client.calls) == 2


async def test_shot_with_unknown_scene_index_retries_then_fails() -> None:
    draft = dict(VALID_DRAFT)
    bad_shot = dict(VALID_DRAFT["shots"][0])
    bad_shot["scene_index"] = 99
    draft["shots"] = [bad_shot]
    client = FakeChatClient([json.dumps(draft)] * 5)
    generator = ScriptGenerator(client, max_retries=1)
    with pytest.raises(ScriptError, match="unknown scene_index"):
        await generator.generate(idea="x", platforms=[Platform.DOUYIN])
