"""Tests fuer die zentrale UI-Aktionsauflosung."""

from __future__ import annotations

from models.repo_models import LocalRepo, RemoteRepo
from models.state_models import RepositoryState
from services.repo_action_resolver import RepoActionResolver


def _build_local_repo(**overrides) -> LocalRepo:
    """
    Erzeugt ein kompaktes lokales Repository-Testmodell mit ueberschreibbaren Standardwerten.
    """

    payload = {
        "name": "demo",
        "full_path": "C:/demo",
        "current_branch": "main",
        "has_remote": True,
        "remote_url": "https://github.com/dbzs/demo.git",
        "has_changes": False,
        "untracked_count": 0,
        "modified_count": 0,
        "last_commit_hash": "abc123",
        "last_commit_date": "2026-03-15T10:00:00+00:00",
        "last_commit_message": "Demo",
        "remote_status": "REMOTE_OK",
        "exists_local": True,
    }
    payload.update(overrides)
    return LocalRepo(**payload)


def test_repo_action_resolver_returns_remote_repair_for_missing_remote() -> None:
    """
    Prueft, dass fuer `REMOTE_MISSING` die Reparatur als Primaeraktion angeboten wird.
    """

    resolver = RepoActionResolver()
    repository = _build_local_repo(remote_status="REMOTE_MISSING")

    actions = resolver.resolve_local_actions(repository)

    assert actions[0].action_id == "repair_remote"
    assert actions[0].recommended is True
    assert resolver.resolve_local_primary_action(repository) == "Remote reparieren"


def test_repo_action_resolver_marks_missing_local_path_as_no_action_case() -> None:
    """
    Prueft, dass ein fehlender lokaler Pfad keine lokalen Kontextaktionen mehr anbietet.
    """

    resolver = RepoActionResolver()
    repository = _build_local_repo(exists_local=False)

    actions = resolver.resolve_local_actions(repository)

    assert actions == []
    assert resolver.resolve_local_primary_action(repository) == "Pfad fehlt"


def test_repo_action_resolver_returns_visibility_toggle_for_remote_repository() -> None:
    """
    Prueft, dass fuer Remote-Repositories die passende Sichtbarkeitsaktion zentral aufgeloest wird.
    """

    resolver = RepoActionResolver()
    repository = RemoteRepo(
        repo_id=7,
        name="demo",
        full_name="dbzs/demo",
        owner="dbzs",
        visibility="private",
        default_branch="main",
        language="Python",
        archived=False,
        fork=False,
        clone_url="https://github.com/dbzs/demo.git",
        ssh_url="git@github.com:dbzs/demo.git",
        html_url="https://github.com/dbzs/demo",
        description="Demo",
    )

    actions = resolver.resolve_remote_actions(repository)

    assert actions[0].action_id == "set_public"
    assert actions[0].recommended is True


def test_repo_action_resolver_derives_state_actions_for_dirty_ahead_repository() -> None:
    """
    Prueft, dass der PHASE-II-Resolver aus dem RepositoryState Commit und Push ableitet.
    """

    resolver = RepoActionResolver()
    repository = RepositoryState(
        name="demo",
        source_type="local",
        local_path="C:/demo",
        is_git_repo=True,
        exists_local=True,
        has_remote=True,
        remote_configured=True,
        git_initialized=True,
        has_uncommitted_changes=True,
        ahead_count=2,
        behind_count=0,
        sync_state="AHEAD",
        health_state="healthy",
        status="REMOTE_OK",
    )

    actions = resolver.resolve_repo_actions(repository)

    assert {action.action_id for action in actions} >= {"commit", "push"}
    assert resolver.resolve_repo_primary_action(repository) in {"Commit", "Push"}
