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


class DummyGitHubService:
    """Einfacher Test-Stub fuer die Sichtbarkeitsauflosung eines GitHub-Remotes."""

    def resolve_remote_metadata(self, remote_url: str) -> tuple[str, int]:
        """
        Liefert fuer den Test eine feste Sichtbarkeit samt Repo-ID.

        Eingabeparameter:
        - remote_url: Im Test uebergebene Remote-URL.

        Rueckgabewerte:
        - Tupel aus Sichtbarkeit und Repository-ID.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Ermoeglicht gezielte Assertions auf die neue Public-/Visibility-Logik.
        """

        return "public", 42


class DummyGitServiceWithoutRemote:
    """Einfacher Test-Stub fuer ein lokales Repository ohne konfiguriertes Remote."""

    def ensure_git_available(self) -> None:
        """
        Simuliert eine vorhandene Git-Installation.
        """

    def get_repo_details(self, repo_path: Path) -> dict[str, object]:
        """
        Liefert feste Testdaten fuer ein lokales Repository ohne Remote.
        """

        return {
            "branch": "main",
            "has_remote": False,
            "remote_url": "",
            "has_changes": False,
            "untracked_count": 0,
            "modified_count": 0,
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
    assert repositories[0].remote_visibility == "unknown"


def test_scan_repositories_sets_remote_visibility_when_github_metadata_exists(tmp_path: Path) -> None:
    """
    Prueft die Anreicherung lokaler Repositories mit GitHub-Sichtbarkeitsdaten.

    Eingabeparameter:
    - tmp_path: Temporäres Testverzeichnis von pytest.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - AssertionError bei fehlender Visibility-Aufloesung.

    Wichtige interne Logik:
    - Kombiniert lokalen Scan mit einem GitHub-Metadaten-Stub fuer die Public-Spalte.
    """

    repo_root = tmp_path / "demo_repo"
    (repo_root / ".git").mkdir(parents=True)
    (repo_root / "main.py").write_text("print('demo')", encoding="utf-8")

    service = LocalRepoService(git_service=DummyGitService(), github_service=DummyGitHubService())

    repositories = service.scan_repositories(tmp_path)

    assert repositories[0].remote_visibility == "public"
    assert repositories[0].publish_as_public is True
    assert repositories[0].remote_repo_id == 42


def test_scan_repositories_defaults_local_only_repositories_to_public(tmp_path: Path) -> None:
    """
    Prueft, dass lokale Repositories ohne Remote standardmaessig als public vorgemerkt sind.
    """

    repo_root = tmp_path / "demo_repo"
    (repo_root / ".git").mkdir(parents=True)
    (repo_root / "main.py").write_text("print('demo')", encoding="utf-8")

    service = LocalRepoService(git_service=DummyGitServiceWithoutRemote())

    repositories = service.scan_repositories(tmp_path)

    assert repositories[0].has_remote is False
    assert repositories[0].publish_as_public is True
    assert repositories[0].remote_visibility == "not_published"
