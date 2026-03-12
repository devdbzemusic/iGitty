"""Service fuer Push-Ablaufe lokaler Repositories nach GitHub."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from db.state_repository import StateRepository
from models.job_models import ActionRecord
from models.repo_models import LocalRepo
from models.state_models import RepositoryState, RepoStatusEvent
from services.git_service import GitService
from services.github_service import GitHubService
from services.state_db import compute_repository_status


class PushService:
    """Fuehrt Pushes aus und erstellt bei Bedarf neue GitHub-Repositories."""

    def __init__(
        self,
        git_service: GitService,
        github_service: GitHubService,
        state_repository: StateRepository | None = None,
    ) -> None:
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
        self._state_repository = state_repository

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
                repository_state = self.load_repository_state(repository)
                repository_status = self._resolve_repository_status(repository, repository_state)
                if repository_status == "BROKEN_GIT":
                    raise RuntimeError("Repository ist als BROKEN_GIT markiert. Bitte zuerst ueber das Kontextmenue reparieren.")
                if repository_status == "NOT_INITIALIZED":
                    raise RuntimeError("Repository ist nicht initialisiert. Bitte zuerst Git initialisieren.")
                if repository_status == "REMOTE_MISSING":
                    raise RuntimeError("Remote existiert online nicht mehr. Bitte Remote entfernen oder neu erstellen.")

                if repository_status == "LOCAL_ONLY" or not remote_url:
                    if not create_remote:
                        raise RuntimeError("Kein Remote vorhanden und Remote-Erstellung deaktiviert.")
                    remote_repo = self._github_service.create_repository(
                        name=repository.name,
                        private=remote_private if not repository.publish_as_public else False,
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
                        reversible_flag=False,
                    )
                )
                self._write_state_event(repository_state, repository.full_path, "PUSH_COMPLETED", "Push erfolgreich abgeschlossen.")
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
                        reversible_flag=False,
                    )
                )
                self._write_state_event(repository_state, repository.full_path, "PUSH_FAILED", str(error))
        return results

    def load_repository_state(self, repository: LocalRepo) -> RepositoryState | None:
        """
        Laedt den bekannten Zustand eines lokalen Repositories aus der State-Datenbank.

        Eingabeparameter:
        - repository: Lokales Repository aus UI oder Workflow.

        Rueckgabewerte:
        - Persistierter Zustand oder `None`, wenn noch kein Indexeintrag existiert.

        Moegliche Fehlerfaelle:
        - Keine; fehlende State-Datenbank fuehrt zu `None`.

        Wichtige interne Logik:
        - Der Push-Workflow bleibt auch ohne Scan-Daten benutzbar und faellt dann auf UI-Daten zurueck.
        """

        if self._state_repository is None:
            return None
        return self._state_repository.fetch_repository_by_local_path(repository.full_path)

    def remove_remote_and_keep_local(self, repository: LocalRepo) -> None:
        """
        Entfernt den konfigurierten Remote eines lokalen Repositories.

        Eingabeparameter:
        - repository: Ziel-Repository fuer die Reparaturaktion.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git lehnt das Entfernen des Remotes ab.

        Wichtige interne Logik:
        - Die Methode wird fuer `REMOTE_MISSING` und manuelle Kontextaktionen verwendet.
        """

        self._git_service.ensure_git_available()
        self._git_service.remove_remote_origin(Path(repository.full_path))
        self._write_state_event(self.load_repository_state(repository), repository.full_path, "REMOTE_REMOVED", "Remote origin wurde entfernt.")

    def reinitialize_repository(self, repository: LocalRepo) -> None:
        """
        Initialisiert ein lokales Repository erneut mit `git init`.

        Eingabeparameter:
        - repository: Ziel-Repository fuer die Reparatur.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git-Initialisierung schlaegt fehl.

        Wichtige interne Logik:
        - Die Methode fuehrt bewusst keinen Commit und kein Remote-Setup aus.
        """

        self._git_service.ensure_git_available()
        self._git_service.initialize_repository(Path(repository.full_path))
        self._write_state_event(self.load_repository_state(repository), repository.full_path, "REPOSITORY_REINITIALIZED", "Repository wurde per git init neu initialisiert.")

    def _resolve_repository_status(self, repository: LocalRepo, repository_state: RepositoryState | None) -> str:
        """
        Leitet den fuer den Push massgeblichen Repository-Status ab.

        Eingabeparameter:
        - repository: UI-nahes LocalRepo-Modell.
        - repository_state: Optionaler persistierter Zustand aus der State-Datenbank.

        Rueckgabewerte:
        - Fachlicher Statuswert wie `REMOTE_OK` oder `REMOTE_MISSING`.

        Moegliche Fehlerfaelle:
        - Keine; es wird immer ein defensiver Fallback geliefert.

        Wichtige interne Logik:
        - Persistente Scan-Daten haben Vorrang, danach wird auf lokale UI-Metadaten zurueckgefallen.
        """

        if repository_state is not None and repository_state.status:
            return repository_state.status
        if repository.remote_status and repository.remote_status != "-":
            return repository.remote_status
        return compute_repository_status(True, repository.has_remote, repository.remote_exists_online)

    def _write_state_event(
        self,
        repository_state: RepositoryState | None,
        local_path: str,
        event_type: str,
        message: str,
    ) -> None:
        """
        Schreibt ein technisches Ereignis in `repo_status_events`, wenn ein State-Eintrag bekannt ist.

        Eingabeparameter:
        - repository_state: Bereits geladener oder optional fehlender Repository-Zustand.
        - local_path: Lokaler Repository-Pfad fuer einen eventuellen Nach-Lookup.
        - event_type: Technischer Ereignistyp.
        - message: Lesbare Zusatzinformation.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehlende State-Daten fuehren still zu keinem Event.

        Wichtige interne Logik:
        - Die Methode bleibt defensiv, damit Push- und Reparaturpfade nie an einer Event-Schreibspur scheitern.
        """

        if self._state_repository is None:
            return
        effective_state = repository_state or self._state_repository.fetch_repository_by_local_path(local_path)
        if effective_state is None or effective_state.id is None:
            return
        self._state_repository.add_status_event(
            RepoStatusEvent(
                repo_id=int(effective_state.id),
                event_type=event_type,
                message=message,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
