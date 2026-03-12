"""Service fuer Push-Ablaufe lokaler Repositories nach GitHub."""

from __future__ import annotations

from pathlib import Path

from models.job_models import ActionRecord
from models.repo_models import LocalRepo
from services.git_service import GitService
from services.github_service import GitHubService


class PushService:
    """Fuehrt Pushes aus und erstellt bei Bedarf neue GitHub-Repositories."""

    def __init__(self, git_service: GitService, github_service: GitHubService) -> None:
        """
        Initialisiert den Push-Service mit Git- und GitHub-Abhaengigkeiten.

        Eingabeparameter:
        - git_service: Service fuer lokale Git-Befehle.
        - github_service: Service fuer GitHub-REST-Operationen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Verbindet lokale und remote Schritte an genau einer Stelle.
        """

        self._git_service = git_service
        self._github_service = github_service

    def push_repositories(
        self,
        repositories: list[LocalRepo],
        create_remote: bool,
        remote_private: bool,
        description: str,
        job_id: str,
    ) -> list[ActionRecord]:
        """
        Fuehrt Pushes fuer mehrere lokale Repositories aus.

        Eingabeparameter:
        - repositories: Ausgewaehlte lokale Repositories.
        - create_remote: Ob fehlende Remotes auf GitHub angelegt werden sollen.
        - remote_private: Sichtbarkeit fuer neu erzeugte Remotes.
        - description: Optionale Beschreibung fuer neue Remotes.
        - job_id: Uebergeordnete Job-ID fuer den Batch.

        Rueckgabewerte:
        - Ergebnisliste je Repository.

        Moegliche Fehlerfaelle:
        - Git- oder GitHub-Schritte koennen pro Repository fehlschlagen.

        Wichtige interne Logik:
        - Existierende Remotes werden direkt genutzt, fehlende bei Bedarf on-demand erzeugt.
        """

        self._git_service.ensure_git_available()
        results: list[ActionRecord] = []
        for repository in repositories:
            repo_path = Path(repository.full_path)
            remote_url = repository.remote_url
            try:
                if not remote_url:
                    if not create_remote:
                        raise RuntimeError("Kein Remote vorhanden und Remote-Erstellung deaktiviert.")
                    remote_repo = self._github_service.create_repository(
                        name=repository.name,
                        private=remote_private,
                        description=description,
                    )
                    remote_url = remote_repo.clone_url
                    self._git_service.set_remote_origin(repo_path, remote_url)

                branch_name = repository.current_branch if repository.current_branch and repository.current_branch != "-" else "main"
                self._git_service.push_current_branch(repo_path, branch_name)
                results.append(
                    ActionRecord(
                        job_id=job_id,
                        action_type="push",
                        repo_name=repository.name,
                        source_type="local",
                        local_path=repository.full_path,
                        remote_url=remote_url,
                        status="success",
                        message="Push erfolgreich abgeschlossen.",
                    )
                )
            except Exception as error:  # noqa: BLE001
                results.append(
                    ActionRecord(
                        job_id=job_id,
                        action_type="push",
                        repo_name=repository.name,
                        source_type="local",
                        local_path=repository.full_path,
                        remote_url=remote_url,
                        status="error",
                        message=str(error),
                    )
                )
        return results
