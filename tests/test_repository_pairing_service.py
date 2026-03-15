"""Tests fuer die Pairing-Logik zwischen lokalen und entfernten Repositories."""

from __future__ import annotations

from pathlib import Path

from db.state_repository import StateRepository
from models.state_models import RepoLink, RepositoryState
from services.repository_pairing_service import RepositoryPairingService
from services.state_db import initialize_state_database


def _create_repository_state(**overrides) -> RepositoryState:
    """
    Erzeugt einen kompakten RepositoryState fuer Pairing-Tests mit ueberschreibbaren Defaults.
    """

    payload = {
        "name": "demo",
        "source_type": "local",
        "local_path": "C:/repos/demo",
        "remote_url": "https://github.com/dbzs/demo.git",
        "github_repo_id": 0,
        "default_branch": "main",
        "visibility": "public",
        "is_git_repo": True,
        "current_branch": "main",
        "head_commit": "abc123",
        "has_remote": True,
        "remote_name": "origin",
        "remote_host": "github.com",
        "remote_owner": "dbzs",
        "remote_repo_name": "demo",
        "exists_local": True,
        "exists_remote": True,
        "git_initialized": True,
        "remote_configured": True,
        "sync_state": "IN_SYNC",
        "health_state": "healthy",
        "status": "IN_SYNC",
        "recommended_action": "Oeffnen",
    }
    payload.update(overrides)
    return RepositoryState(**payload)


def _create_service(tmp_path: Path) -> tuple[StateRepository, RepositoryPairingService]:
    """
    Baut fuer die Tests eine isolierte State-Datenbank samt Pairing-Service auf.
    """

    database_file = tmp_path / "igitty_state.db"
    initialize_state_database(database_file)
    repository = StateRepository(database_file)
    return repository, RepositoryPairingService(repository)


def test_repository_pairing_service_prefers_exact_url_matches(tmp_path: Path) -> None:
    """
    Prueft, dass identische GitHub-URLs als aktiver exakter Pairing-Link gespeichert werden.
    """

    state_repository, pairing_service = _create_service(tmp_path)
    local_repository = state_repository.upsert_repository(_create_repository_state())
    remote_repository = state_repository.upsert_repository(
        _create_repository_state(
            source_type="remote",
            repo_key="remote::99",
            local_path="",
            github_repo_id=99,
            remote_url="git@github.com:dbzs/demo.git",
            has_remote=False,
            exists_local=False,
            remote_owner="dbzs",
            remote_repo_name="demo",
        )
    )

    links = pairing_service.resolve_links([local_repository], [remote_repository])

    assert len(links) == 1
    assert links[0].link_type == "exact"
    assert links[0].link_confidence == 100
    assert links[0].is_active is True


def test_repository_pairing_service_uses_github_id_match_when_available(tmp_path: Path) -> None:
    """
    Prueft, dass eine bekannte GitHub-Repository-ID als sicherer Match verwendet wird.
    """

    state_repository, pairing_service = _create_service(tmp_path)
    local_repository = state_repository.upsert_repository(
        _create_repository_state(
            github_repo_id=77,
            remote_url="",
            has_remote=False,
            remote_configured=False,
            remote_owner="",
            remote_repo_name="",
        )
    )
    remote_repository = state_repository.upsert_repository(
        _create_repository_state(
            source_type="remote",
            repo_key="remote::77",
            local_path="",
            github_repo_id=77,
            remote_url="https://github.com/dbzs/demo.git",
            has_remote=False,
            exists_local=False,
        )
    )

    links = pairing_service.resolve_links([local_repository], [remote_repository])

    assert len(links) == 1
    assert links[0].link_type == "github_id_match"
    assert links[0].link_confidence == 100


def test_repository_pairing_service_marks_name_matches_as_inactive_hints(tmp_path: Path) -> None:
    """
    Prueft, dass reine Namensmatches nicht stillschweigend als sichere aktive Pairings gelten.
    """

    state_repository, pairing_service = _create_service(tmp_path)
    local_repository = state_repository.upsert_repository(
        _create_repository_state(
            remote_url="",
            has_remote=False,
            remote_configured=False,
            remote_owner="",
            remote_repo_name="",
        )
    )
    remote_repository = state_repository.upsert_repository(
        _create_repository_state(
            source_type="remote",
            repo_key="remote::55",
            local_path="",
            github_repo_id=55,
            remote_url="https://github.com/anderer/demo.git",
            has_remote=False,
            exists_local=False,
            remote_owner="anderer",
            remote_repo_name="demo",
        )
    )

    links = pairing_service.resolve_links([local_repository], [remote_repository])

    assert len(links) == 1
    assert links[0].link_type == "name_match"
    assert links[0].link_confidence == 60
    assert links[0].is_active is False


def test_repository_pairing_service_keeps_manual_links_active(tmp_path: Path) -> None:
    """
    Prueft, dass eine manuelle Verknuepfung bei spaeteren Pairing-Laeufen wiederverwendet wird.
    """

    state_repository, pairing_service = _create_service(tmp_path)
    local_repository = state_repository.upsert_repository(_create_repository_state())
    remote_repository = state_repository.upsert_repository(
        _create_repository_state(
            source_type="remote",
            repo_key="remote::101",
            local_path="",
            github_repo_id=101,
            remote_url="https://github.com/dbzs/demo.git",
            has_remote=False,
            exists_local=False,
        )
    )
    state_repository.upsert_repo_link(
        RepoLink(
            state_repo_id=int(local_repository.id or 0),
            github_repo_id=101,
            local_path=local_repository.local_path,
            remote_url=remote_repository.remote_url,
            remote_owner="dbzs",
            remote_name="demo",
            link_type="manual",
            link_confidence=100,
            is_active=True,
            last_verified_at="2026-03-15T12:00:00+00:00",
        )
    )

    links = pairing_service.resolve_links([local_repository], [remote_repository])

    assert len(links) == 1
    assert links[0].link_type == "manual"
    assert links[0].is_active is True
