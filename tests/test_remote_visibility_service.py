"""Tests fuer den Service zur Aenderung der Remote-Sichtbarkeit."""

from __future__ import annotations

from models.repo_models import RemoteRepo
from services.remote_visibility_service import RemoteVisibilityService


class DummyRemoteVisibilityGitHubService:
    """Test-Double fuer GitHub-Aufrufe zur Sichtbarkeitsaenderung."""

    def __init__(self, should_fail: bool = False) -> None:
        """
        Konfiguriert, ob der simulierte GitHub-Aufruf erfolgreich sein oder fehlschlagen soll.

        Eingabeparameter:
        - should_fail: Steuert, ob der Test-Double eine Ausnahme ausloest.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Objekt merkt sich den letzten Aufruf, damit der Service die korrekten
          Parameter an die GitHub-Schicht uebergibt.
        """

        self.should_fail = should_fail
        self.calls: list[tuple[str, str, bool]] = []

    def update_repository_visibility(self, owner: str, name: str, private: bool) -> RemoteRepo:
        """
        Simuliert eine GitHub-Sichtbarkeitsaenderung oder loest absichtlich einen Fehler aus.

        Eingabeparameter:
        - owner: GitHub-Owner des Ziel-Repositories.
        - name: Repository-Name.
        - private: Zielzustand fuer das Remote.

        Rueckgabewerte:
        - Aktualisiertes RemoteRepo fuer Erfolgsfaelle.

        Moegliche Fehlerfaelle:
        - RuntimeError, wenn `should_fail` aktiviert wurde.

        Wichtige interne Logik:
        - Der Rueckgabewert spiegelt die von GitHub erwartete finale Sichtbarkeit wider.
        """

        self.calls.append((owner, name, private))
        if self.should_fail:
            raise RuntimeError("GitHub verweigert die Sichtbarkeitsaenderung")
        return RemoteRepo(
            repo_id=7,
            name=name,
            full_name=f"{owner}/{name}",
            owner=owner,
            visibility="private" if private else "public",
            default_branch="main",
            language="Python",
            archived=False,
            fork=False,
            clone_url=f"https://example.invalid/{name}.git",
            ssh_url=f"git@example.invalid:{name}.git",
            html_url=f"https://example.invalid/{name}",
            description="",
        )


def test_change_visibility_returns_success_and_updated_repository() -> None:
    """
    Prueft, dass der Service bei Erfolg ein Aktionsergebnis und das aktualisierte Repo liefert.
    """

    github_service = DummyRemoteVisibilityGitHubService()
    service = RemoteVisibilityService(github_service=github_service)
    repository = RemoteRepo(
        repo_id=7,
        name="demo",
        full_name="dbzs/demo",
        owner="dbzs",
        visibility="public",
        default_branch="main",
        language="Python",
        archived=False,
        fork=False,
        clone_url="https://example.invalid/demo.git",
        ssh_url="git@example.invalid:demo.git",
        html_url="https://example.invalid/demo",
        description="",
    )

    result, updated_repository = service.change_visibility(repository, "private", "job-visibility-1")

    assert github_service.calls == [("dbzs", "demo", True)]
    assert result.status == "success"
    assert "public auf private" in result.message
    assert updated_repository is not None
    assert updated_repository.visibility == "private"


def test_change_visibility_returns_error_result_when_github_fails() -> None:
    """
    Prueft, dass GitHub-Fehler als regulaeres Fehlerergebnis an den Controller gehen.
    """

    github_service = DummyRemoteVisibilityGitHubService(should_fail=True)
    service = RemoteVisibilityService(github_service=github_service)
    repository = RemoteRepo(
        repo_id=7,
        name="demo",
        full_name="dbzs/demo",
        owner="dbzs",
        visibility="private",
        default_branch="main",
        language="Python",
        archived=False,
        fork=False,
        clone_url="https://example.invalid/demo.git",
        ssh_url="git@example.invalid:demo.git",
        html_url="https://example.invalid/demo",
        description="",
    )

    result, updated_repository = service.change_visibility(repository, "public", "job-visibility-2")

    assert github_service.calls == [("dbzs", "demo", False)]
    assert result.status == "error"
    assert "GitHub verweigert" in result.message
    assert updated_repository is None
