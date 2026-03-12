"""Tests fuer die lokale Repository-Erkennung."""

from pathlib import Path

from services.local_repo_service import LocalRepoService


class DummyGitService:
    """Einfacher Test-Stub fuer Git-Abfragen ohne echte CLI-Aufrufe."""

    def ensure_git_available(self) -> None:
        """
        Simuliert eine vorhandene Git-Installation.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Test konzentriert sich auf den Scanner und nicht auf echte Git-Prozesse.
        """

    def get_repo_details(self, repo_path: Path) -> dict[str, object]:
        """
        Liefert feste Testdaten fuer ein erkanntes Repository.

        Eingabeparameter:
        - repo_path: Vom Scanner gefundener Repository-Pfad.

        Rueckgabewerte:
        - Deterministische Statuswerte fuer Assertions.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Rueckgabewert ist bewusst vollstaendig, damit der Scanner alle Felder fuellen kann.
        """

        return {
            "branch": "main",
            "has_remote": True,
            "remote_url": "https://example.invalid/repo.git",
            "has_changes": True,
            "untracked_count": 1,
            "modified_count": 2,
            "last_commit_hash": "abc1234",
            "last_commit_date": "2026-03-12T10:00:00+00:00",
            "last_commit_message": "Test Commit",
        }


def test_scan_repositories_finds_git_folder(tmp_path: Path) -> None:
    """
    Prueft die Erkennung eines lokalen Repositories ueber einen `.git`-Ordner.

    Eingabeparameter:
    - tmp_path: Temporäres Testverzeichnis von pytest.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - AssertionError bei fehlender Erkennung oder falschen Feldwerten.

    Wichtige interne Logik:
    - Legt ein minimales Dateibaum-Szenario an, das dem echten Scan-Verhalten entspricht.
    """

    repo_root = tmp_path / "demo_repo"
    (repo_root / ".git").mkdir(parents=True)
    (repo_root / "main.py").write_text("print('demo')", encoding="utf-8")

    service = LocalRepoService(git_service=DummyGitService())

    repositories = service.scan_repositories(tmp_path)

    assert len(repositories) == 1
    assert repositories[0].name == "demo_repo"
    assert repositories[0].current_branch == "main"
    assert repositories[0].has_remote is True
    assert repositories[0].language_guess == "Python"
