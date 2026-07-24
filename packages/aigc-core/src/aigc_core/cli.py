"""Command-line entry point for the AIGC studio."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from aigc_core.config import get_settings
from aigc_core.models import Platform

app = typer.Typer(help="AIGC short-drama studio CLI")
script_app = typer.Typer(help="Script generation commands")
app.add_typer(script_app, name="script")


@app.callback()
def main() -> None:
    """AIGC short-drama studio."""


@app.command()
def version() -> None:
    """Print the studio version."""
    typer.echo("aigc-studio 0.1.0")


@script_app.command("generate")
def script_generate(
    idea: str = typer.Option(..., "--idea", "-i", help="选题/创意一句话"),
    platform: list[str] = typer.Option(["douyin"], "--platform", "-p", help="目标平台，可多次指定"),
    duration: float = typer.Option(30.0, "--duration", "-d", help="目标总时长（秒）"),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="剧本 JSON 输出路径（默认打印到 stdout）"
    ),
) -> None:
    """Generate a structured short-drama script via the configured LLM."""
    # Deferred import keeps aigc-core usable without the ideation extras.
    from aigc_ideation import AnthropicChatClient, LlmConfig, ScriptGenerator

    settings = get_settings()
    if not settings.llm_api_key:
        raise typer.BadParameter("未配置 LLM_API_KEY。请复制 .env.example 为 .env 并填入密钥。")

    client = AnthropicChatClient(
        LlmConfig(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    )
    generator = ScriptGenerator(client)
    platforms = [Platform(p) for p in platform]
    story = asyncio.run(
        generator.generate(idea=idea, platforms=platforms, total_duration_seconds=duration)
    )
    payload = json.dumps(story.model_dump(mode="json"), ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"剧本已写入 {output}")
    else:
        typer.echo(payload)


if __name__ == "__main__":
    app()
