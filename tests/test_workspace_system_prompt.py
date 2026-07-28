"""Regression test: a workspace's system.md must reach the model.

WorkspaceManager has always read system.md and passed `system_prompt`
into WorkspaceConfig, but the field was not declared on the model, so
pydantic dropped it silently. Chat then raised AttributeError whenever
the operator left the System prompt box empty, and the personas in
system.md never took effect. Both failures are covered here.
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.models import WorkspaceConfig
from app.workspaces.manager import WorkspaceManager


class _Paths:
    """Minimal stand-in for Paths — only `workspaces` is consulted here."""

    def __init__(self, root: Path):
        self.workspaces = root


def _make_workspace(root: Path, slug: str, system_text: str | None) -> None:
    ws = root / slug
    ws.mkdir(parents=True)
    (ws / "workspace.yaml").write_text(
        yaml.safe_dump(
            {"name": slug.title(), "slug": slug, "description": "test workspace"}
        )
    )
    if system_text is not None:
        (ws / "system.md").write_text(system_text)


def test_system_prompt_is_loaded_from_system_md(tmp_path):
    _make_workspace(tmp_path, "mactech", "You are Jarvis in the MacTech workspace.")
    manager = WorkspaceManager(_Paths(tmp_path))

    workspace = manager.get_workspace("mactech")

    assert workspace is not None
    assert workspace.system_prompt == "You are Jarvis in the MacTech workspace."


def test_missing_system_md_yields_empty_string_not_an_error(tmp_path):
    # The chat path reads workspace.system_prompt unconditionally, so the
    # attribute must exist even when the file does not.
    _make_workspace(tmp_path, "bare", None)
    manager = WorkspaceManager(_Paths(tmp_path))

    workspace = manager.get_workspace("bare")

    assert workspace is not None
    assert workspace.system_prompt == ""


def test_config_declares_the_field_so_it_survives_construction():
    # Guards the actual defect: an undeclared field is dropped silently
    # by pydantic rather than raising at construction time.
    config = WorkspaceConfig(
        name="Test",
        slug="test",
        description="d",
        system_prompt="persona text",
    )
    assert config.system_prompt == "persona text"
