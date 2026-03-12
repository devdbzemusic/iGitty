"""Tests fuer die lesende Diagnoseaufbereitung des State-Layers."""

from __future__ import annotations

from pathlib import Path

from core.paths import RuntimePaths
from db.init_db import initialize_databases
from db.state_repository import StateRepository
from models.state_models import RepoStatusEvent, RepositoryState
from services.state_view_service import StateViewService


def _build_runtime_paths(tmp_path: Path) -> RuntimePaths:
    """
    Erstellt isolierte Laufzeitpfade fuer Diagnose-Tests.
    """

    paths = RuntimePaths(
        project_root=tmp_path,
        assets_dir=tmp_path / "assets",
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        jobs_db_file=tmp_path / "data" / "igitty_jobs.db",
        repo_struct_db_file=tmp_path / "data" / "repo_struct_vault.db",
        state_db_file=tmp_path / "data" / "igitty_state.db",
        log_file=tmp_path / "logs" / "igitty.log",
        stylesheet_file=tmp_path / "assets" / "styles" / "neon_dark.qss",
    )
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    initialize_databases(paths)
    return paths


def test_state_view_service_formats_repository_diagnostics(tmp_path: Path) -> None:
    """
    Prueft, dass die Diagnoseansicht Repository-Status und juengste Events zusammenfasst.
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
            remote_exists_online=1,
            remote_visibility="public",
            status="REMOTE_OK",
            last_local_scan_at="2026-03-12T10:00:00+00:00",
            last_remote_check_at="2026-03-12T10:01:00+00:00",
        )
    )
    repository.add_status_event(
        RepoStatusEvent(
            repo_id=int(state.id or 0),
            event_type="LOCAL_SCAN_COMPLETED",
            message="Lokaler Scan fertig.",
            created_at="2026-03-12T10:02:00+00:00",
        )
    )
    service = StateViewService(repository)

    lines = service.build_local_repo_diagnostics("C:/demo")

    assert lines[0] == "Status: REMOTE_OK"
    assert any("LOCAL_SCAN_COMPLETED" in line for line in lines)


def test_state_view_service_handles_missing_repository(tmp_path: Path) -> None:
    """
    Prueft, dass unbekannte Repositories eine stabile Platzhalterdiagnose liefern.
    """

    paths = _build_runtime_paths(tmp_path)
    service = StateViewService(StateRepository(paths.state_db_file))

    lines = service.build_local_repo_diagnostics("C:/unknown")

    assert lines == ["Noch kein persistierter State-Eintrag fuer dieses Repository vorhanden."]
