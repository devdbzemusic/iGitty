"""Tests fuer den neuen persistenten State-Layer von iGitty."""

from __future__ import annotations

from pathlib import Path

from core.paths import RuntimePaths
from db.init_db import initialize_databases
from db.sqlite_manager import sqlite_connection
from db.state_repository import StateRepository
from models.repo_models import LocalRepo
from models.state_models import RepositoryState
from services.push_service import PushService
from services.remote_validation_service import RemoteValidationService
from services.repo_index_service import RepoIndexService
from services.repo_structure_service import RepoStructureService


class DummyInspectorService:
    """Liefert deterministische Git-Inspektionsdaten fuer den Repo-Index-Test."""

    def inspect_repository(self, repo_path: Path) -> dict[str, object]:
        """
        Gibt feste Metadaten fuer ein gefundenes Test-Repository zurueck.
        """

        return {
            "name": repo_path.name,
            "local_path": str(repo_path),
            "is_git_repo": True,
            "branch": "main",
            "head_commit": "abc123",
            "head_commit_date": "2026-03-12T10:00:00+00:00",
            "has_remote": True,
            "remote_name": "origin",
            "remote_url": "https://github.com/dbzs/demo.git",
            "remote_host": "github.com",
            "remote_owner": "dbzs",
            "remote_repo_name": "demo",
            "has_uncommitted_changes": False,
        }


class DummyRemoteValidationService:
    """Setzt einen erfolgreichen Online-Status ohne echte HTTP-Aufrufe."""

    def __init__(self, state_repository: StateRepository) -> None:
        """
        Speichert das Ziel-Repository fuer das realistische Persistenzverhalten des Stubs.
        """

        self._state_repository = state_repository

    def validate_repository(self, repository: RepositoryState) -> RepositoryState:
        """
        Markiert das Test-Repository als online vorhanden.
        """

        repository.remote_exists_online = 1
        repository.remote_visibility = "public"
        repository.status = "REMOTE_OK"
        return self._state_repository.upsert_repository(repository)


class DummyRepoStructureService:
    """Simuliert eine erfolgreiche Dateiindexierung."""

    def __init__(self) -> None:
        """
        Initialisiert einen einfachen Aufrufzaehler fuer Assertions.
        """

        self.calls = 0

    def index_repository_files(self, repo_id: int, repo_path: Path) -> int:
        """
        Liefert eine feste Dateianzahl fuer Assertions.
        """

        self.calls += 1
        return 2


class DummyValidationGitHubService:
    """Simuliert GitHub-Metadaten fuer die Remote-Validierung."""

    def __init__(self, status_code: int) -> None:
        """
        Speichert den gewuenschten HTTP-Status fuer spaetere Antworten.
        """

        self._status_code = status_code

    def parse_github_remote(self, remote_url: str) -> tuple[str, str] | None:
        """
        Zerlegt im Test jede GitHub-URL in Owner und Repository-Name.
        """

        return "dbzs", "demo"

    def fetch_repository_metadata(self, owner: str, name: str) -> tuple[int, dict]:
        """
        Liefert den konfigurierten Statuscode mit minimaler Payload.
        """

        if self._status_code == 200:
            return 200, {"id": 99, "visibility": "private"}
        return self._status_code, {}


class DummyPushGitService:
    """Merkt sich, ob ein Push versehentlich trotz fehlendem Remote versucht wurde."""

    def __init__(self) -> None:
        """
        Initialisiert die Aufrufprotokolle fuer Assertions.
        """

        self.pushes: list[tuple[str, str]] = []

    def ensure_git_available(self) -> None:
        """
        Simuliert eine vorhandene Git-Installation.
        """

    def push_current_branch(self, repo_path: Path, branch_name: str) -> None:
        """
        Protokolliert Push-Aufrufe fuer spaetere Assertions.
        """

        self.pushes.append((str(repo_path), branch_name))

    def set_remote_origin(self, repo_path: Path, remote_url: str) -> None:
        """
        Wird im Test nicht benoetigt.
        """


class DummyPushGitHubService:
    """Leeres Test-Double fuer den Push-Service."""

    def create_repository(self, name: str, private: bool, description: str):
        """
        Wird im Test fuer `REMOTE_MISSING` bewusst nicht aufgerufen.
        """

        raise AssertionError("GitHub-Repository darf in diesem Test nicht erzeugt werden.")


class DummyStructureGitService:
    """Liefert feste Tracking- und Ignore-Daten fuer den Dateiindex-Test."""

    def list_tracked_files(self, repo_path: Path) -> list[str]:
        """
        Markiert eine Datei als tracked.
        """

        return ["src/app.py"]

    def list_ignored_paths(self, repo_path: Path) -> list[str]:
        """
        Meldet keine zusaetzlichen ignorierten Dateien fuer den Test.
        """

        return []


def _build_runtime_paths(tmp_path: Path) -> RuntimePaths:
    """
    Erstellt konsistente Laufzeitpfade fuer isolierte Datenbanktests.
    """

    paths = RuntimePaths(
        project_root=tmp_path,
        assets_dir=tmp_path / "assets",
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        jobs_db_file=tmp_path / "data" / "igitty_jobs.db",
        repo_struct_db_file=tmp_path / "data" / "repo_struct_vault.db",
        state_db_file=tmp_path / "data" / "igitty_state.db",
        log_file=tmp_path / "logs" / "log.txt",
        stylesheet_file=tmp_path / "assets" / "styles" / "neon_dark.qss",
    )
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    initialize_databases(paths)
    return paths


def test_repo_index_service_persists_repository_and_events(tmp_path: Path) -> None:
    """
    Prueft, dass ein lokaler Scan einen Repository-Zustand samt Events persistiert.
    """

    repo_root = tmp_path / "repos" / "demo"
    (repo_root / ".git").mkdir(parents=True)
    paths = _build_runtime_paths(tmp_path)
    repository = StateRepository(paths.state_db_file)
    service = RepoIndexService(
        state_repository=repository,
        git_inspector_service=DummyInspectorService(),
        remote_validation_service=DummyRemoteValidationService(repository),
        repo_structure_service=DummyRepoStructureService(),
    )

    results = service.scan_root(tmp_path / "repos")

    assert len(results) == 1
    persisted = repository.fetch_repository_by_local_path(str(repo_root))
    assert persisted is not None
    assert persisted.status == "REMOTE_OK"
    latest_event = repository.fetch_latest_event(int(persisted.id or 0), "FILE_INDEX_COMPLETED")
    assert latest_event is not None
    assert latest_event.message == "2 Dateien indexiert."


def test_remote_validation_service_marks_missing_remote(tmp_path: Path) -> None:
    """
    Prueft, dass eine 404-Antwort eines GitHub-Remotes als `REMOTE_MISSING` gespeichert wird.
    """

    paths = _build_runtime_paths(tmp_path)
    repository = StateRepository(paths.state_db_file)
    state = repository.upsert_repository(
        RepositoryState(
            name="demo",
            local_path="C:/demo",
            is_git_repo=True,
            current_branch="main",
            head_commit="abc123",
            head_commit_date="2026-03-12T10:00:00+00:00",
            has_remote=True,
            remote_name="origin",
            remote_url="https://github.com/dbzs/demo.git",
            remote_host="github.com",
            remote_owner="dbzs",
            remote_repo_name="demo",
            remote_exists_online=None,
            remote_visibility="unknown",
            status="REMOTE_UNREACHABLE",
            last_local_scan_at="2026-03-12T10:00:00+00:00",
            last_remote_check_at="",
        )
    )
    service = RemoteValidationService(DummyValidationGitHubService(status_code=404), repository)

    updated = service.validate_repository(state)

    assert updated.remote_exists_online == 0
    assert updated.status == "REMOTE_MISSING"


def test_repo_structure_service_indexes_files(tmp_path: Path) -> None:
    """
    Prueft, dass der Dateiscanner relevante Repository-Dateien in `repo_files` persistiert.
    """

    repo_root = tmp_path / "demo"
    (repo_root / "src").mkdir(parents=True)
    (repo_root / ".git").mkdir()
    (repo_root / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (repo_root / "__pycache__").mkdir()
    (repo_root / "__pycache__" / "skip.pyc").write_bytes(b"x")

    paths = _build_runtime_paths(tmp_path)
    repository = StateRepository(paths.state_db_file)
    state = repository.upsert_repository(
        RepositoryState(
            name="demo",
            local_path=str(repo_root),
            is_git_repo=True,
            current_branch="main",
            head_commit="abc123",
            head_commit_date="2026-03-12T10:00:00+00:00",
            has_remote=False,
            remote_name="",
            remote_url="",
            remote_host="",
            remote_owner="",
            remote_repo_name="",
            remote_exists_online=None,
            remote_visibility="not_published",
            status="LOCAL_ONLY",
            last_local_scan_at="2026-03-12T10:00:00+00:00",
            last_remote_check_at="",
        )
    )
    service = RepoStructureService(repository, DummyStructureGitService())

    indexed_count = service.index_repository_files(int(state.id or 0), repo_root)

    assert indexed_count == 1
    with sqlite_connection(paths.state_db_file) as connection:
        row = connection.execute(
            "SELECT relative_path, is_tracked FROM repo_files WHERE repo_id = ?",
            (int(state.id or 0),),
        ).fetchone()
    assert row is not None
    assert row["relative_path"] == "src/app.py"
    assert row["is_tracked"] == 1


def test_push_service_blocks_missing_remote_using_state_database(tmp_path: Path) -> None:
    """
    Prueft, dass ein als `REMOTE_MISSING` markiertes Repository nicht blind gepusht wird.
    """

    paths = _build_runtime_paths(tmp_path)
    repository = StateRepository(paths.state_db_file)
    repository.upsert_repository(
        RepositoryState(
            name="demo",
            local_path="C:/demo",
            is_git_repo=True,
            current_branch="main",
            head_commit="abc123",
            head_commit_date="2026-03-12T10:00:00+00:00",
            has_remote=True,
            remote_name="origin",
            remote_url="https://github.com/dbzs/demo.git",
            remote_host="github.com",
            remote_owner="dbzs",
            remote_repo_name="demo",
            remote_exists_online=0,
            remote_visibility="unknown",
            status="REMOTE_MISSING",
            last_local_scan_at="2026-03-12T10:00:00+00:00",
            last_remote_check_at="2026-03-12T10:01:00+00:00",
        )
    )
    git_service = DummyPushGitService()
    service = PushService(git_service=git_service, github_service=DummyPushGitHubService(), state_repository=repository)

    results = service.push_repositories(
        repositories=[
            LocalRepo(
                name="demo",
                full_path="C:/demo",
                current_branch="main",
                has_remote=True,
                remote_url="https://github.com/dbzs/demo.git",
                has_changes=False,
                untracked_count=0,
                modified_count=0,
                last_commit_hash="-",
                last_commit_date="-",
                last_commit_message="-",
                remote_status="REMOTE_MISSING",
            )
        ],
        create_remote=False,
        remote_private=True,
        description="",
        job_id="job-remote-missing",
    )

    assert results[0].status == "error"
    assert "Remote existiert online nicht mehr" in results[0].message
    assert git_service.pushes == []


def test_repo_index_service_skips_file_index_for_broken_git_repositories(tmp_path: Path) -> None:
    """
    Prueft, dass defekte Repositories nicht zusaetzlich in die Dateiindexierung laufen.
    """

    class BrokenInspectorService:
        """
        Liefert einen Zustand, der kein gueltiges Git-Repository mehr darstellt.
        """

        def inspect_repository(self, repo_path: Path) -> dict[str, object]:
            return {
                "name": repo_path.name,
                "local_path": str(repo_path),
                "is_git_repo": False,
                "branch": "",
                "head_commit": "",
                "head_commit_date": "",
                "has_remote": False,
                "remote_name": "",
                "remote_url": "",
                "remote_host": "",
                "remote_owner": "",
                "remote_repo_name": "",
                "has_uncommitted_changes": False,
            }

    repo_root = tmp_path / "repos" / "broken_demo"
    (repo_root / ".git").mkdir(parents=True)
    paths = _build_runtime_paths(tmp_path)
    repository = StateRepository(paths.state_db_file)
    repo_structure_service = DummyRepoStructureService()
    service = RepoIndexService(
        state_repository=repository,
        git_inspector_service=BrokenInspectorService(),
        repo_structure_service=repo_structure_service,
    )

    results = service.scan_root(tmp_path / "repos")

    assert len(results) == 1
    assert results[0].status == "BROKEN_GIT"
    assert repo_structure_service.calls == 0
