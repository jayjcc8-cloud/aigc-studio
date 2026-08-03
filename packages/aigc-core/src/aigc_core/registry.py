"""Provider registry: workflows reference providers by (capability, name)."""

from __future__ import annotations

from typing import Protocol

from aigc_core.models import GenerationStatus
from aigc_core.provider import (
    BaseProvider,
    GenerationRequest,
    GenerationResult,
    ProviderConfig,
)

# Capability labels used in workflow templates.
LLM = "llm"
VIDEO = "video"
IMAGE = "image"
TTS = "tts"
MUSIC = "music"
SFX = "sfx"
SUBTITLE = "subtitle"


class ChatClientLike(Protocol):
    """Structural type for text-in/text-out chat clients."""

    async def complete(self, *, system: str, user: str) -> str: ...


class ProviderRegistry:
    """Maps (capability, name) to provider instances.

    Business code never imports a concrete provider class; it asks the
    registry for whatever is configured for that capability slot.
    """

    def __init__(self) -> None:
        self._providers: dict[tuple[str, str], BaseProvider] = {}

    def register(self, capability: str, provider: BaseProvider) -> None:
        self._providers[(capability, provider.name)] = provider

    def get(self, capability: str, name: str) -> BaseProvider:
        try:
            return self._providers[(capability, name)]
        except KeyError:
            available = ", ".join(f"{cap}/{n}" for (cap, n) in sorted(self._providers))
            raise KeyError(
                f"no provider registered for ({capability!r}, {name!r}); "
                f"available: {available or 'none'}"
            ) from None

    def names(self, capability: str) -> list[str]:
        """Return all registered provider names for a capability."""
        return sorted(n for (cap, n) in self._providers if cap == capability)


class LlmProviderAdapter(BaseProvider):
    """Adapts a ChatClient (text-in/text-out) to the provider interface.

    LLM calls produce text, not file assets; the text is returned in
    ``GenerationResult.raw_response["text"]`` for the workflow engine.
    """

    def __init__(self, name: str, client: ChatClientLike) -> None:
        super().__init__(ProviderConfig(name=name))
        self._client = client

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        try:
            text = await self._client.complete(
                system=str(request.params.get("system", "")),
                user=request.prompt,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as FAILED result
            return GenerationResult(status=GenerationStatus.FAILED, error_message=str(exc))
        return GenerationResult(status=GenerationStatus.SUCCESS, raw_response={"text": text})

    async def healthcheck(self) -> bool:
        return True

    def estimate_cost(self, request: GenerationRequest) -> float:
        """Rough CNY heuristic until token usage is tracked (~4 chars/token)."""
        return round(len(request.prompt) / 4 * 0.000001 * 3, 6)
