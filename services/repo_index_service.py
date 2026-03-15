"""Persistente Indexierung lokaler Git-Repositories fuer den neuen State-Layer."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from core.logger import AppLogger
from db.state_repository import StateRepository
from models.state_models import RepoStatusEvent, RepositoryState
from services.git_inspector_service import GitInspectorService
from services.repo_action_resolver import RepoActionResolver
from services.repo_fingerprint_service import RepoFingerprintService
from services.repository_snapshot_service import RepositorySnapshotService
from services.repository_structure_scanner import RepositoryStructureScanner
from services.remote_validation_service import RemoteValidationService
from services.repo_structure_service import RepoStructureService
from services.state_db import compute_repository_status


class RepoIndexService:
    """Scannt einen Wurzelordner, persistiert Repository-Zustaende und indexiert Dateien."""

    def __init__(
        self,
        state_repository: StateRepository,
        git_inspector_service: GitInspectorService,
        repo_fingerprint_service: RepoFingerprintService | None = None,
        remote_validation_service: RemoteValidationService | None = None,
        repo_structure_service: RepoStructureService | None = None,
        repository_structure_scanner: RepositoryStructureScanner | None = None,
        repo_action_resolver: RepoActionResolver | None = None,
        repository_snapshot_service: RepositorySnapshotService | None = None,
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
        self._repo_fingerprint_service = repo_fingerprint_service or RepoFingerprintService()
        self._remote_validation_service = remote_validation_service
        self._repo_structure_service = repo_structure_service
        self._repository_structure_scanner = repository_structure_scanner
        self._repo_action_resolver = repo_action_resolver or RepoActionResolver()
        self._repository_snapshot_service = repository_snapshot_service
        self._logger = logger

    def scan_root(self, root_path: Path, hard_refresh: bool = False) -> list[RepositoryState]:
        """
        Scannt einen Wurzelordner nach Git-Repositories und persistiert den aktuellen Zustand.

        Eingabeparameter:
        - root_path: Zu scannender Basisordner.
        - hard_refresh: Erzwingt Tiefenscans auch fuer unveraenderte Fingerprints.

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
            self._logger.event(
                "scan",
                "repo_index_root_begin",
                f"root_path={root_path} | hard_refresh={hard_refresh}",
            )
        indexed_repositories: list[RepositoryState] = []
        scan_timestamp = self._utc_now()
        scan_started_at = datetime.now(timezone.utc)
        scan_type = "local_hard_refresh" if hard_refresh else "local_normal_refresh"
        scan_run_id = self._state_repository.create_scan_run(scan_type, scan_timestamp)
        known_repositories = {
            repository.local_path: repository
            for repository in self._state_repository.fetch_repositories_by_root_path(str(root_path))
        }
        seen_local_paths: set[str] = set()
        changed_count = 0
        unchanged_count = 0
        error_count = 0
        for current_path, dir_names, _file_names in root_path.walk():
            if ".git" not in dir_names:
                continue

            repo_path = Path(current_path)
            seen_local_paths.add(str(repo_path))
            if self._logger is not None:
                self._logger.event("scan", "repo_index_repository_found", f"repo_path={repo_path}")
            existing_repository = known_repositories.get(str(repo_path))
            quick_fingerprint = self._repo_fingerprint_service.build_local_quick_fingerprint(repo_path)

            if (
                existing_repository is not None
                and not hard_refresh
                and existing_repository.scan_fingerprint == quick_fingerprint
                and not existing_repository.needs_rescan
                and not existing_repository.is_missing
            ):
                repository = self._state_repository.touch_repository_seen(
                    int(existing_repository.id or 0),
                    scan_timestamp,
                    quick_fingerprint,
                )
                if repository is not None:
                    indexed_repositories.append(repository)
                    unchanged_count += 1
                    self._state_repository.add_status_event(
                        RepoStatusEvent(
                            repo_id=int(repository.id or 0),
                            event_type="LOCAL_SCAN_SKIPPED_UNCHANGED",
                            severity="debug",
                            message=f"Leichter Fingerprint unveraendert fuer '{repository.name}'.",
                            created_at=scan_timestamp,
                        )
                    )
                dir_names[:] = []
                continue

            try:
                repository = self._inspect_repository(repo_path, scan_timestamp, quick_fingerprint)
            except Exception as error:  # noqa: BLE001
                error_count += 1
                if self._logger is not None:
                    self._logger.exception(f"Tiefenscan fehlgeschlagen fuer '{repo_path}': {error}")
                dir_names[:] = []
                continue

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

            if self._repo_structure_service is not None and repository.id is not None and repository.is_git_repo:
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
                self._run_structure_vault_scan(repository)
            elif self._repo_structure_service is not None and repository.id is not None and self._logger is not None:
                self._logger.event(
                    "scan",
                    "file_index_skipped",
                    f"name={repository.name} | repo_id={repository.id} | reason=repository_is_not_valid_git_repo",
                )

            repository.needs_rescan = False
            self._apply_resolved_actions(repository)
            repository.status_hash = self._repo_fingerprint_service.build_repository_status_hash(repository)
            repository = self._state_repository.upsert_repository(repository)
            if self._repository_snapshot_service is not None:
                self._repository_snapshot_service.capture_snapshot_for_repository(
                    repository,
                    trigger_type="local_scan",
                    force=False,
                )
            indexed_repositories.append(repository)
            changed_count += 1
            dir_names[:] = []

        missing_count = self._state_repository.mark_missing_repositories(str(root_path), seen_local_paths, scan_timestamp)
        if missing_count:
            changed_count += missing_count
        indexed_repositories.sort(key=lambda item: item.name.lower())
        finished_at = self._utc_now()
        duration_ms = int((datetime.now(timezone.utc) - scan_started_at).total_seconds() * 1000)
        self._state_repository.complete_scan_run(
            scan_run_id,
            finished_at,
            duration_ms,
            changed_count,
            unchanged_count,
            error_count,
        )
        if self._logger is not None:
            self._logger.event(
                "scan",
                "repo_index_root_complete",
                (
                    f"root_path={root_path} | repositories={len(indexed_repositories)} | "
                    f"changed={changed_count} | unchanged={unchanged_count} | missing={missing_count} | "
                    f"errors={error_count} | hard_refresh={hard_refresh}"
                ),
            )
        return indexed_repositories

    def index_repository(self, repo_path: Path, hard_refresh: bool = True) -> RepositoryState | None:
        """
        Aktualisiert gezielt genau ein lokales Repository im State-Layer.

        Eingabeparameter:
        - repo_path: Vollstaendiger Pfad des lokalen Repositories.
        - hard_refresh: Erzwingt einen Tiefenscan auch bei unveraendertem Fingerprint.

        Rueckgabewerte:
        - Aktualisierter `RepositoryState` oder `None`, wenn der Pfad nicht existiert.

        Moegliche Fehlerfaelle:
        - Defekte Repositories werden als `BROKEN_GIT` persistiert statt den Aufrufer scheitern zu lassen.

        Wichtige interne Logik:
        - Die Methode wird fuer direkte UI-Reparaturen genutzt, damit die Tabelle nicht auf
          einen spaeteren Komplettscan warten muss.
        """

        if not repo_path.exists():
            if self._logger is not None:
                self._logger.warning(f"Einzelne Repository-Aktualisierung uebersprungen, Pfad existiert nicht: {repo_path}")
            return None

        scan_timestamp = self._utc_now()
        quick_fingerprint = self._repo_fingerprint_service.build_local_quick_fingerprint(repo_path)
        existing_repository = self._state_repository.fetch_repository_by_local_path(str(repo_path))
        if (
            existing_repository is not None
            and not hard_refresh
            and existing_repository.scan_fingerprint == quick_fingerprint
            and not existing_repository.needs_rescan
            and not existing_repository.is_missing
        ):
            repository = self._state_repository.touch_repository_seen(
                int(existing_repository.id or 0),
                scan_timestamp,
                quick_fingerprint,
            )
            if repository is not None and self._logger is not None:
                self._logger.event(
                    "scan",
                    "repo_index_single_skipped_unchanged",
                    f"repo_path={repo_path} | status={repository.status}",
                )
            return repository

        repository = self._inspect_repository(repo_path, scan_timestamp, quick_fingerprint)
        repository = self._state_repository.upsert_repository(repository)
        self._state_repository.add_status_event(
            RepoStatusEvent(
                repo_id=int(repository.id or 0),
                event_type="LOCAL_SCAN_COMPLETED",
                message=f"Direkte Aktualisierung fuer '{repository.name}' abgeschlossen.",
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

        if self._repo_structure_service is not None and repository.id is not None and repository.is_git_repo:
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
            self._run_structure_vault_scan(repository)
        elif self._repo_structure_service is not None and repository.id is not None and self._logger is not None:
            self._logger.event(
                "scan",
                "file_index_skipped",
                f"name={repository.name} | repo_id={repository.id} | reason=repository_is_not_valid_git_repo",
            )

        repository.needs_rescan = False
        self._apply_resolved_actions(repository)
        repository.status_hash = self._repo_fingerprint_service.build_repository_status_hash(repository)
        repository = self._state_repository.upsert_repository(repository)
        if self._repository_snapshot_service is not None:
            self._repository_snapshot_service.capture_snapshot_for_repository(
                repository,
                trigger_type="local_scan",
                force=False,
            )
        if self._logger is not None:
            self._logger.event(
                "scan",
                "repo_index_single_complete",
                f"repo_path={repo_path} | status={repository.status}",
            )
        return repository

    def _run_structure_vault_scan(self, repository: RepositoryState) -> None:
        """
        Aktualisiert zusaetzlich den baumartigen Struktur-Vault fuer den RepoExplorer.

        Eingabeparameter:
        - repository: Bereits persistierter lokaler RepositoryState.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Strukturfehler werden nur protokolliert und blockieren den eigentlichen State-Scan nicht.

        Wichtige interne Logik:
        - Der Struktur-Vault ist eine Zusatzsicht fuer RepoViewer und Diagnose; ein Fehler dort
          darf deshalb den allgemeinen Refresh nicht unbrauchbar machen.
        """

        if self._repository_structure_scanner is None or repository.id is None or not repository.local_path:
            return
        try:
            stats = self._repository_structure_scanner.scan_repository(
                repo_identifier=repository.repo_key or f"local::{repository.local_path.lower()}",
                source_type="local",
                repo_path=Path(repository.local_path),
                include_commit_details=False,
            )
            self._state_repository.add_status_event(
                RepoStatusEvent(
                    repo_id=int(repository.id),
                    event_type="STRUCT_SCAN_DONE",
                    message=(
                        f"Struktur aktualisiert: {stats.total_count} Knoten "
                        f"(+{stats.inserted_count} / ~{stats.updated_count} / -{stats.deleted_count})."
                    ),
                    created_at=self._utc_now(),
                )
            )
        except Exception as error:  # noqa: BLE001
            if self._logger is not None:
                self._logger.exception(f"Struktur-Vault-Scan fehlgeschlagen fuer '{repository.local_path}': {error}")
            self._state_repository.add_status_event(
                RepoStatusEvent(
                    repo_id=int(repository.id),
                    event_type="STRUCT_SCAN_FAILED",
                    severity="error",
                    message=str(error),
                    created_at=self._utc_now(),
                )
            )

    def _apply_resolved_actions(self, repository: RepositoryState) -> None:
        """
        Uebernimmt empfohlene und verfuegbare Aktionen in den persistierten RepositoryState.

        Eingabeparameter:
        - repository: Bereits fachlich aufgebauter RepositoryState.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; die Ableitung bleibt rein im Speicher.

        Wichtige interne Logik:
        - Die persistierten Aktionsfelder ermoeglichen DB-first-Dashboards und spaetere
          Automatisierung, ohne bei jeder Anzeige erneut Regeln auswerten zu muessen.
        """

        resolved_actions = self._repo_action_resolver.resolve_repo_actions(repository)
        repository.recommended_action = self._repo_action_resolver.resolve_repo_primary_action(repository)
        repository.available_actions_json = json.dumps(
            [action.action_id for action in resolved_actions],
            ensure_ascii=True,
        )

    def fetch_cached_root(self, root_path: Path) -> list[RepositoryState]:
        """
        Liest bekannte persistierte Repository-Zustaende fuer einen Root direkt aus der State-Datenbank.

        Eingabeparameter:
        - root_path: Basisverzeichnis des lokalen Arbeitsbereichs.

        Rueckgabewerte:
        - Liste aller zu diesem Root passenden persistierten Repository-Zustaende.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Lesen der State-Datenbank.

        Wichtige interne Logik:
        - Die Methode dient der DB-first-Initialisierung in STUFE 2 und fuehrt keinen Scan aus.
        """

        return self._state_repository.fetch_repositories_by_root_path(str(root_path))

    def _inspect_repository(self, repo_path: Path, scan_timestamp: str, quick_fingerprint: str) -> RepositoryState:
        """
        Baut einen persistierbaren RepositoryState aus der Git-Inspektion auf.

        Eingabeparameter:
        - repo_path: Lokaler Pfad des gefundenen Repositories.
        - scan_timestamp: Zeitstempel des aktuellen Root-Scans.
        - quick_fingerprint: Bereits zuvor berechneter leichter Delta-Fingerprint.

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
                repo_key=f"local::{str(repo_path).lower()}",
                source_type="local",
                local_path=str(repo_path),
                visibility="unknown",
                is_archived=False,
                is_deleted=False,
                is_missing=False,
                last_seen_at=scan_timestamp,
                last_changed_at=scan_timestamp,
                last_checked_at=scan_timestamp,
                scan_fingerprint=quick_fingerprint,
                status_hash="",
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
                exists_local=True,
                exists_remote=None,
                git_initialized=False,
                remote_configured=False,
                has_uncommitted_changes=False,
                ahead_count=0,
                behind_count=0,
                is_diverged=False,
                auth_state="unknown",
                sync_state="BROKEN_GIT",
                health_state="broken_git",
                dirty_hint=False,
                needs_rescan=True,
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
            repo_key=f"local::{str(repo_path).lower()}",
            name=str(data.get("name") or repo_path.name),
            source_type="local",
            local_path=str(data.get("local_path") or repo_path),
            remote_url=str(data.get("remote_url") or ""),
            github_repo_id=0,
            default_branch=str(data.get("branch") or ""),
            visibility="unknown" if data.get("has_remote") else "not_published",
            is_archived=False,
            is_deleted=False,
            is_missing=False,
            last_seen_at=scan_timestamp,
            last_changed_at=scan_timestamp,
            last_checked_at=scan_timestamp,
            scan_fingerprint=quick_fingerprint,
            status_hash="",
            is_git_repo=is_git_repo,
            current_branch=str(data.get("branch") or ""),
            head_commit=str(data.get("head_commit") or ""),
            head_commit_date=str(data.get("head_commit_date") or ""),
            has_remote=bool(data.get("has_remote")),
            remote_name=str(data.get("remote_name") or ""),
            remote_host=str(data.get("remote_host") or ""),
            remote_owner=str(data.get("remote_owner") or ""),
            remote_repo_name=str(data.get("remote_repo_name") or ""),
            remote_exists_online=None,
            remote_visibility="unknown" if data.get("has_remote") else "not_published",
            exists_local=True,
            exists_remote=None,
            git_initialized=is_git_repo,
            remote_configured=bool(data.get("has_remote")),
            has_uncommitted_changes=bool(data.get("has_uncommitted_changes")),
            ahead_count=int(data.get("ahead_count") or 0),
            behind_count=int(data.get("behind_count") or 0),
            is_diverged=bool(data.get("is_diverged")),
            auth_state="unknown",
            sync_state=status,
            health_state=self._build_health_state(status),
            dirty_hint=bool(data.get("has_uncommitted_changes")),
            needs_rescan=True,
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

    def _build_health_state(self, status: str) -> str:
        """
        Leitet aus dem aktuellen Repository-Status einen kompakten Gesundheitswert ab.

        Eingabeparameter:
        - status: Fachlicher Gesamtstatus des Repositories.

        Rueckgabewerte:
        - Kurzer technischer Health-State fuer den persistierten Status-Layer.

        Moegliche Fehlerfaelle:
        - Unbekannte Stati fallen auf `unknown` zurueck.

        Wichtige interne Logik:
        - Die Abbildung bleibt bewusst zentral, damit spaetere UI-Resolver und Diagnosen
          nicht an mehreren Stellen eigene Statusinterpretationen pflegen.
        """

        mapping = {
            "REMOTE_OK": "healthy",
            "LOCAL_ONLY": "local_only",
            "REMOTE_MISSING": "missing_remote",
            "REMOTE_UNREACHABLE": "remote_unreachable",
            "BROKEN_GIT": "broken_git",
            "NOT_INITIALIZED": "not_initialized",
        }
        return mapping.get(status, "unknown")

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
