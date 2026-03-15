"""Tests fuer DB-first-Remote-Cache und Delta-Synchronisierung."""

from __future__ import annotations

from pathlib import Path

from db.state_repository import StateRepository
from models.repo_models import RateLimitInfo, RemoteRepo
from services.remote_repo_service import RemoteRepoService
from services.state_db import initialize_state_database


def _build_remote_repo(**overrides) -> RemoteRepo:
    """
    Erzeugt ein Remote-Repository-Testmodell mit ueberschreibbaren Standardwerten.
    """

    payload = {
        "repo_id": 7,
        "name": "demo",
        "full_name": "dbzs/demo",
        "owner": "dbzs",
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "archived": False,
        "fork": False,
        "clone_url": "https://github.com/dbzs/demo.git",
        "ssh_url": "git@github.com:dbzs/demo.git",
        "html_url": "https://github.com/dbzs/demo",
        "description": "Demo Repository",
        "topics": ["tooling", "python"],
        "contributors_count": 2,
        "contributors_summary": "alice, bob",
        "created_at": "2026-03-01T10:00:00Z",
        "updated_at": "2026-03-10T10:00:00Z",
        "pushed_at": "2026-03-11T10:00:00Z",
        "size": 123,
    }
    payload.update(overrides)
    return RemoteRepo(**payload)


class _DummyGitHubService:
    """Kleines GitHub-Testdouble mit vorbereiteten Antwortfolgen."""

    def __init__(self, responses: list[tuple[list[RemoteRepo], RateLimitInfo]]) -> None:
        """
        Speichert eine feste Reihenfolge von Antwortpaaren fuer mehrere Sync-Aufrufe.
        """

        self._responses = list(responses)
        self.last_authenticated_login = "devdbzemusic"

    def fetch_remote_repositories(self) -> tuple[list[RemoteRepo], RateLimitInfo]:
        """
        Liefert die naechste vorbereitete GitHub-Antwort zurueck.
        """

        return self._responses.pop(0)


def _create_service(tmp_path: Path, responses: list[tuple[list[RemoteRepo], RateLimitInfo]]) -> RemoteRepoService:
    """
    Initialisiert einen isolierten RemoteRepoService mit temporaerer State-Datenbank.
    """

    database_file = tmp_path / "igitty_state.db"
    initialize_state_database(database_file)
    return RemoteRepoService(
        github_service=_DummyGitHubService(responses),
        state_repository=StateRepository(database_file),
    )


def test_remote_repo_service_loads_cached_repositories_from_state_db(tmp_path: Path) -> None:
    """
    Prueft, dass der Service nach einem Sync denselben Remote-Zustand DB-first wieder laden kann.
    """

    service = _create_service(
        tmp_path,
        [
            (
                [_build_remote_repo()],
                RateLimitInfo(limit=5000, remaining=4999, reset_at="-"),
            )
        ],
    )

    repositories, _rate_limit = service.sync_repositories()
    cached_repositories = service.load_cached_repositories()

    assert len(repositories) == 1
    assert len(cached_repositories) == 1
    assert cached_repositories[0].full_name == "dbzs/demo"
    assert cached_repositories[0].topics == ["tooling", "python"]
    assert cached_repositories[0].available_actions == ["set_private"]


def test_remote_repo_service_marks_missing_remote_repositories_and_removes_them_from_cache(tmp_path: Path) -> None:
    """
    Prueft, dass verschwundene GitHub-Repositories nach dem Refresh nicht mehr im sichtbaren Cache bleiben.
    """

    service = _create_service(
        tmp_path,
        [
            (
                [_build_remote_repo()],
                RateLimitInfo(limit=5000, remaining=4999, reset_at="-"),
            ),
            (
                [],
                RateLimitInfo(limit=5000, remaining=4998, reset_at="-"),
            ),
        ],
    )

    first_repositories, _rate_limit = service.sync_repositories()
    second_repositories, _rate_limit = service.sync_repositories()

    assert len(first_repositories) == 1
    assert second_repositories == []
    assert service.load_cached_repositories() == []


def test_remote_repo_service_can_cache_multiple_remote_repositories_without_local_path_conflict(tmp_path: Path) -> None:
    """
    Prueft, dass mehrere reine Remote-Repositories trotz leerem lokalem Pfad gemeinsam gespeichert werden koennen.
    """

    service = _create_service(
        tmp_path,
        [
            (
                [
                    _build_remote_repo(repo_id=7, name="demo", full_name="dbzs/demo"),
                    _build_remote_repo(repo_id=8, name="tool", full_name="dbzs/tool"),
                ],
                RateLimitInfo(limit=5000, remaining=4999, reset_at="-"),
            )
        ],
    )

    repositories, _rate_limit = service.sync_repositories()

    assert len(repositories) == 2
    assert {repository.repo_id for repository in repositories} == {7, 8}
