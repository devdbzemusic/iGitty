"""Tests fuer die SQLite-Initialisierung."""

from pathlib import Path

from core.paths import RuntimePaths
from db.init_db import initialize_databases


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
        log_file=tmp_path / "logs" / "igitty.log",
        stylesheet_file=tmp_path / "assets" / "styles" / "neon_dark.qss",
    )
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)

    initialize_databases(paths)

    assert paths.jobs_db_file.exists()
    assert paths.repo_struct_db_file.exists()


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
from db.job_log_repository import JobLogRepository
from models.job_models import CloneRecord
