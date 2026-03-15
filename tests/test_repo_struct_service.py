"""Tests fuer den Struktur-Scan-Service."""

from pathlib import Path

from models.repo_models import LocalRepo
from services.repo_struct_service import RepoStructService


class DummyRepoStructRepository:
    """Test-Double fuer die Persistenz des Struktur-Vaults."""

    def __init__(self) -> None:
        """
        Initialisiert den Testzustand fuer spaetere Scan-Ergebnisse.
        """

        self.calls: list[tuple[str, str, str, int]] = []

    def replace_repo_items(self, repo_identifier: str, source_type: str, root_path: str, items: list) -> None:
        """
        Merkt sich die Anzahl der gespeicherten Strukturknoten fuer Assertions.
        """

        self.calls.append((repo_identifier, source_type, root_path, len(items)))

    def fetch_repo_summary(self, repo_identifier: str, source_type: str) -> tuple[bool, int, str | None]:
        """
        Liefert eine feste Struktur-Zusammenfassung fuer Tests des Kontext-Services.
        """

        return True, 7, "2026-03-12T12:00:00"

    def fetch_repo_items(self, repo_identifier: str, source_type: str, include_deleted: bool = False) -> list:
        """
        Liefert eine leere Strukturliste fuer RepoViewer-nahe Tests.
        """

        return []


def test_repo_struct_service_scans_and_persists_items(tmp_path: Path) -> None:
    """
    Prueft, dass ein Struktur-Scan Knoten sammelt und an das Repository uebergibt.
    """

    repo_root = tmp_path / "demo_repo"
    repo_root.mkdir()
    (repo_root / "src").mkdir()
    (repo_root / "src" / "app.py").write_text("print('demo')", encoding="utf-8")
    repository = DummyRepoStructRepository()
    service = RepoStructService(repository=repository)
    local_repo = LocalRepo(
        name="demo_repo",
        full_path=str(repo_root),
        current_branch="main",
        has_remote=False,
        remote_url="",
        has_changes=False,
        untracked_count=0,
        modified_count=0,
        last_commit_hash="-",
        last_commit_date="-",
        last_commit_message="-",
    )

    results = service.scan_repositories([local_repo], job_id="job-3")

    assert results[0].status == "success"
    assert repository.calls[0][0] == f"local::{str(repo_root).lower()}"
    assert repository.calls[0][3] >= 2
