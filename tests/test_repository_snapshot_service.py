"""Tests fuer RepositorySnapshotService und Snapshot-Diffs."""

from __future__ import annotations

from pathlib import Path

from core.paths import RuntimePaths
from db.init_db import initialize_databases
from db.job_log_repository import JobLogRepository
from db.repo_struct_repository import RepoStructRepository
from db.state_repository import StateRepository
from models.evolution_models import RepositorySnapshot, RepositorySnapshotFile
from models.state_models import RepoFileState, RepositoryState
from models.struct_models import RepoTreeItem
from services.repo_struct_service import RepoStructService
from services.repository_snapshot_service import RepositorySnapshotService


def _build_runtime_paths(tmp_path: Path) -> RuntimePaths:
    """
    Erstellt isolierte Laufzeitpfade fuer Snapshot-Tests.
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


def test_repository_snapshot_service_skips_redundant_scan_snapshots(tmp_path: Path) -> None:
    """
    Prueft, dass bei identischem Fingerprint kein redundanter Scan-Snapshot erzeugt wird.
    """

    paths = _build_runtime_paths(tmp_path)
    state_repository = StateRepository(paths.state_db_file)
    job_log_repository = JobLogRepository(paths.jobs_db_file)
    struct_repository = RepoStructRepository(paths.repo_struct_db_file)
    struct_service = RepoStructService(struct_repository)
    snapshot_service = RepositorySnapshotService(
        state_repository=state_repository,
        job_log_repository=job_log_repository,
        repo_struct_repository=struct_repository,
        repo_struct_service=struct_service,
    )
    repository = state_repository.upsert_repository(
        RepositoryState(
            repo_key="local::c:/demo",
            name="demo",
            source_type="local",
            local_path="C:/demo",
            is_git_repo=True,
            current_branch="main",
            head_commit="abc123",
            has_remote=True,
            remote_url="https://github.com/dbzs/demo.git",
            remote_owner="dbzs",
            remote_repo_name="demo",
            exists_local=True,
            remote_configured=True,
            git_initialized=True,
            status="REMOTE_OK",
            scan_fingerprint="fp-1",
            status_hash="status-1",
        )
    )
    state_repository.update_repo_files_delta(
        int(repository.id or 0),
        [
            RepoFileState(
                repo_id=int(repository.id or 0),
                relative_path="src/app.py",
                path_type="file",
                content_hash="hash-app",
                last_seen_at="2026-03-15T10:00:00+00:00",
                last_seen_scan_at="2026-03-15T10:00:00+00:00",
            )
        ],
    )
    struct_repository.replace_repo_items(
        repo_identifier=struct_service.build_repo_identifier(local_path="C:/demo"),
        source_type="local",
        root_path="C:/demo",
        items=[
            RepoTreeItem(
                repo_identifier="local::c:/demo",
                relative_path="src/app.py",
                item_type="file",
                extension=".py",
                git_status="clean",
                version_scan_timestamp="2026-03-15T10:00:00+00:00",
            )
        ],
    )

    first_snapshot = snapshot_service.capture_snapshot_for_repository(repository, trigger_type="local_scan")
    second_snapshot = snapshot_service.capture_snapshot_for_repository(repository, trigger_type="local_scan")

    assert first_snapshot is not None
    assert second_snapshot is None
    assert len(job_log_repository.fetch_repository_snapshots("local::c:/demo")) == 1


def test_repository_snapshot_service_compare_snapshots_detects_file_and_commit_changes() -> None:
    """
    Prueft, dass der Snapshot-Diff neue, geloeschte und commitbezogene Aenderungen erkennt.
    """

    snapshot_a = RepositorySnapshot(
        id=1,
        repo_key="local::c:/demo",
        snapshot_timestamp="2026-03-15T10:00:00+00:00",
        head_commit="abc123",
        files=[
            RepositorySnapshotFile(relative_path="src/app.py", path_type="file", extension=".py", content_hash="1"),
            RepositorySnapshotFile(relative_path="README.md", path_type="file", extension=".md", content_hash="2"),
        ],
    )
    snapshot_b = RepositorySnapshot(
        id=2,
        repo_key="local::c:/demo",
        snapshot_timestamp="2026-03-15T11:00:00+00:00",
        head_commit="def456",
        files=[
            RepositorySnapshotFile(relative_path="src/app.py", path_type="file", extension=".py", content_hash="1"),
            RepositorySnapshotFile(relative_path="src/new_file.ts", path_type="file", extension=".ts", content_hash="3"),
        ],
    )
    service = RepositorySnapshotService.__new__(RepositorySnapshotService)

    diff = RepositorySnapshotService.compare_snapshots(service, snapshot_a, snapshot_b)

    assert diff.new_files == ["src/new_file.ts"]
    assert diff.deleted_files == ["README.md"]
    assert diff.commit_changed is True
