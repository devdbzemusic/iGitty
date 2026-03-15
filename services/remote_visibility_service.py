"""Service fuer die Aenderung der GitHub-Repository-Sichtbarkeit."""

from __future__ import annotations

from models.job_models import ActionRecord
from models.repo_models import RemoteRepo
from services.github_service import GitHubService


class RemoteVisibilityService:
    """Kapselt die fachliche Sichtbarkeitsaenderung fuer Remote-Repositories."""

    def __init__(self, github_service: GitHubService) -> None:
        """
        Initialisiert den Service mit dem zentralen GitHub-Zugriff.

        Eingabeparameter:
        - github_service: Service fuer authentifizierte GitHub-API-Aufrufe.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Die Klasse bleibt bewusst schmal und konzentriert sich darauf, aus einem
          GitHub-Aufruf ein fuer Controller und Historie brauchbares Aktionsergebnis
          zu erzeugen.
        """

        self._github_service = github_service

    def change_visibility(
        self,
        repository: RemoteRepo,
        target_visibility: str,
        job_id: str,
    ) -> tuple[ActionRecord, RemoteRepo | None]:
        """
        Aendert die Sichtbarkeit eines einzelnen GitHub-Repositories.

        Eingabeparameter:
        - repository: Das aktuell in der UI bekannte Remote-Repository.
        - target_visibility: Gewuenschter Zielwert `public` oder `private`.
        - job_id: Uebergeordnete Job-ID fuer Historie und Logging.

        Rueckgabewerte:
        - Tupel aus allgemeinem Aktionsergebnis und optional aktualisiertem RemoteRepo.

        Moegliche Fehlerfaelle:
        - Ungueltige Ziel-Sichtbarkeit.
        - GitHub-API lehnt die Aenderung ab.

        Wichtige interne Logik:
        - Fehler werden als reguliaeres Aktionsergebnis zurueckgegeben, damit die UI
          denselben Ergebnisfluss wie bei anderen Aktionen verwenden kann.
        """

        normalized_visibility = target_visibility.strip().lower()
        if normalized_visibility not in {"public", "private"}:
            return (
                ActionRecord(
                    job_id=job_id,
                    action_type="set_remote_visibility",
                    repo_name=repository.name,
                    source_type="remote",
                    local_path="",
                    remote_url=repository.html_url,
                    status="error",
                    message=f"Ungueltige Ziel-Sichtbarkeit: {target_visibility}",
                    repo_owner=repository.owner,
                    reversible_flag=False,
                ),
                None,
            )

        try:
            updated_repository = self._github_service.update_repository_visibility(
                repository.owner,
                repository.name,
                private=normalized_visibility == "private",
            )
        except Exception as error:  # noqa: BLE001
            return (
                ActionRecord(
                    job_id=job_id,
                    action_type="set_remote_visibility",
                    repo_name=repository.name,
                    source_type="remote",
                    local_path="",
                    remote_url=repository.html_url,
                    status="error",
                    message=str(error),
                    repo_owner=repository.owner,
                    reversible_flag=False,
                ),
                None,
            )

        return (
            ActionRecord(
                job_id=job_id,
                action_type="set_remote_visibility",
                repo_name=repository.name,
                source_type="remote",
                local_path="",
                remote_url=updated_repository.html_url or repository.html_url,
                status="success",
                message=(
                    f"Sichtbarkeit von '{repository.name}' wurde von "
                    f"{repository.visibility} auf {updated_repository.visibility} geaendert."
                ),
                repo_owner=repository.owner,
                reversible_flag=False,
            ),
            updated_repository,
        )
