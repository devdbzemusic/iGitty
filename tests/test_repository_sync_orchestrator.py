"""Tests fuer den zentralen RepositorySyncOrchestrator."""

from __future__ import annotations

from pathlib import Path

from models.repo_models import RateLimitInfo, RemoteRepo
from models.state_models import RepositoryState
from services.repository_sync_orchestrator import RepositorySyncOrchestrator


class DummyRepoIndexService:
    """Kleines Test-Double fuer lokale Delta-Scans."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, bool]] = []

    def scan_root(self, root_path: Path, hard_refresh: bool = False) -> list[RepositoryState]:
        """
        Merkt sich Aufrufe und liefert einen minimalen lokalen RepositoryState.
        """

        self.calls.append((root_path, hard_refresh))
        return [RepositoryState(name="demo", local_path=str(root_path / "demo"), source_type="local")]


class DummyRemoteRepoService:
    """Kleines Test-Double fuer den GitHub-Refresh."""

    def sync_repositories(self):
        """
        Liefert eine feste Remote-Liste und ein simples Rate-Limit.
        """

        return (
            [
                RemoteRepo(
                    repo_id=1,
                    name="demo",
                    full_name="dbzs/demo",
                    owner="dbzs",
                    visibility="public",
                    default_branch="main",
                    language="Python",
                    archived=False,
                    fork=False,
                    clone_url="https://github.com/dbzs/demo.git",
                    ssh_url="git@github.com:dbzs/demo.git",
                    html_url="https://github.com/dbzs/demo",
                    description="Demo",
                )
            ],
            RateLimitInfo(limit=60, remaining=59, reset_at="-"),
        )


def test_repository_sync_orchestrator_combines_local_and_remote_refreshes(tmp_path: Path) -> None:
    """
    Prueft, dass der Orchestrator beide Seiten in einem gemeinsamen Snapshot zusammenfuehrt.
    """

    repo_index_service = DummyRepoIndexService()
    remote_repo_service = DummyRemoteRepoService()
    orchestrator = RepositorySyncOrchestrator(repo_index_service, remote_repo_service)

    snapshot = orchestrator.refresh_all(tmp_path, hard_refresh=True)

    assert repo_index_service.calls == [(tmp_path, True)]
    assert len(snapshot.local_repositories) == 1
    assert len(snapshot.remote_repositories) == 1
    assert snapshot.rate_limit.remaining == 59
    assert snapshot.hard_refresh is True
