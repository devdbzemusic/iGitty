"""Tests fuer die SQLite-Initialisierung."""

from pathlib import Path

from core.paths import RuntimePaths
from db.job_log_repository import JobLogRepository
from db.init_db import initialize_databases
from db.sqlite_manager import sqlite_connection
from models.job_models import ActionRecord, CloneRecord
from services.state_db import initialize_state_database


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
        log_file=tmp_path / "logs" / "log.txt",
        stylesheet_file=tmp_path / "assets" / "styles" / "neon_dark.qss",
    )
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)

    initialize_databases(paths)

    assert paths.jobs_db_file.exists()
    assert paths.repo_struct_db_file.exists()
    assert paths.state_db_file.exists()

    with sqlite_connection(paths.state_db_file) as connection:
        table_names = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        repository_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(repositories)").fetchall()
        }
        repo_status_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(repo_status)").fetchall()
        }

    assert {"repositories", "repo_status", "repo_files", "repo_status_events", "scan_runs"} <= table_names
    assert {
        "repo_key",
        "source_type",
        "scan_fingerprint",
        "status_hash",
        "is_missing",
        "topics_json",
        "contributors_summary",
        "updated_at",
    } <= repository_columns
    assert {"repo_id", "exists_local", "needs_rescan", "sync_state", "health_state"} <= repo_status_columns


def test_initialize_state_database_migrates_legacy_repositories_before_creating_indexes(tmp_path: Path) -> None:
    """
    Prueft, dass eine alte State-DB ohne `repo_key` sauber erweitert wird, bevor neue Indizes angelegt werden.
    """

    database_file = tmp_path / "igitty_state.db"
    with sqlite_connection(database_file) as connection:
        connection.executescript(
            """
            CREATE TABLE repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                local_path TEXT
            );
            """
        )

    initialize_state_database(database_file)

    with sqlite_connection(database_file) as connection:
        repository_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(repositories)").fetchall()
        }
        index_names = {
            row["name"]
            for row in connection.execute("PRAGMA index_list(repositories)").fetchall()
        }

    assert "repo_key" in repository_columns
    assert "idx_repositories_repo_key" in index_names


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
        log_file=tmp_path / "logs" / "log.txt",
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
        log_file=tmp_path / "logs" / "log.txt",
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
        log_file=tmp_path / "logs" / "log.txt",
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
