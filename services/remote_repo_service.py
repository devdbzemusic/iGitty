"""DB-first-Service fuer GitHub-Remote-Repositories und deren SQLite-Cache."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from time import perf_counter

from core.logger import AppLogger
from db.state_repository import StateRepository
from models.repo_models import RateLimitInfo, RemoteRepo
from models.state_models import RepositoryState
from services.github_service import GitHubService
from services.repo_action_resolver import RepoActionResolver
from services.repo_fingerprint_service import RepoFingerprintService


class RemoteRepoService:
    """Kapselt DB-first-Lesen und Delta-Synchronisierung fuer Remote-Repositories."""

    def __init__(
        self,
        github_service: GitHubService,
        state_repository: StateRepository,
        logger: AppLogger | None = None,
        repo_action_resolver: RepoActionResolver | None = None,
        repo_fingerprint_service: RepoFingerprintService | None = None,
    ) -> None:
        """
        Initialisiert den Service mit GitHub-, State- und Resolver-Abhaengigkeiten.

        Eingabeparameter:
        - github_service: Service fuer authentifizierte GitHub-API-Aufrufe.
        - state_repository: SQLite-Zugriff auf den persistierten State-Store.
        - logger: Optionaler Anwendungslogger fuer Diagnose und Delta-Metriken.
        - repo_action_resolver: Zentrale Regelinstanz fuer Remote-Kontextaktionen.
        - repo_fingerprint_service: Fingerprint-Helfer fuer Delta-Vergleiche.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Service haelt die GitHub-API strikt von der UI fern und sorgt dafuer,
          dass Startansicht und Background-Refresh denselben SQLite-State benutzen.
        """

        self._github_service = github_service
        self._state_repository = state_repository
        self._logger = logger
        self._repo_action_resolver = repo_action_resolver or RepoActionResolver()
        self._repo_fingerprint_service = repo_fingerprint_service or RepoFingerprintService()

    def load_cached_repositories(self) -> list[RemoteRepo]:
        """
        Laedt bekannte Remote-Repositories sofort aus SQLite fuer den App-Start.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Liste der aus der State-DB rekonstruierten Remote-View-Modelle.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler werden an den Aufrufer weitergereicht.

        Wichtige interne Logik:
        - Die Methode fuehrt bewusst keinen Netzwerkzugriff aus und bildet damit die
          DB-first-Einstiegsschicht fuer STUFE 2.
        """

        repository_states = self._state_repository.fetch_remote_repositories()
        mapped_repositories = [self._map_state_to_remote_repo(repository) for repository in repository_states]
        mapped_repositories.sort(key=lambda item: item.full_name.lower() or item.name.lower())
        return mapped_repositories

    def sync_repositories(self) -> tuple[list[RemoteRepo], RateLimitInfo]:
        """
        Synchronisiert Remote-Repositories mit GitHub und aktualisiert nur echte Delta-Aenderungen.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Tupel aus aktueller Cache-Sicht der Remote-Repositories und GitHub-Rate-Limit-Infos.

        Moegliche Fehlerfaelle:
        - GitHub-API- oder SQLite-Fehler werden an den Worker/Controller weitergereicht.

        Wichtige interne Logik:
        - Unveraenderte Datensaetze werden nur getoucht.
        - Veraenderte oder neue Datensaetze werden gezielt per Upsert geschrieben.
        - Fehlende Remote-Repositories werden als Missing/Deleted markiert, damit die UI
          spaeter gezielte `remove`-Events statt eines Voll-Rebuilds ausloesen kann.
        """

        started_at = self._utc_now()
        started_at_perf = perf_counter()
        run_id = self._state_repository.create_scan_run("remote_refresh", started_at)
        changed_count = 0
        unchanged_count = 0
        error_count = 0
        try:
            if self._logger is not None:
                self._logger.event("scan", "remote_sync_begin", "source=github_api")
            repositories, rate_limit = self._github_service.fetch_remote_repositories()
            previous_states = {
                repository.github_repo_id: repository
                for repository in self._state_repository.fetch_remote_repositories()
                if repository.github_repo_id > 0
            }
            seen_repo_ids: set[int] = set()

            for repository in repositories:
                seen_repo_ids.add(repository.repo_id)
                repository_state = self._map_remote_repo_to_state(repository, started_at)
                previous_state = previous_states.get(repository.repo_id)
                if self._is_remote_repository_unchanged(previous_state, repository_state):
                    if previous_state is not None and previous_state.id is not None:
                        self._state_repository.touch_remote_repository_seen(
                            previous_state.id,
                            started_at,
                            repository_state.scan_fingerprint,
                        )
                    unchanged_count += 1
                    continue
                self._state_repository.upsert_repository(repository_state)
                changed_count += 1

            changed_count += self._state_repository.mark_missing_remote_repositories(seen_repo_ids, started_at)
            finished_at = self._utc_now()
            duration_ms = int((perf_counter() - started_at_perf) * 1000)
            self._state_repository.complete_scan_run(
                run_id=run_id,
                finished_at=finished_at,
                duration_ms=duration_ms,
                changed_count=changed_count,
                unchanged_count=unchanged_count,
                error_count=error_count,
            )
            cached_repositories = self.load_cached_repositories()
            if self._logger is not None:
                self._logger.event(
                    "state",
                    "remote_sync_complete",
                    (
                        f"loaded={len(repositories)} | changed={changed_count} | "
                        f"unchanged={unchanged_count} | cached={len(cached_repositories)}"
                    ),
                    level=20,
                )
            return cached_repositories, rate_limit
        except Exception:
            error_count += 1
            finished_at = self._utc_now()
            duration_ms = int((perf_counter() - started_at_perf) * 1000)
            self._state_repository.complete_scan_run(
                run_id=run_id,
                finished_at=finished_at,
                duration_ms=duration_ms,
                changed_count=changed_count,
                unchanged_count=unchanged_count,
                error_count=error_count,
            )
            raise

    def upsert_cached_repository(self, repository: RemoteRepo) -> RemoteRepo:
        """
        Schreibt genau ein aktualisiertes Remote-Repository in den SQLite-Cache zurueck.

        Eingabeparameter:
        - repository: Bereits von GitHub bestaetigtes Remote-Repository.

        Rueckgabewerte:
        - Das aus dem State-Store rekonstruierte Remote-Repository fuer konsistente UI-Nutzung.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Upsert.

        Wichtige interne Logik:
        - Die Methode wird nach einzelnen Remote-Aktionen wie Sichtbarkeitsaenderungen
          verwendet, damit App-Neustarts sofort den neuen Zustand zeigen.
        """

        state = self._map_remote_repo_to_state(repository, self._utc_now())
        stored_state = self._state_repository.upsert_repository(state)
        return self._map_state_to_remote_repo(stored_state)

    def _map_remote_repo_to_state(self, repository: RemoteRepo, scan_timestamp: str) -> RepositoryState:
        """
        Wandelt ein GitHub-Remote-Modell in den persistierbaren RepositoryState um.

        Eingabeparameter:
        - repository: Remote-Repository aus API oder Einzelaktion.
        - scan_timestamp: Zeitstempel des aktuellen Refresh- oder Update-Laufs.

        Rueckgabewerte:
        - Vollstaendig vorbereiteter RepositoryState fuer SQLite.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Felder werden mit stabilen Defaults behandelt.

        Wichtige interne Logik:
        - Das Mapping sammelt alle fuer Remote-UI und spaeteren RepoViewer relevanten
          Metadaten in einem konsistenten State-Modell.
        """

        repository_state = RepositoryState(
            repo_key=f"remote::{repository.repo_id}",
            name=repository.name,
            source_type="remote",
            local_path="",
            remote_url=repository.clone_url,
            github_repo_id=repository.repo_id,
            default_branch=repository.default_branch,
            visibility=repository.visibility,
            is_archived=repository.archived,
            is_deleted=False,
            is_missing=False,
            last_seen_at=scan_timestamp,
            last_changed_at=scan_timestamp,
            last_checked_at=scan_timestamp,
            scan_fingerprint="",
            status_hash="",
            is_git_repo=False,
            current_branch=repository.default_branch,
            head_commit="",
            head_commit_date="",
            has_remote=False,
            remote_name="origin",
            remote_host="github.com",
            remote_owner=repository.owner,
            remote_repo_name=repository.name,
            language=repository.language or "-",
            description=repository.description or "",
            topics_json=json.dumps(repository.topics or [], ensure_ascii=True),
            contributors_count=int(repository.contributors_count or 0),
            contributors_summary=repository.contributors_summary or "-",
            created_at=repository.created_at,
            updated_at=repository.updated_at,
            pushed_at=repository.pushed_at,
            size_kb=int(repository.size or 0),
            is_fork=repository.fork,
            remote_exists_online=1,
            remote_visibility=repository.visibility,
            exists_local=False,
            exists_remote=True,
            git_initialized=False,
            remote_configured=False,
            has_uncommitted_changes=False,
            ahead_count=0,
            behind_count=0,
            is_diverged=False,
            auth_state="authenticated" if self._github_service.last_authenticated_login else "unknown",
            sync_state="REMOTE_ONLY",
            health_state="healthy",
            dirty_hint=False,
            needs_rescan=False,
            status="REMOTE_ONLY",
            last_local_scan_at="",
            last_remote_check_at=scan_timestamp,
        )
        repository_state.scan_fingerprint = self._repo_fingerprint_service.build_remote_fingerprint(repository)
        repository_state.status_hash = self._repo_fingerprint_service.build_repository_status_hash(repository_state)
        return repository_state

    def _map_state_to_remote_repo(self, repository: RepositoryState) -> RemoteRepo:
        """
        Wandelt einen persistierten Remote-State in das UI-nahe RemoteRepo-Modell um.

        Eingabeparameter:
        - repository: Persistierter RepositoryState aus SQLite.

        Rueckgabewerte:
        - Vollstaendig gemapptes RemoteRepo fuer Tabelle und Kontextaktionen.

        Moegliche Fehlerfaelle:
        - Ungueltiges `topics_json` wird defensiv als leere Liste behandelt.

        Wichtige interne Logik:
        - Die Methode rekonstruiert die bestehende Remote-UI aus dem zentralen State,
          damit die Darstellung beim App-Start ohne API-Wartezeit verfuegbar ist.
        """

        try:
            topics = json.loads(repository.topics_json or "[]")
        except json.JSONDecodeError:
            topics = []

        mapped_repository = RemoteRepo(
            repo_id=repository.github_repo_id,
            name=repository.name,
            full_name=f"{repository.remote_owner}/{repository.name}" if repository.remote_owner else repository.name,
            owner=repository.remote_owner,
            visibility=repository.visibility,
            default_branch=repository.default_branch,
            language=repository.language or "-",
            archived=repository.is_archived,
            fork=repository.is_fork,
            clone_url=repository.remote_url,
            ssh_url=f"git@github.com:{repository.remote_owner}/{repository.name}.git"
            if repository.remote_owner and repository.name
            else "",
            html_url=f"https://github.com/{repository.remote_owner}/{repository.name}"
            if repository.remote_owner and repository.name
            else "",
            description=repository.description,
            topics=[str(topic) for topic in topics if isinstance(topic, str)],
            contributors_count=repository.contributors_count,
            contributors_summary=repository.contributors_summary or "-",
            created_at=repository.created_at,
            updated_at=repository.updated_at,
            pushed_at=repository.pushed_at,
            size=repository.size_kb,
            state_status_hash=repository.status_hash,
        )
        mapped_repository.available_actions = [
            action.action_id
            for action in self._repo_action_resolver.resolve_remote_actions(mapped_repository)
        ]
        return mapped_repository

    def _is_remote_repository_unchanged(
        self,
        previous_state: RepositoryState | None,
        current_state: RepositoryState,
    ) -> bool:
        """
        Prueft, ob sich ein Remote-Repository fachlich gegenueber dem Cache nicht veraendert hat.

        Eingabeparameter:
        - previous_state: Vorheriger persistierter Zustand oder `None` fuer neue Eintraege.
        - current_state: Neu vorbereiteter Zustand aus der GitHub-API.

        Rueckgabewerte:
        - `True`, wenn nur Sichtungszeitstempel aktualisiert werden muessen.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Neben Fingerprint und Status-Hash wird auch der Missing-Marker beruecksichtigt,
          damit zuvor geloeschte Eintraege beim Wiederauftauchen sauber reaktiviert werden.
        """

        if previous_state is None:
            return False
        return (
            previous_state.scan_fingerprint == current_state.scan_fingerprint
            and previous_state.status_hash == current_state.status_hash
            and not previous_state.is_missing
        )

    def _utc_now(self) -> str:
        """
        Erzeugt einen einheitlichen UTC-Zeitstempel fuer Refresh- und Cache-Updates.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - ISO-8601-Zeitstempel in UTC.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Einheitliche Zeitstempel vereinfachen Delta-Vergleiche, Debugging und Tests.
        """

        return datetime.now(timezone.utc).isoformat()
