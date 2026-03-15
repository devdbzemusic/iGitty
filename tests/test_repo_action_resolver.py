"""Tests fuer die zentrale UI-Aktionsauflosung."""

from __future__ import annotations

from models.repo_models import LocalRepo
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
