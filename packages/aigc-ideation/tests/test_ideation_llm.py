"""Tests for the Anthropic-compatible chat client."""

import json

import httpx
import pytest
from aigc_ideation import AnthropicChatClient, LlmConfig, LlmError


def make_client(handler, **overrides) -> AnthropicChatClient:  # type: ignore[no-untyped-def]
    config = LlmConfig(api_key="test-key", **overrides)
    return AnthropicChatClient(config, transport=httpx.MockTransport(handler))


async def test_complete_returns_concatenated_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "test-key"
        body = json.loads(request.content)
        assert body["model"] == "claude-sonnet-4-5"
        assert body["messages"][0]["content"] == "user prompt"
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "hello "},
                    {"type": "text", "text": "world"},
                ]
            },
        )

    client = make_client(handler)
    result = await client.complete(system="sys", user="user prompt")
    assert result == "hello world"


async def test_complete_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    client = make_client(handler)
    with pytest.raises(LlmError, match="429"):
        await client.complete(system="s", user="u")


async def test_complete_raises_on_malformed_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    client = make_client(handler)
    with pytest.raises(LlmError, match="Malformed"):
        await client.complete(system="s", user="u")


async def test_custom_base_url_and_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://api.moonshot.cn/anthropic")
        body = json.loads(request.content)
        assert body["model"] == "kimi-k3"
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    client = make_client(handler, base_url="https://api.moonshot.cn/anthropic", model="kimi-k3")
    assert await client.complete(system="s", user="u") == "ok"
