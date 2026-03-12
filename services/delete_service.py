"""Service fuer sichere Remote-Loeschvorgaenge."""

from __future__ import annotations

from models.job_models import ActionRecord
from models.repo_models import RemoteRepo
from services.github_service import GitHubService


class DeleteService:
    """Loescht Remote-Repositories erst nach bestandener Vorpruefung."""

    def __init__(self, github_service: GitHubService) -> None:
        """
        Initialisiert den Service mit einer GitHub-Abhaengigkeit.

        Eingabeparameter:
        - github_service: Service fuer GitHub-Delete-Operationen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Initialisierung.

        Wichtige interne Logik:
        - Die Sicherheitspruefung selbst findet ausserhalb dieses Services statt.
        """

        self._github_service = github_service

    def delete_repositories(self, repositories: list[RemoteRepo], job_id: str) -> list[ActionRecord]:
        """
        Loescht mehrere Remote-Repositories ueber die GitHub-API.

        Eingabeparameter:
        - repositories: Bereits freigegebene Ziel-Repositories.
        - job_id: Uebergeordnete Job-ID fuer den Batch.

        Rueckgabewerte:
        - Ergebnisliste je Repository.

        Moegliche Fehlerfaelle:
        - GitHub lehnt einzelne Delete-Aufrufe ab.

        Wichtige interne Logik:
        - Fehler pro Repository werden gesammelt statt den Batch sofort abzubrechen.
        """

        results: list[ActionRecord] = []
        for repository in repositories:
            try:
                self._github_service.delete_repository(repository.owner, repository.name)
                results.append(
                    ActionRecord(
                        job_id=job_id,
                        action_type="delete_remote",
                        repo_name=repository.name,
                        source_type="remote",
                        local_path="",
                        remote_url=repository.html_url,
                        status="success",
                        message="Remote-Repository erfolgreich geloescht.",
                    )
                )
            except Exception as error:  # noqa: BLE001
                results.append(
                    ActionRecord(
                        job_id=job_id,
                        action_type="delete_remote",
                        repo_name=repository.name,
                        source_type="remote",
                        local_path="",
                        remote_url=repository.html_url,
                        status="error",
                        message=str(error),
                    )
                )
        return results
