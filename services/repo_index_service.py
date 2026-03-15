"""Persistente Indexierung lokaler Git-Repositories fuer den neuen State-Layer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.logger import AppLogger
from db.state_repository import StateRepository
from models.state_models import RepoStatusEvent, RepositoryState
from services.git_inspector_service import GitInspectorService
from services.remote_validation_service import RemoteValidationService
from services.repo_structure_service import RepoStructureService
from services.state_db import compute_repository_status


class RepoIndexService:
    """Scannt einen Wurzelordner, persistiert Repository-Zustaende und indexiert Dateien."""

    def __init__(
        self,
        state_repository: StateRepository,
        git_inspector_service: GitInspectorService,
        remote_validation_service: RemoteValidationService | None = None,
        repo_structure_service: RepoStructureService | None = None,
        logger: AppLogger | None = None,
    ) -> None:
        """
        Initialisiert die Indexierung mit den benoetigten Fachservices.

        Eingabeparameter:
        - state_repository: Persistente Ablage fuer Repository-Zustaende.
        - git_inspector_service: Liest Git-Metadaten aus lokalen Repositories.
        - remote_validation_service: Optionaler Online-Check fuer GitHub-Remotes.
        - repo_structure_service: Optionaler Dateiindex fuer gefundene Repositories.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Die optionalen Abhaengigkeiten erlauben schnelle Tests ohne Netzwerk oder Dateiindex.
        """

        self._state_repository = state_repository
        self._git_inspector_service = git_inspector_service
        self._remote_validation_service = remote_validation_service
        self._repo_structure_service = repo_structure_service
        self._logger = logger

    def scan_root(self, root_path: Path) -> list[RepositoryState]:
        """
        Scannt einen Wurzelordner nach Git-Repositories und persistiert den aktuellen Zustand.

        Eingabeparameter:
        - root_path: Zu scannender Basisordner.

        Rueckgabewerte:
        - Liste aller aktualisierten RepositoryState-Eintraege.

        Moegliche Fehlerfaelle:
        - Einzelne defekte Repositories werden als `BROKEN_GIT` markiert, ohne den Gesamtscan abzubrechen.

        Wichtige interne Logik:
        - Erkennt Repositories ueber vorhandene `.git`-Ordner.
        - Schneidet erkannte Unterbaeume ab, damit verschachtelte Pfade nicht doppelt indexiert werden.
        """

        if not root_path.exists():
            if self._logger is not None:
                self._logger.warning(f"Root-Scan uebersprungen, Pfad existiert nicht: {root_path}")
            return []

        if self._logger is not None:
            self._logger.event("scan", "repo_index_root_begin", f"root_path={root_path}")
        indexed_repositories: list[RepositoryState] = []
        scan_timestamp = self._utc_now()
        for current_path, dir_names, _file_names in root_path.walk():
            if ".git" not in dir_names:
                continue

            if self._logger is not None:
                self._logger.event("scan", "repo_index_repository_found", f"repo_path={current_path}")
            repository = self._inspect_repository(Path(current_path), scan_timestamp)
            repository = self._state_repository.upsert_repository(repository)
            self._state_repository.add_status_event(
                RepoStatusEvent(
                    repo_id=int(repository.id or 0),
                    event_type="LOCAL_SCAN_COMPLETED",
                    message=f"Lokaler Scan fuer '{repository.name}' abgeschlossen.",
                    created_at=scan_timestamp,
                )
            )

            if self._remote_validation_service is not None and repository.has_remote:
                if self._logger is not None:
                    self._logger.event(
                        "scan",
                        "remote_validation_begin",
                        f"name={repository.name} | remote_url={repository.remote_url}",
                    )
                repository = self._remote_validation_service.validate_repository(repository)
                self._state_repository.add_status_event(
                    RepoStatusEvent(
                        repo_id=int(repository.id or 0),
                        event_type="REMOTE_VALIDATION_COMPLETED",
                        message=f"Remote-Status: {repository.status}",
                        created_at=self._utc_now(),
                    )
                )

            if self._repo_structure_service is not None and repository.id is not None:
                if self._logger is not None:
                    self._logger.event(
                        "scan",
                        "file_index_begin",
                        f"name={repository.name} | repo_id={repository.id} | local_path={repository.local_path}",
                    )
                indexed_count = self._repo_structure_service.index_repository_files(int(repository.id), Path(repository.local_path))
                self._state_repository.add_status_event(
                    RepoStatusEvent(
                        repo_id=int(repository.id),
                        event_type="FILE_INDEX_COMPLETED",
                        message=f"{indexed_count} Dateien indexiert.",
                        created_at=self._utc_now(),
                    )
                )

            indexed_repositories.append(repository)
            dir_names[:] = []

        indexed_repositories.sort(key=lambda item: item.name.lower())
        if self._logger is not None:
            self._logger.event(
                "scan",
                "repo_index_root_complete",
                f"root_path={root_path} | repositories={len(indexed_repositories)}",
            )
        return indexed_repositories

    def _inspect_repository(self, repo_path: Path, scan_timestamp: str) -> RepositoryState:
        """
        Baut einen persistierbaren RepositoryState aus der Git-Inspektion auf.

        Eingabeparameter:
        - repo_path: Lokaler Pfad des gefundenen Repositories.
        - scan_timestamp: Zeitstempel des aktuellen Root-Scans.

        Rueckgabewerte:
        - Vorbereiteter RepositoryState fuer Persistenz und Weiterverarbeitung.

        Moegliche Fehlerfaelle:
        - Fehlerhafte Git-Repositories werden als `BROKEN_GIT` modelliert.

        Wichtige interne Logik:
        - Das Mapping liegt zentral hier, damit weder Scanner noch UI rohes Git-Output kennen muessen.
        """

        try:
            if self._logger is not None:
                self._logger.event("scan", "inspect_repository_state_begin", f"repo_path={repo_path}")
            data = self._git_inspector_service.inspect_repository(repo_path)
        except Exception as error:  # noqa: BLE001
            if self._logger is not None:
                self._logger.warning(f"Repository konnte nicht inspiziert werden: {repo_path} | {error}")
            return RepositoryState(
                name=repo_path.name,
                local_path=str(repo_path),
                is_git_repo=False,
                current_branch="",
                head_commit="",
                head_commit_date="",
                has_remote=False,
                remote_name="",
                remote_url="",
                remote_host="",
                remote_owner="",
                remote_repo_name="",
                remote_exists_online=None,
                remote_visibility="unknown",
                status="BROKEN_GIT",
                last_local_scan_at=scan_timestamp,
                last_remote_check_at="",
            )

        is_git_repo = bool(data.get("is_git_repo"))
        status = "BROKEN_GIT" if not is_git_repo else compute_repository_status(
            is_git_repo,
            bool(data.get("has_remote")),
            None,
        )

        repository_state = RepositoryState(
            name=str(data.get("name") or repo_path.name),
            local_path=str(data.get("local_path") or repo_path),
            is_git_repo=is_git_repo,
            current_branch=str(data.get("branch") or ""),
            head_commit=str(data.get("head_commit") or ""),
            head_commit_date=str(data.get("head_commit_date") or ""),
            has_remote=bool(data.get("has_remote")),
            remote_name=str(data.get("remote_name") or ""),
            remote_url=str(data.get("remote_url") or ""),
            remote_host=str(data.get("remote_host") or ""),
            remote_owner=str(data.get("remote_owner") or ""),
            remote_repo_name=str(data.get("remote_repo_name") or ""),
            remote_exists_online=None,
            remote_visibility="unknown" if data.get("has_remote") else "not_published",
            status=status,
            last_local_scan_at=scan_timestamp,
            last_remote_check_at="",
        )
        if self._logger is not None:
            self._logger.event(
                "scan",
                "inspect_repository_state_complete",
                f"name={repository_state.name} | status={repository_state.status} | has_remote={repository_state.has_remote}",
            )
        return repository_state

    def _utc_now(self) -> str:
        """
        Liefert einen konsistenten UTC-Zeitstempel fuer Index-Operationen.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - ISO-Zeitstempel mit Zeitzone.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Zentralisiert die Zeitstempelbildung fuer reproduzierbare Tests.
        """

        return datetime.now(timezone.utc).isoformat()
