"""Storage layout convention for project files.

Layout (ADR 006):
    projects/{workspace_id}/{project_id}/{source,generated,approved,exports,archive,state}/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from aigc_core.config import get_settings
from aigc_core.models import Project
from aigc_core.os_models import KnowledgeBase

KINDS = ("source", "generated", "approved", "exports", "archive", "state")


class ProjectStorage:
    """Resolves and creates the standard directory layout for a project."""

    def __init__(
        self,
        project_id: UUID | str,
        workspace_id: UUID | str | None = None,
        base_dir: Path | None = None,
    ) -> None:
        root = base_dir or get_settings().projects_dir
        ws = str(workspace_id) if workspace_id else "default"
        self.root = Path(root) / ws / str(project_id)

    def dir(self, kind: str) -> Path:
        if kind not in KINDS:
            raise ValueError(f"unknown storage kind {kind!r}; expected one of {KINDS}")
        path = self.root / kind
        path.mkdir(parents=True, exist_ok=True)
        return path

    def new_file(self, kind: str, extension: str, name: str | None = None) -> Path:
        """Return a fresh unique file path inside the given storage kind."""
        filename = f"{name or uuid4().hex}{extension}"
        return self.dir(kind) / filename

    def state_file(self, name: str) -> Path:
        """Return a JSON state file path (tasks, generations, costs)."""
        return self.dir("state") / f"{name}.json"

    def save_project(self, project: Project) -> Path:
        """Persist a project document to source/project.json."""
        path = self.dir("source") / "project.json"
        path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_project(self) -> Project:
        """Load the project document from source/project.json."""
        path = self.dir("source") / "project.json"
        if not path.exists():
            raise FileNotFoundError(f"project not found at {path}")
        return Project.model_validate_json(path.read_text(encoding="utf-8"))

    def save_knowledge_base(self, kb: KnowledgeBase) -> Path:
        path = self.dir("source") / "knowledge.json"
        items: list[dict[str, Any]] = []
        if path.exists():
            items = json.loads(path.read_text(encoding="utf-8"))
        items.append(kb.model_dump(mode="json"))
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2, default=str))
        return path

    def list_kb(self) -> list[dict[str, Any]]:
        path = self.dir("source") / "knowledge.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
