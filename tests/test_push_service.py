"""Tests fuer den Push-Service."""

from models.repo_models import LocalRepo, RemoteRepo
from services.push_service import PushService


class DummyPushGitService:
    """Test-Double fuer Git-Operationen des Push-Services."""

    def __init__(self) -> None:
        """
        Initialisiert die Aufrufprotokolle fuer Assertions.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Merkt sich die aufgerufenen Remotes und Branches fuer spaetere Pruefungen.
        """

        self.remote_updates: list[tuple[str, str]] = []
        self.pushes: list[tuple[str, str]] = []

    def ensure_git_available(self) -> None:
        """
        Simuliert eine vorhandene Git-CLI.
        """

    def set_remote_origin(self, repo_path, remote_url: str) -> None:
        """
        Merkt sich die gesetzte Remote-URL fuer Assertions.
        """

        self.remote_updates.append((str(repo_path), remote_url))

    def push_current_branch(self, repo_path, branch_name: str) -> None:
        """
        Merkt sich den Push-Aufruf fuer Assertions.
        """

        self.pushes.append((str(repo_path), branch_name))


class DummyPushGitHubService:
    """Test-Double fuer GitHub-Repository-Erstellung."""

    def create_repository(self, name: str, private: bool, description: str) -> RemoteRepo:
        """
        Liefert ein simuliertes GitHub-Repository fuer den Push-Test.
        """

        return RemoteRepo(
            repo_id=77,
            name=name,
            full_name=f"owner/{name}",
            owner="owner",
            visibility="private" if private else "public",
            default_branch="main",
            language="Python",
            archived=False,
            fork=False,
            clone_url=f"https://example.invalid/{name}.git",
            ssh_url=f"git@example.invalid:{name}.git",
            html_url=f"https://example.invalid/{name}",
            description=description,
        )


def test_push_service_creates_remote_when_missing() -> None:
    """
    Prueft, dass der Push-Service bei fehlendem Remote zuerst ein GitHub-Repo erzeugt.
    """

    git_service = DummyPushGitService()
    github_service = DummyPushGitHubService()
    service = PushService(git_service=git_service, github_service=github_service)
    repositories = [
        LocalRepo(
            name="demo",
            full_path="C:/demo",
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
    ]

    results = service.push_repositories(repositories, create_remote=True, remote_private=True, description="Demo", job_id="job-1")

    assert results[0].status == "success"
    assert git_service.remote_updates[0][1] == "https://example.invalid/demo.git"
    assert git_service.pushes[0][1] == "main"
