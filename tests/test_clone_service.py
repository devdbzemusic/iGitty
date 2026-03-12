"""Tests fuer die Clone-Orchestrierung."""

from pathlib import Path

from models.repo_models import RemoteRepo
from services.clone_service import CloneService


class DummyCloneGitService:
    """Test-Double fuer Clone-Operationen ohne echte Git-Prozesse."""

    def __init__(self) -> None:
        """
        Initialisiert den Testzustand fuer spaetere Clone-Aufrufe.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Merkt sich geklonte Ziele, damit der Test das Verhalten pruefen kann.
        """

        self.cloned_targets: list[Path] = []

    def ensure_git_available(self) -> None:
        """
        Simuliert eine vorhandene Git-CLI.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Test konzentriert sich auf die Orchestrierung und nicht auf echte Systemabhaengigkeiten.
        """

    def clone_repository(self, clone_url: str, target_path: Path) -> None:
        """
        Simuliert einen erfolgreichen Clone in ein neues Zielverzeichnis.

        Eingabeparameter:
        - clone_url: Unbenutzte Test-URL.
        - target_path: Zielpfad fuer den simulierten Clone.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Erzeugt den Zielordner real, damit nachfolgende Pfadpruefungen realistisch bleiben.
        """

        target_path.mkdir(parents=True, exist_ok=False)
        self.cloned_targets.append(target_path)


def test_clone_service_skips_existing_targets(tmp_path: Path) -> None:
    """
    Prueft, dass bestehende Zielordner sicher uebersprungen werden.

    Eingabeparameter:
    - tmp_path: Temporäres Testverzeichnis von pytest.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - AssertionError bei falscher Clone-Orchestrierung.

    Wichtige interne Logik:
    - Simuliert einen Batch mit einem neuen und einem bereits vorhandenen Zielverzeichnis.
    """

    existing_repo_path = tmp_path / "existing-repo"
    existing_repo_path.mkdir()
    repositories = [
        RemoteRepo(
            repo_id=1,
            name="new-repo",
            full_name="owner/new-repo",
            owner="owner",
            visibility="public",
            default_branch="main",
            language="Python",
            archived=False,
            fork=False,
            clone_url="https://example.invalid/new-repo.git",
            ssh_url="git@example.invalid:new-repo.git",
            html_url="https://example.invalid/new-repo",
            description="",
        ),
        RemoteRepo(
            repo_id=2,
            name="existing-repo",
            full_name="owner/existing-repo",
            owner="owner",
            visibility="public",
            default_branch="main",
            language="Python",
            archived=False,
            fork=False,
            clone_url="https://example.invalid/existing-repo.git",
            ssh_url="git@example.invalid:existing-repo.git",
            html_url="https://example.invalid/existing-repo",
            description="",
        ),
    ]
    git_service = DummyCloneGitService()
    service = CloneService(git_service=git_service)

    results = service.clone_repositories(repositories=repositories, target_root=tmp_path, job_id="job-1")

    assert len(results) == 2
    assert results[0].status == "success"
    assert results[1].status == "skipped"
    assert tmp_path.joinpath("new-repo").exists()
