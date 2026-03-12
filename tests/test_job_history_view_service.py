"""Tests fuer die lesende UI-Aufbereitung der Job-Historie."""

from __future__ import annotations

from pathlib import Path

from core.paths import RuntimePaths
from db.init_db import initialize_databases
from db.job_log_repository import JobLogRepository
from models.job_models import ActionRecord, CloneRecord
from services.job_history_view_service import JobHistoryViewService


def _build_runtime_paths(tmp_path: Path) -> RuntimePaths:
    """
    Erstellt isolierte Laufzeitpfade fuer Job-Historien-Tests.
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


def test_job_history_view_service_combines_clone_and_action_history(tmp_path: Path) -> None:
    """
    Prueft, dass Clone- und Aktionshistorie gemeinsam fuer die UI aufbereitet werden.
    """

    paths = _build_runtime_paths(tmp_path)
    repository = JobLogRepository(paths.jobs_db_file)
    repository.add_clone_record(
        CloneRecord(
            job_id="clone-1",
            repo_id=1,
            repo_name="demo",
            repo_owner="dbzs",
            remote_url="https://github.com/dbzs/demo.git",
            local_path="C:/demo",
            status="success",
            message="Clone ok",
        )
    )
    repository.add_action_record(
        ActionRecord(
            job_id="push-1",
            action_type="push",
            repo_name="demo",
            source_type="local",
            repo_owner="dbzs",
            local_path="C:/demo",
            remote_url="https://github.com/dbzs/demo.git",
            status="success",
            message="Push ok",
        )
    )
    service = JobHistoryViewService(repository)

    lines = service.build_repo_history(
        repo_name="demo",
        remote_url="https://github.com/dbzs/demo.git",
        local_path="C:/demo",
    )

    assert len(lines) == 2
    assert any("clone" in line for line in lines)
    assert any("push" in line for line in lines)


def test_job_history_view_service_handles_missing_history(tmp_path: Path) -> None:
    """
    Prueft, dass fehlende Historie eine stabile Platzhalterzeile liefert.
    """

    paths = _build_runtime_paths(tmp_path)
    service = JobHistoryViewService(JobLogRepository(paths.jobs_db_file))

    lines = service.build_repo_history(repo_name="demo")

    assert lines == ["Keine Job-Historie fuer dieses Repository vorhanden."]
