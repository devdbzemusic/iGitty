"""Zentrale Orchestrierung fuer lokale und entfernte Repository-Synchronisation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.logger import AppLogger
from db.state_repository import StateRepository
from models.state_models import RepoLink, RepoStatusEvent, RepositorySyncSnapshot, RepositoryState
from services.remote_repo_service import RemoteRepoService
from services.repo_fingerprint_service import RepoFingerprintService
from services.repo_index_service import RepoIndexService
from services.repository_pairing_service import RepositoryPairingService
from services.repository_sync_analyzer import RepositoryPairAnalysis, RepositorySyncAnalyzer


class RepositorySyncOrchestrator:
    """Koordiniert lokale Delta-Scans, Remote-Sync, Pairing und Sync-Diagnose zentral."""

    def __init__(
        self,
        repo_index_service: RepoIndexService,
        remote_repo_service: RemoteRepoService,
        state_repository: StateRepository | None = None,
        pairing_service: RepositoryPairingService | None = None,
        sync_analyzer: RepositorySyncAnalyzer | None = None,
        repo_fingerprint_service: RepoFingerprintService | None = None,
        logger: AppLogger | None = None,
    ) -> None:
        """
        Initialisiert die Orchestrierung ueber Local-, Remote-, Pairing- und Sync-Analyse.

        Eingabeparameter:
        - repo_index_service: Delta-faehiger Local-State-Indexer.
        - remote_repo_service: DB-first-Service fuer GitHub-Repositories.
        - state_repository: Persistenter State-Store fuer gezielte Nachbearbeitung.
        - pairing_service: Zentrale Verknuepfungslogik fuer lokale und entfernte Repositories.
        - sync_analyzer: Zustandsmaschine fuer technische Sync-Entscheidungen.
        - repo_fingerprint_service: Optionaler Helfer fuer Delta-Hashes ueber Zustandsaenderungen.
        - logger: Optionaler zentraler Logger fuer Diagnose- und Ablaufmeldungen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Orchestrator kapselt die abteilungsuebergreifende Reihenfolge, ohne den
          bestehenden Controllern ihre spezialisierten Verantwortlichkeiten zu nehmen.
        """

        self._repo_index_service = repo_index_service
        self._remote_repo_service = remote_repo_service
        self._state_repository = state_repository
        self._pairing_service = pairing_service
        self._sync_analyzer = sync_analyzer
        self._repo_fingerprint_service = repo_fingerprint_service or RepoFingerprintService()
        self._logger = logger

    def refresh_local(self, root_path: Path, hard_refresh: bool = False) -> list[RepositoryState]:
        """
        Fuehrt einen lokalen Delta- oder Hard-Refresh aus und berechnet danach Pairing und Sync-Zustaende neu.

        Eingabeparameter:
        - root_path: Lokaler Wurzelpfad fuer die Repository-Erkennung.
        - hard_refresh: Erzwingt einen Tiefenscan trotz unveraenderter Fingerprints.

        Rueckgabewerte:
        - Liste der aktualisierten lokalen Repository-Zustaende nach Analyse und Persistenz.

        Moegliche Fehlerfaelle:
        - Dateisystem-, Git- oder SQLite-Fehler werden an den Aufrufer weitergereicht.

        Wichtige interne Logik:
        - Nach dem eigentlichen Local-Scan wird bewusst noch einmal der globale Pairing-
          und Sync-Layer ueber den persistierten State gerechnet, damit die UI keine
          veralteten Beziehungen zwischen lokal und remote anzeigt.
        """

        if self._logger is not None:
            self._logger.event(
                "sync",
                "orchestrator_local_refresh_begin",
                f"root_path={root_path} | hard_refresh={hard_refresh}",
                level=20,
            )
        repositories = self._repo_index_service.scan_root(root_path, hard_refresh=hard_refresh)
        if self._state_repository is not None:
            self.reconcile_cached_states()
            repositories = self._state_repository.fetch_repositories_by_root_path(str(root_path))
        if self._logger is not None:
            self._logger.event(
                "sync",
                "orchestrator_local_refresh_complete",
                f"root_path={root_path} | repositories={len(repositories)} | hard_refresh={hard_refresh}",
                level=20,
            )
        return repositories

    def refresh_remote(self):
        """
        Fuehrt einen Remote-Refresh ueber GitHub und den SQLite-Cache aus und verknuepft danach beide Seiten neu.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Tupel aus aktueller Remote-Liste und Rate-Limit-Information.

        Moegliche Fehlerfaelle:
        - GitHub- oder SQLite-Fehler werden an den Aufrufer weitergereicht.

        Wichtige interne Logik:
        - Nach der GitHub-Synchronisierung laeuft dieselbe Pairing- und Sync-Analyse wie
          nach lokalen Scans, damit Remote-Only- und Pair-Zustaende konsistent bleiben.
        """

        if self._logger is not None:
            self._logger.event("sync", "orchestrator_remote_refresh_begin", level=20)
        repositories, rate_limit = self._remote_repo_service.sync_repositories()
        if self._state_repository is not None:
            self.reconcile_cached_states()
            repositories = self._remote_repo_service.load_cached_repositories()
        if self._logger is not None:
            self._logger.event(
                "sync",
                "orchestrator_remote_refresh_complete",
                f"repositories={len(repositories)} | remaining={rate_limit.remaining}/{rate_limit.limit}",
                level=20,
            )
        return repositories, rate_limit

    def refresh_all(self, root_path: Path, hard_refresh: bool = False) -> RepositorySyncSnapshot:
        """
        Fuehrt einen kombinierten lokalen und entfernten Synchronisationslauf aus.

        Eingabeparameter:
        - root_path: Lokaler Root-Pfad fuer den Repository-Scan.
        - hard_refresh: Erzwingt fuer den lokalen Teil einen Vollscan.

        Rueckgabewerte:
        - RepositorySyncSnapshot mit beiden Seiten des aktuellen Gesamtlaufs.

        Moegliche Fehlerfaelle:
        - Einzelne Servicefehler werden nicht geschluckt, damit Diagnose und UI klar reagieren koennen.

        Wichtige interne Logik:
        - Die Reihenfolge bleibt lokal dann remote, anschliessend wird aber einmal zentral
          ueber alle bekannten Repositories gepaart und synchronisiert.
        """

        if self._logger is not None:
            self._logger.event(
                "sync",
                "orchestrator_refresh_all_begin",
                f"root_path={root_path} | hard_refresh={hard_refresh}",
                level=20,
            )
        local_repositories = self.refresh_local(root_path, hard_refresh=hard_refresh)
        remote_repositories, rate_limit = self.refresh_remote()
        snapshot = RepositorySyncSnapshot(
            local_repositories=local_repositories,
            remote_repositories=remote_repositories,
            rate_limit=rate_limit,
            hard_refresh=hard_refresh,
        )
        if self._logger is not None:
            self._logger.event(
                "sync",
                "orchestrator_refresh_all_complete",
                (
                    f"local={len(snapshot.local_repositories)} | remote={len(snapshot.remote_repositories)} | "
                    f"hard_refresh={snapshot.hard_refresh}"
                ),
                level=20,
            )
        return snapshot

    def refresh_repository(
        self,
        *,
        local_path: str = "",
        github_repo_id: int = 0,
        hard_refresh: bool = True,
    ) -> tuple[RepositoryState | None, RepositoryState | None]:
        """
        Aktualisiert gezielt ein einzelnes Repository oder Repository-Paar.

        Eingabeparameter:
        - local_path: Optionaler lokaler Pfad fuer einen gezielten Local-Refresh.
        - github_repo_id: Optionale GitHub-Repository-ID fuer einen gezielten Remote-Bezug.
        - hard_refresh: Erzwingt beim lokalen Teil einen Tiefenscan.

        Rueckgabewerte:
        - Tupel aus lokalem und entferntem Repository-Zustand nach der Analyse.

        Moegliche Fehlerfaelle:
        - Git-, GitHub- oder SQLite-Fehler werden an den Aufrufer weitergereicht.

        Wichtige interne Logik:
        - Fuer lokale Pfade nutzt die Methode den bestehenden Einzel-Indexer.
        - Fuer reine Remote-IDs wird der bestehende Cache neu gepaart und analysiert,
          ohne unkontrollierte Schreibaktionen auszufuehren.
        """

        if local_path:
            self._repo_index_service.index_repository(Path(local_path), hard_refresh=hard_refresh)
        elif github_repo_id > 0:
            self._remote_repo_service.sync_repositories()
        self.reconcile_cached_states()
        if self._state_repository is None:
            return None, None
        local_repository = self._state_repository.fetch_repository_by_local_path(local_path) if local_path else None
        remote_repository = (
            self._state_repository.fetch_repository_by_github_repo_id(github_repo_id)
            if github_repo_id > 0
            else (
                self._state_repository.fetch_repository_by_github_repo_id(local_repository.github_repo_id)
                if local_repository is not None and local_repository.github_repo_id > 0
                else None
            )
        )
        return local_repository, remote_repository

    def reconcile_cached_states(self) -> int:
        """
        Fuehrt Pairing und Sync-Analyse ueber den aktuellen persistierten Gesamtzustand aus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Anzahl der fachlich veraenderten Repository-Zustaende.

        Moegliche Fehlerfaelle:
        - SQLite- oder Git-Lesefehler werden an den Aufrufer weitergereicht.

        Wichtige interne Logik:
        - Die Methode arbeitet ausschliesslich auf dem State-Layer plus lesenden Git-
          Abfragen und ist damit der zentrale Synchronisationspunkt zwischen Local- und Remote-Seite.
        """

        if self._state_repository is None or self._pairing_service is None or self._sync_analyzer is None:
            return 0

        analysis_timestamp = self._utc_now()
        local_repositories = self._state_repository.fetch_local_repositories()
        remote_repositories = self._state_repository.fetch_remote_repositories()
        repo_links = self._pairing_service.resolve_links(
            local_repositories=local_repositories,
            remote_repositories=remote_repositories,
            verified_at=analysis_timestamp,
        )
        active_links_by_local_id = {
            repo_link.state_repo_id: repo_link
            for repo_link in repo_links
            if repo_link.is_active
        }
        remote_by_id = {
            repository.github_repo_id: repository
            for repository in remote_repositories
            if repository.github_repo_id > 0
        }
        processed_remote_ids: set[int] = set()
        changed_count = 0

        for local_repository in local_repositories:
            repo_link = active_links_by_local_id.get(int(local_repository.id or 0))
            remote_repository = (
                remote_by_id.get(repo_link.github_repo_id)
                if repo_link is not None and repo_link.github_repo_id > 0
                else None
            )
            analysis = self._sync_analyzer.analyze_repository_pair(local_repository, remote_repository, repo_link)
            changed_count += self._persist_analysis(analysis, analysis_timestamp)
            if remote_repository is not None:
                processed_remote_ids.add(remote_repository.github_repo_id)

        for remote_repository in remote_repositories:
            if remote_repository.github_repo_id in processed_remote_ids:
                continue
            analysis = self._sync_analyzer.analyze_repository_pair(None, remote_repository, None)
            changed_count += self._persist_analysis(analysis, analysis_timestamp)

        if self._logger is not None:
            self._logger.event(
                "sync",
                "orchestrator_reconcile_complete",
                (
                    f"locals={len(local_repositories)} | remotes={len(remote_repositories)} | "
                    f"links={len(repo_links)} | changed={changed_count}"
                ),
                level=20,
            )
        return changed_count

    def _persist_analysis(self, analysis: RepositoryPairAnalysis, analysis_timestamp: str) -> int:
        """
        Persistiert die Ergebnisse einer einzelnen Pair-Analyse und erzeugt Statusereignisse bei Delta-Aenderungen.

        Eingabeparameter:
        - analysis: Ergebnisobjekt aus dem Sync-Analyzer.
        - analysis_timestamp: Zeitstempel des aktuellen Analyse-Laufs.

        Rueckgabewerte:
        - Anzahl der fachlich veraenderten persistierten Repository-Zustaende.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Upsert oder Event-Schreiben.

        Wichtige interne Logik:
        - Nur echte fachliche Aenderungen auf Basis des Status-Hashes zaehlen als Delta,
          damit spaetere UI-Refreshes und Diagnoseanzeigen schlank bleiben.
        """

        changed_count = 0
        for repository in (analysis.local_repository, analysis.remote_repository):
            if repository is None:
                continue
            previous_status_hash = repository.status_hash
            repository.last_checked_at = analysis_timestamp
            repository.status_hash = self._repo_fingerprint_service.build_repository_status_hash(repository)
            stored_repository = self._state_repository.upsert_repository(repository)
            if previous_status_hash != stored_repository.status_hash:
                changed_count += 1
            self._state_repository.add_status_event(
                RepoStatusEvent(
                    repo_id=int(stored_repository.id or 0),
                    event_type="SYNC_STATE_ANALYZED",
                    severity="info" if previous_status_hash != stored_repository.status_hash else "debug",
                    message=analysis.analysis_reason,
                    payload_json=(
                        f'{{"sync_state":"{analysis.sync_state}","health_state":"{analysis.health_state}"}}'
                    ),
                    created_at=analysis_timestamp,
                )
            )
        return changed_count

    def _utc_now(self) -> str:
        """
        Liefert einen konsistenten UTC-Zeitstempel fuer Orchestrierungslaeufe.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - ISO-8601-Zeitstempel in UTC.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Einheitliche Zeitstempel erleichtern Logging, Tests und Delta-Auswertungen.
        """

        return datetime.now(timezone.utc).isoformat()
