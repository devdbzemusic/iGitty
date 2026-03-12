"""Tests fuer die SQLite-Initialisierung."""

from pathlib import Path

from core.paths import RuntimePaths
from db.job_log_repository import JobLogRepository
from db.init_db import initialize_databases
from db.sqlite_manager import sqlite_connection
from models.job_models import ActionRecord, CloneRecord


def test_initialize_databases_creates_files(tmp_path: Path) -> None:
    """
    Prueft die Erzeugung der beiden MVP-Datenbanken.

    Eingabeparameter:
    - tmp_path: Von pytest bereitgestelltes temporaeres Verzeichnis.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - AssertionError, wenn Dateien nicht erzeugt wurden.

    Wichtige interne Logik:
    - Verwendet ein isoliertes Temp-Verzeichnis, damit kein reales Projektmaterial beeinflusst wird.
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

    assert paths.jobs_db_file.exists()
    assert paths.repo_struct_db_file.exists()
    assert paths.state_db_file.exists()


def test_has_successful_clone_matches_remote_url_or_repo_id(tmp_path: Path) -> None:
    """
    Prueft, dass der Clone-Nachweis nicht nur ueber den Repository-Namen funktioniert.
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
    repository = JobLogRepository(paths.jobs_db_file)
    repository.add_clone_record(
        CloneRecord(
            job_id="job-9",
            repo_id=999,
            repo_name="demo",
            remote_url="https://example.invalid/demo.git",
            local_path="C:/demo",
            status="success",
            message="ok",
        )
    )

    assert repository.has_successful_clone("anderer-name", remote_url="https://example.invalid/demo.git", repo_id=0) is True
    assert repository.has_successful_clone("anderer-name", remote_url="", repo_id=999) is True


def test_initialize_databases_creates_extended_history_tables(tmp_path: Path) -> None:
    """
    Prueft, dass die erweiterten Job-Logging-Tabellen fuer Steps, Snapshots und Spezialhistorien existieren.
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

    with sqlite_connection(paths.jobs_db_file) as connection:
        table_names = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }

    assert {"job_steps", "repo_snapshots", "commit_history", "push_history", "delete_history"} <= table_names


def test_add_action_record_writes_specialized_history(tmp_path: Path) -> None:
    """
    Prueft, dass ein Push-Eintrag sowohl in der allgemeinen als auch in der spezialisierten Historie landet.
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
    repository = JobLogRepository(paths.jobs_db_file)
    repository.add_action_record(
        ActionRecord(
            job_id="job-push-1",
            action_type="push",
            repo_name="demo",
            source_type="local",
            local_path="C:/demo",
            remote_url="https://example.invalid/demo.git",
            status="success",
            message="Push ok",
            repo_owner="dbzs",
            reversible_flag=False,
        )
    )

    with sqlite_connection(paths.jobs_db_file) as connection:
        push_row = connection.execute("SELECT repo_name, repo_owner, status FROM push_history").fetchone()
        snapshot_row = connection.execute("SELECT action_type, repo_name FROM repo_snapshots").fetchone()
        step_row = connection.execute("SELECT step_name, status FROM job_steps").fetchone()

    assert push_row is not None
    assert push_row["repo_owner"] == "dbzs"
    assert snapshot_row is not None
    assert snapshot_row["action_type"] == "push"
    assert step_row is not None
    assert step_row["step_name"] == "push"
