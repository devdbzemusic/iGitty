"""Service fuer Commit-Ablaufe lokaler Repositories."""

from __future__ import annotations

from pathlib import Path

from models.job_models import ActionRecord
from models.repo_models import LocalRepo
from services.git_service import GitService


class CommitService:
    """Fuehrt Commit-Aktionen fuer lokale Repositories kontrolliert aus."""

    def __init__(self, git_service: GitService) -> None:
        """
        Initialisiert den Service mit einer Git-Abhaengigkeit.

        Eingabeparameter:
        - git_service: Git-CLI-Service fuer die eigentlichen Befehle.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Initialisierung.

        Wichtige interne Logik:
        - Commit-Fachlogik bleibt von UI und Dialogen getrennt.
        """

        self._git_service = git_service

    def commit_repositories(self, repositories: list[LocalRepo], message: str, stage_all: bool, job_id: str) -> list[ActionRecord]:
        """
        Fuehrt fuer mehrere lokale Repositories einen Commit durch.

        Eingabeparameter:
        - repositories: Ausgewaehlte lokale Repositories.
        - message: Commit-Nachricht.
        - stage_all: `True` fuer `git add -A`, sonst nur tracked files.
        - job_id: Uebergeordnete Job-ID fuer den Batch.

        Rueckgabewerte:
        - Ergebnisliste je Repository.

        Moegliche Fehlerfaelle:
        - Git-Befehle koennen pro Repository fehlschlagen.

        Wichtige interne Logik:
        - Fehler eines Repositories stoppen nicht den gesamten Batch.
        """

        self._git_service.ensure_git_available()
        results: list[ActionRecord] = []
        for repository in repositories:
            repo_path = Path(repository.full_path)
            try:
                if stage_all:
                    self._git_service.stage_all_changes(repo_path)
                else:
                    self._git_service.stage_tracked_changes(repo_path)
                self._git_service.commit(repo_path, message)
                results.append(
                    ActionRecord(
                        job_id=job_id,
                        action_type="commit",
                        repo_name=repository.name,
                        source_type="local",
                        local_path=repository.full_path,
                        remote_url=repository.remote_url,
                        status="success",
                        message="Commit erfolgreich erstellt.",
                        reversible_flag=False,
                    )
                )
            except Exception as error:  # noqa: BLE001
                results.append(
                    ActionRecord(
                        job_id=job_id,
                        action_type="commit",
                        repo_name=repository.name,
                        source_type="local",
                        local_path=repository.full_path,
                        remote_url=repository.remote_url,
                        status="error",
                        message=str(error),
                        reversible_flag=False,
                    )
                )
        return results
