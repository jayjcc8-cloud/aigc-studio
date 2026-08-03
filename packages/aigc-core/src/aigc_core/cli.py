"""Command-line entry point for the AIGC studio."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import typer

from aigc_core.config import get_settings
from aigc_core.models import Platform, Project
from aigc_core.os_models import KnowledgeBase
from aigc_core.storage import ProjectStorage

app = typer.Typer(help="AIGC Studio OS — 多模态内容生产与项目交付系统")
script_app = typer.Typer(help="Script generation commands")
video_app = typer.Typer(help="Video generation commands")
project_app = typer.Typer(help="Project management commands")
kb_app = typer.Typer(help="Knowledge base commands")
workflow_app = typer.Typer(help="Workflow run & review commands")
export_app = typer.Typer(help="Export inspection commands")

app.add_typer(script_app, name="script")
app.add_typer(video_app, name="video")
app.add_typer(project_app, name="project")
app.add_typer(kb_app, name="kb")
app.add_typer(workflow_app, name="workflow")
app.add_typer(export_app, name="export")


@app.callback()
def main() -> None:
    """AIGC Studio OS."""


# ── shared helpers ──────────────────────────────────────────────────────


async def _run_workflow_standalone(
    template_name: str, project_id, storage: ProjectStorage, context: dict[str, object]
) -> None:
    """Run or resume a workflow template, printing step status."""
    from aigc_audio import DummyMusicProvider, DummySfxProvider, DummySubtitleProvider
    from aigc_audio import DummyTtsProvider as AudioDummyTts
    from aigc_generation import DummyImageProvider, DummyVideoProvider
    from aigc_ideation import AnthropicChatClient, LlmConfig
    from aigc_workflows import WorkflowEngine, WorkflowError, load_template

    from aigc_core.provider import ProviderConfig
    from aigc_core.registry import LlmProviderAdapter, ProviderRegistry

    settings = get_settings()

    # Build registry
    registry = ProviderRegistry()
    registry.register("video", DummyVideoProvider(ProviderConfig(name="dummy-video")))
    registry.register("image", DummyImageProvider(ProviderConfig(name="dummy-image")))
    registry.register("tts", AudioDummyTts(ProviderConfig(name="dummy-tts")))
    registry.register("music", DummyMusicProvider(ProviderConfig(name="dummy-music")))
    registry.register("sfx", DummySfxProvider(ProviderConfig(name="dummy-sfx")))
    registry.register("subtitle", DummySubtitleProvider(ProviderConfig(name="dummy-subtitle")))

    if settings.llm_api_key:
        llm_client = AnthropicChatClient(
            LlmConfig(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        )
        registry.register("llm", LlmProviderAdapter("kimi", llm_client))
    else:
        # Fallback fake LLM so the workflow doesn't crash on missing key;
        # real text generation won't work.
        class _FakeLLM:
            async def complete(
                self, *, system: str, user: str
            ) -> str:  # noqa: ARG002  # noqa: ARG002
                _ = (system, user)
                return '{"error":"LLM_API_KEY not configured"}'

        registry.register("llm", LlmProviderAdapter("kimi", _FakeLLM()))

    template_dir = (
        Path(__file__).parent.parent
        / ".."
        / ".."
        / "aigc-workflows"
        / "src"
        / "aigc_workflows"
        / "templates"
    )
    engine = WorkflowEngine(registry, storage)
    existing = engine.load_state()

    if existing and existing.status == "paused":
        typer.secho(
            "发现暂停的工作流状态，使用 resume 继续或 --restart 重新开始。", fg=typer.colors.YELLOW
        )
        return

    template = load_template(template_dir / f"{template_name}.yaml")
    typer.secho(f"启动模板: {template.name}", fg=typer.colors.CYAN)

    try:
        state = await engine.run(
            template,
            project_id,
            context | {"_input": context.get("product_docs", "")[:120]},
            auto_approve=False,
        )
    except WorkflowError as exc:
        typer.secho(f"工作流失败: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    if state.status == "paused":
        step = state.steps[state.current_index]
        typer.secho(f'⏸  暂停: 步骤 "{step.id}" 等待审核', fg=typer.colors.YELLOW)
        text = engine.pending_approval_text(state)
        typer.echo(f"\n--- 待审核内容 (前 500 字) ---\n{text[:500]}\n")
        typer.echo("审核通过后执行: aigc workflow approve")
    else:
        _print_completion(state)


def _print_completion(state: object) -> None:  # type: ignore[no-untyped-def]
    state_ctx: dict[str, object] = state.context if hasattr(state, "context") else {}
    typer.secho(f"✅ 工作流完成 ({state.status})", fg=typer.colors.GREEN)
    export_path = state_ctx.get("package") or state_ctx.get("product_brief", "export/")
    typer.echo(f"  package/brief: {export_path}")
    for f in sorted(Path(str(export_path)).rglob("*")):
        if f.is_file():
            typer.echo(f"  {f}")


# ── common commands ─────────────────────────────────────────────────────


@app.command()
def version() -> None:
    """Print the studio version."""
    typer.echo("aigc-studio 0.1.0")


# ── script ──────────────────────────────────────────────────────────────


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


# ── video ───────────────────────────────────────────────────────────────


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


# ── project ─────────────────────────────────────────────────────────────


@project_app.command("create")
def project_create(
    name: str = typer.Option(..., "--name", "-n", help="项目名称"),
    project_type: str = typer.Option(
        "product_launch", "--type", "-t", help="项目类型: product_launch | ai_drama | custom 等"
    ),
    client: str = typer.Option("", "--client", "-c", help="客户名称"),
    workspace: str = typer.Option("default", "--workspace", "-w", help="工作区 ID"),
) -> None:
    """Create a project with a standard storage layout."""
    project = Project(
        title=name,
        project_type=project_type,
        client_name=client,
        workspace_id=None if workspace == "default" else __import__("uuid").UUID(workspace),
    )
    storage = ProjectStorage(project.id, workspace_id=workspace)
    path = storage.save_project(project)
    typer.secho(f"项目已创建: {project.id}", fg=typer.colors.GREEN)
    typer.echo(f"  name: {name}")
    typer.echo(f"  type: {project_type}")
    typer.echo(f"  workspace: {workspace}")
    typer.echo(f"  file: {path}")


@project_app.command("ls")
def project_list(
    workspace: str = typer.Option("default", "--workspace", "-w"),
) -> None:
    """List projects under a workspace."""
    root = get_settings().projects_dir / workspace
    if not root.exists():
        typer.echo("(empty)")
        return
    for pid in sorted(root.iterdir()):
        src = pid / "source" / "project.json"
        if src.exists():
            try:
                proj = Project.model_validate_json(src.read_text())
                typer.echo(
                    f"  {proj.id}  {proj.project_type:20s}  {proj.client_name:16s}  {proj.title}"
                )
            except Exception:
                typer.echo(f"  {pid.name:38s}  (corrupt project.json)")
        else:
            typer.echo(f"  {pid.name:38s}  (no project.json)")


# ── knowledge base ─────────────────────────────────────────────────────


@kb_app.command("add")
def kb_add(
    project_id: str = typer.Option(..., "--project", help="项目 UUID"),
    name: str = typer.Option(..., "--name", help="知识条目名称"),
    knowledge_type: str = typer.Option(
        ..., "--type", "-t", help="类型: product_info|brand_voice|glossary|canon|prohibition"
    ),
    content: str = typer.Option(..., "--content", "-c", help="内容"),
    workspace: str = typer.Option("default", "--workspace", "-w"),
) -> None:
    """Add a knowledge-base entry to a project."""
    from uuid import UUID

    kb = KnowledgeBase(
        project_id=UUID(project_id),
        name=name,
        knowledge_type=knowledge_type,
        content=content,
    )
    storage = ProjectStorage(project_id, workspace_id=workspace)
    path = storage.save_knowledge_base(kb)
    typer.secho(f"知识条目已追加: {path}", fg=typer.colors.GREEN)


@kb_app.command("ls")
def kb_list(
    project_id: str = typer.Option(..., "--project", help="项目 UUID"),
    workspace: str = typer.Option("default", "--workspace", "-w"),
) -> None:
    """List knowledge-base entries for a project."""
    storage = ProjectStorage(project_id, workspace_id=workspace)
    items = storage.list_kb()
    if not items:
        typer.echo("(empty)")
        return
    for item in items:
        typer.echo(
            f"  {item.get('knowledge_type', ''):20s}  {item.get('name', ''):30s}  {item.get('content', '')[:60]}"
        )


# ── workflow ────────────────────────────────────────────────────────────


@workflow_app.command("run")
def workflow_run(
    project_id: str = typer.Option(..., "--project", help="项目 UUID"),
    template: str = typer.Option(
        "product_launch", "--template", "-t", help="模板名: product_launch | ai_drama"
    ),
    product_docs: str = typer.Option(
        "", "--docs", help="产品资料文本（product_launch 模板的输入端）"
    ),
    workspace: str = typer.Option("default", "--workspace", "-w"),
    restart: bool = typer.Option(False, "--restart", help="丢弃旧状态，从头开始"),
) -> None:
    """Run (or resume) a workflow template for a project."""
    from uuid import UUID

    pid = UUID(project_id)
    storage = ProjectStorage(project_id, workspace_id=workspace)

    if restart:
        state_file = storage.state_file("workflow")
        if state_file.exists():
            state_file.unlink()
            typer.echo("已丢弃旧状态，重新开始。")

    context: dict[str, object] = {}
    if product_docs:
        context["product_docs"] = product_docs
    asyncio.run(_run_workflow_standalone(template, pid, storage, context))


@workflow_app.command("approve")
def workflow_approve(
    project_id: str = typer.Option(..., "--project", help="项目 UUID"),
    comment: str = typer.Option("", "--comment", "-c", help="审核意见"),
    workspace: str = typer.Option("default", "--workspace", "-w"),
) -> None:
    """Approve the waiting step and resume workflow execution."""
    from uuid import UUID

    from aigc_workflows import WorkflowError, load_template

    pid = UUID(project_id)
    storage = ProjectStorage(project_id, workspace_id=workspace)
    engine = _make_simple_engine(storage)
    state = engine.load_state()
    if state is None:
        typer.secho("没有待恢复的工作流状态。", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    step_spec = state.steps[state.current_index]
    typer.echo(f'审核步骤 "{step_spec.id}"，状态: {step_spec.status}')
    engine.approve(state, reviewer="cli", comment=comment)

    template_dir = (
        Path(__file__).parent.parent
        / ".."
        / ".."
        / "aigc-workflows"
        / "src"
        / "aigc_workflows"
        / "templates"
    )
    template = load_template(template_dir / f"{state.template_name}.yaml")

    try:
        state = asyncio.run(engine.run(template, pid, {}, auto_approve=False, state=state))
    except WorkflowError as exc:
        typer.secho(f"工作流失败: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    if state.status == "completed":
        typer.secho("✅ 工作流完成", fg=typer.colors.GREEN)
    elif state.status == "paused":
        step = state.steps[state.current_index]
        typer.secho(f'⏸  暂停: 步骤 "{step.id}" 等待审核', fg=typer.colors.YELLOW)
        text = engine.pending_approval_text(state)
        typer.echo(f"\n--- 待审核内容 (前 500 字) ---\n{text[:500]}\n")
        typer.echo("审核通过后执行: aigc workflow approve --project <id>")


@workflow_app.command("status")
def workflow_status(
    project_id: str = typer.Option(..., "--project", help="项目 UUID"),
    workspace: str = typer.Option("default", "--workspace", "-w"),
) -> None:
    """Show current workflow state for a project."""
    storage = ProjectStorage(project_id, workspace_id=workspace)

    engine = _make_simple_engine(storage)
    state = engine.load_state()
    if state is None:
        typer.echo("(无运行中的工作流)")
        return
    typer.echo(f"模板: {state.template_name}")
    typer.echo(f"状态: {state.status}   当前步骤: {state.current_index}/{len(state.steps)}")
    for i, step in enumerate(state.steps):
        marker = "←" if i == state.current_index else " "
        typer.echo(f"  {marker} {step.status:20s}  {step.id}")
    if state.status == "paused":
        pending_engine = _make_simple_engine(storage)
        text = pending_engine.pending_approval_text(state)
        if text:
            typer.echo(f"\n--- 待审核内容 (前 500 字) ---\n{text[:500]}")


def _make_simple_engine(storage: ProjectStorage):  # type: ignore[no-untyped-def]
    from aigc_audio import DummyMusicProvider, DummySfxProvider, DummySubtitleProvider
    from aigc_audio import DummyTtsProvider as AudioDummyTts
    from aigc_generation import DummyImageProvider, DummyVideoProvider
    from aigc_ideation import AnthropicChatClient, LlmConfig
    from aigc_workflows import WorkflowEngine

    from aigc_core.provider import ProviderConfig
    from aigc_core.registry import LlmProviderAdapter, ProviderRegistry

    settings = get_settings()
    registry = ProviderRegistry()
    registry.register("video", DummyVideoProvider(ProviderConfig(name="dummy-video")))
    registry.register("image", DummyImageProvider(ProviderConfig(name="dummy-image")))
    registry.register("tts", AudioDummyTts(ProviderConfig(name="dummy-tts")))
    registry.register("music", DummyMusicProvider(ProviderConfig(name="dummy-music")))
    registry.register("sfx", DummySfxProvider(ProviderConfig(name="dummy-sfx")))
    registry.register("subtitle", DummySubtitleProvider(ProviderConfig(name="dummy-subtitle")))
    if settings.llm_api_key:
        llm_client = AnthropicChatClient(
            LlmConfig(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        )
        registry.register("llm", LlmProviderAdapter("kimi", llm_client))
    else:

        class _FakeLLM:
            async def complete(self, **_: object) -> str:  # noqa: ARG002
                return '{"error":"LLM_API_KEY not configured"}'

        registry.register("llm", LlmProviderAdapter("kimi", _FakeLLM()))
    return WorkflowEngine(registry, storage)


# ── export ──────────────────────────────────────────────────────────────


@export_app.command("show")
def export_show(
    project_id: str = typer.Option(..., "--project", help="项目 UUID"),
    workspace: str = typer.Option("default", "--workspace", "-w"),
) -> None:
    """Show the export package contents for a project."""
    storage = ProjectStorage(project_id, workspace_id=workspace)
    exports_dir = storage.dir("exports")
    if not exports_dir.exists() or not any(exports_dir.iterdir()):
        typer.echo("(无导出内容)")
        return
    for path in sorted(exports_dir.rglob("*"), key=str):
        prefix = "📁" if path.is_dir() else "📄"
        indent = "  " * (len(path.relative_to(exports_dir).parts) - 1)
        typer.echo(f"  {indent}{prefix} {path.name}")


# ── entry ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    app()
