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
video_app = typer.Typer(help="Video generation commands")
app.add_typer(script_app, name="script")
app.add_typer(video_app, name="video")


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


@video_app.command("generate")
def video_generate(
    prompt: str = typer.Option(..., "--prompt", help="英文视频生成 prompt"),
    duration: int = typer.Option(5, "--duration", "-d", help="时长（秒，4-15）"),
    aspect_ratio: str = typer.Option("9:16", "--aspect-ratio", "-a"),
    resolution: str = typer.Option("720p", "--resolution", "-r"),
    image_url: str | None = typer.Option(
        None, "--image-url", help="参考图公网 URL（提供则为图生视频）"
    ),
    audio: bool = typer.Option(False, "--audio", help="生成同步音效/配乐"),
) -> None:
    """Generate one video clip via the configured Seedance provider."""
    from aigc_generation import SeedanceConfig, SeedanceVideoProvider

    from aigc_core.models import AssetType, GenerationStatus
    from aigc_core.provider import GenerationRequest

    settings = get_settings()
    if not settings.seedance_api_key:
        raise typer.BadParameter("未配置 SEEDANCE_API_KEY，请填入 .env。")

    provider = SeedanceVideoProvider(
        SeedanceConfig(
            base_url=settings.seedance_base_url,
            api_key=settings.seedance_api_key,
            model=settings.seedance_model,
            max_poll_seconds=settings.seedance_max_poll_seconds,
        )
    )
    params: dict[str, object] = {
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "generate_audio": audio,
    }
    if image_url:
        params["image_url"] = image_url

    from uuid import uuid4

    result = asyncio.run(
        provider.generate(
            GenerationRequest(
                project_id=uuid4(),
                operation="cli-test",
                asset_type=AssetType.VIDEO,
                prompt=prompt,
                params=params,
            )
        )
    )
    if result.status != GenerationStatus.SUCCESS or result.asset is None:
        typer.secho(f"生成失败: {result.error_message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho(
        f"生成成功: {result.asset.uri}（耗时 {result.latency_seconds:.0f}s，"
        f"credits={result.asset.metadata.get('credits')}）",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    app()
