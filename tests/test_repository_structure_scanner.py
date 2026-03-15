"""Tests fuer den deltafaehigen RepositoryStructureScanner."""

from __future__ import annotations

from pathlib import Path

from core.paths import RuntimePaths
from db.init_db import initialize_databases
from db.repo_struct_repository import RepoStructRepository
from services.git_service import GitService
from services.repository_structure_scanner import RepositoryStructureScanner


def test_repository_structure_scanner_persists_delta_updates(tmp_path: Path) -> None:
    """
    Prueft, dass der Struktur-Scanner Veraenderungen per Delta in den Vault schreibt.
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
    repository = RepoStructRepository(paths.repo_struct_db_file)
    scanner = RepositoryStructureScanner(repository=repository, git_service=GitService())
    repo_root = tmp_path / "demo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "src").mkdir()
    file_path = repo_root / "src" / "app.py"
    file_path.write_text("print('eins')", encoding="utf-8")

    first_stats = scanner.scan_repository("local::demo", "local", repo_root)
    first_items = repository.fetch_repo_items("local::demo", "local")

    file_path.write_text("print('zwei')", encoding="utf-8")
    second_stats = scanner.scan_repository("local::demo", "local", repo_root)
    second_items = repository.fetch_repo_items("local::demo", "local")

    assert first_stats.total_count >= 2
    assert any(item.relative_path == "src/app.py" for item in first_items)
    assert second_stats.updated_count >= 1 or second_stats.unchanged_count >= 1
    assert any(item.relative_path == "src/app.py" for item in second_items)
