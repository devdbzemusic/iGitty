"""Tests fuer die zentrale Sync-Zustandsanalyse."""

from __future__ import annotations

from pathlib import Path

from models.state_models import RepositoryState
from services.git_service import GitService
from services.repo_action_resolver import RepoActionResolver
from services.repository_sync_analyzer import RepositorySyncAnalyzer


class _StubGitService(GitService):
    """Kleines Testdouble fuer deterministische Git-Sync-Beziehungen."""

    def __init__(
        self,
        *,
        local_head: str = "local-head",
        remote_head: str = "remote-head",
        merge_base: str = "base-head",
        ahead_count: int = 0,
        behind_count: int = 0,
        is_diverged: bool = False,
        status_lines: list[str] | None = None,
    ) -> None:
        """
        Speichert vorbereitete Rueckgabewerte fuer alle benoetigten Git-Leseoperationen.
        """

        super().__init__(logger=None)
        self._local_head = local_head
        self._remote_head = remote_head
        self._merge_base = merge_base
        self._ahead_count = ahead_count
        self._behind_count = behind_count
        self._is_diverged = is_diverged
        self._status_lines = status_lines or []

    def fetch_remote_updates(self, repo_path: Path, remote_name: str = "origin") -> bool:
        """Simuliert einen erfolgreichen lesenden Fetch fuer die Analyse."""

        return True

    def get_head_commit_hash(self, repo_path: Path) -> str:
        """Liefert den vorbereiteten lokalen HEAD-Commit."""

        return self._local_head

    def get_ref_commit_hash(self, repo_path: Path, ref_name: str) -> str:
        """Liefert den vorbereiteten Remote-HEAD-Commit."""

        return self._remote_head

    def get_merge_base_commit(self, repo_path: Path, left_ref: str, right_ref: str) -> str:
        """Liefert die vorbereitete Merge-Base."""

        return self._merge_base

    def get_ahead_behind_counts(
        self,
        repo_path: Path,
        branch_name: str,
        remote_name: str = "origin",
    ) -> tuple[int, int, bool]:
        """Liefert vorbereitete Ahead-/Behind-Werte fuer die Analyse."""

        return self._ahead_count, self._behind_count, self._is_diverged

    def get_status_porcelain(self, repo_path: Path) -> list[str]:
        """Liefert vorbereitete Statuszeilen fuer ungecommittete Aenderungen."""

        return list(self._status_lines)


def _build_repository_state(**overrides) -> RepositoryState:
    """
    Erzeugt einen kompakten RepositoryState fuer Sync-Analyzer-Tests.
    """

    payload = {
        "repo_key": "local::demo",
        "name": "demo",
        "source_type": "local",
        "local_path": "C:/repos/demo",
        "remote_url": "https://github.com/dbzs/demo.git",
        "github_repo_id": 10,
        "default_branch": "main",
        "current_branch": "main",
        "is_git_repo": True,
        "git_initialized": True,
        "has_remote": True,
        "remote_name": "origin",
        "remote_owner": "dbzs",
        "remote_repo_name": "demo",
        "exists_local": True,
        "exists_remote": True,
        "remote_configured": True,
        "health_state": "healthy",
        "sync_state": "IN_SYNC",
        "status": "IN_SYNC",
        "visibility": "public",
    }
    payload.update(overrides)
    return RepositoryState(**payload)


def test_repository_sync_analyzer_detects_in_sync_pair() -> None:
    """
    Prueft, dass identische lokale und entfernte HEADs als `IN_SYNC` erkannt werden.
    """

    analyzer = RepositorySyncAnalyzer(
        git_service=_StubGitService(local_head="same", remote_head="same", merge_base="same"),
        repo_action_resolver=RepoActionResolver(),
    )
    local_repository = _build_repository_state()
    remote_repository = _build_repository_state(source_type="remote", repo_key="remote::10", local_path="", exists_local=False)

    analysis = analyzer.analyze_repository_pair(local_repository, remote_repository)

    assert analysis.sync_state == "IN_SYNC"
    assert analysis.health_state == "healthy"


def test_repository_sync_analyzer_detects_local_ahead_pair() -> None:
    """
    Prueft, dass eine vorauslaufende lokale Historie als `LOCAL_AHEAD` erkannt wird.
    """

    analyzer = RepositorySyncAnalyzer(
        git_service=_StubGitService(
            local_head="local-head",
            remote_head="remote-head",
            merge_base="remote-head",
            ahead_count=2,
            behind_count=0,
        ),
        repo_action_resolver=RepoActionResolver(),
    )

    analysis = analyzer.analyze_repository_pair(_build_repository_state(), _build_repository_state(source_type="remote", repo_key="remote::10", local_path="", exists_local=False))

    assert analysis.sync_state == "LOCAL_AHEAD"
    assert analysis.local_repository is not None
    assert analysis.local_repository.ahead_count == 2


def test_repository_sync_analyzer_detects_remote_ahead_pair() -> None:
    """
    Prueft, dass eine vorauslaufende Remote-Historie als `REMOTE_AHEAD` erkannt wird.
    """

    analyzer = RepositorySyncAnalyzer(
        git_service=_StubGitService(
            local_head="local-head",
            remote_head="remote-head",
            merge_base="local-head",
            ahead_count=0,
            behind_count=3,
        ),
        repo_action_resolver=RepoActionResolver(),
    )

    analysis = analyzer.analyze_repository_pair(_build_repository_state(), _build_repository_state(source_type="remote", repo_key="remote::10", local_path="", exists_local=False))

    assert analysis.sync_state == "REMOTE_AHEAD"


def test_repository_sync_analyzer_detects_diverged_pair() -> None:
    """
    Prueft, dass divergierte Historien als kritischer Zustand erkannt werden.
    """

    analyzer = RepositorySyncAnalyzer(
        git_service=_StubGitService(
            local_head="local-head",
            remote_head="remote-head",
            merge_base="older-base",
            ahead_count=2,
            behind_count=4,
            is_diverged=True,
        ),
        repo_action_resolver=RepoActionResolver(),
    )

    analysis = analyzer.analyze_repository_pair(_build_repository_state(), _build_repository_state(source_type="remote", repo_key="remote::10", local_path="", exists_local=False))

    assert analysis.sync_state == "DIVERGED"
    assert analysis.health_state == "critical"


def test_repository_sync_analyzer_handles_local_only_repository() -> None:
    """
    Prueft, dass ein lokales Repository ohne bestaetigtes Remote-Paar als `LOCAL_ONLY` markiert wird.
    """

    analyzer = RepositorySyncAnalyzer(
        git_service=_StubGitService(),
        repo_action_resolver=RepoActionResolver(),
    )
    local_repository = _build_repository_state(has_remote=False, remote_configured=False, remote_url="", remote_owner="", remote_repo_name="")

    analysis = analyzer.analyze_repository_pair(local_repository, None)

    assert analysis.sync_state == "LOCAL_ONLY"


def test_repository_sync_analyzer_handles_remote_only_repository() -> None:
    """
    Prueft, dass ein reines Remote-Repository als `REMOTE_ONLY` markiert wird.
    """

    analyzer = RepositorySyncAnalyzer(
        git_service=_StubGitService(),
        repo_action_resolver=RepoActionResolver(),
    )
    remote_repository = _build_repository_state(
        source_type="remote",
        repo_key="remote::10",
        local_path="",
        exists_local=False,
    )

    analysis = analyzer.analyze_repository_pair(None, remote_repository)

    assert analysis.sync_state == "REMOTE_ONLY"


def test_repository_sync_analyzer_detects_missing_remote() -> None:
    """
    Prueft, dass ein nicht mehr vorhandenes Remote als `REMOTE_MISSING` erkannt wird.
    """

    analyzer = RepositorySyncAnalyzer(
        git_service=_StubGitService(),
        repo_action_resolver=RepoActionResolver(),
    )
    local_repository = _build_repository_state(remote_exists_online=0, exists_remote=False)
    remote_repository = _build_repository_state(
        source_type="remote",
        repo_key="remote::10",
        local_path="",
        exists_local=False,
        is_missing=True,
    )

    analysis = analyzer.analyze_repository_pair(local_repository, remote_repository)

    assert analysis.sync_state == "REMOTE_MISSING"


def test_repository_sync_analyzer_prioritizes_uncommitted_changes() -> None:
    """
    Prueft, dass ungecommittete lokale Aenderungen vor Ahead-/Behind-Stati gemeldet werden.
    """

    analyzer = RepositorySyncAnalyzer(
        git_service=_StubGitService(
            local_head="local-head",
            remote_head="remote-head",
            merge_base="remote-head",
            ahead_count=1,
            behind_count=0,
            status_lines=[" M app.py"],
        ),
        repo_action_resolver=RepoActionResolver(),
    )

    analysis = analyzer.analyze_repository_pair(_build_repository_state(), _build_repository_state(source_type="remote", repo_key="remote::10", local_path="", exists_local=False))

    assert analysis.sync_state == "UNCOMMITTED_LOCAL_CHANGES"
