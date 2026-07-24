"""Anthropic-compatible chat client for LLM-powered script generation.

Works against the official Anthropic API and any Anthropic-compatible endpoint
(e.g. Moonshot's ``/anthropic`` proxy), selected purely by configuration.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field


class LlmError(RuntimeError):
    """Raised when the LLM endpoint returns an error or malformed payload."""


class LlmConfig(BaseModel):
    """Configuration for an Anthropic-compatible chat endpoint."""

    base_url: str = "https://api.anthropic.com"
    api_key: str
    model: str = "claude-sonnet-4-5"
    timeout_seconds: float = 120.0
    max_tokens: int = Field(default=4096, ge=256)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)


class ChatClient(Protocol):
    """Minimal chat-completion interface used by the ideation package."""

    async def complete(self, *, system: str, user: str) -> str:
        """Return the assistant's text reply for a system/user prompt pair."""
        ...


class AnthropicChatClient:
    """Chat client for the Anthropic Messages API (and compatible proxies)."""

    def __init__(
        self,
        config: LlmConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport

    async def complete(self, *, system: str, user: str) -> str:
        url = f"{self.config.base_url.rstrip('/')}/v1/messages"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds, transport=self._transport
        ) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise LlmError(f"LLM request failed: {exc}") from exc

        if response.status_code != 200:
            raise LlmError(f"LLM endpoint returned {response.status_code}: {response.text[:500]}")

        data = response.json()
        try:
            blocks = data["content"]
            return "".join(block["text"] for block in blocks if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise LlmError(f"Malformed LLM response: {data!r:.500}") from exc
