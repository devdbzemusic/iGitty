"""Tests fuer den Delete-Service."""

from models.repo_models import RemoteRepo
from services.delete_service import DeleteService


class DummyDeleteGitHubService:
    """Test-Double fuer GitHub-Delete-Aufrufe."""

    def __init__(self) -> None:
        """
        Initialisiert das Aufrufprotokoll fuer Assertions.
        """

        self.deleted: list[tuple[str, str]] = []

    def delete_repository(self, owner: str, name: str) -> None:
        """
        Merkt sich den Delete-Aufruf fuer Assertions.
        """

        self.deleted.append((owner, name))


def test_delete_service_returns_success_result() -> None:
    """
    Prueft, dass erfolgreiche Delete-Aufrufe als Erfolgsergebnis zurueckgegeben werden.
    """

    github_service = DummyDeleteGitHubService()
    service = DeleteService(github_service=github_service)
    repositories = [
        RemoteRepo(
            repo_id=4,
            name="demo",
            full_name="owner/demo",
            owner="owner",
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
    ]

    results = service.delete_repositories(repositories, job_id="job-2")

    assert results[0].status == "success"
    assert github_service.deleted == [("owner", "demo")]
