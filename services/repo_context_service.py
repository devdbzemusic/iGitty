"""Service zum Zusammenfuehren eines sauberen Repo-Kontexts fuer Teil 2."""

from __future__ import annotations

from models.evolution_models import RepositoryEvolutionSummary, RepositoryTimelineEntry, SnapshotDiffResult
from models.job_models import ActionSummary
from models.repo_models import LocalRepo, RemoteRepo
from models.view_models import RepoContext
from db.job_log_repository import JobLogRepository
from db.state_repository import StateRepository
from services.repo_action_resolver import RepoActionResolver
from services.repository_evolution_analyzer import RepositoryEvolutionAnalyzer
from services.repository_snapshot_service import RepositorySnapshotService
from services.repo_struct_service import RepoStructService


class RepoContextService:
    """Erzeugt RepoContext-Modelle aus Remote-, Local-, History- und Vault-Daten."""

    def __init__(
        self,
        job_log_repository: JobLogRepository,
        repo_struct_service: RepoStructService,
        state_repository: StateRepository | None = None,
        repo_action_resolver: RepoActionResolver | None = None,
        repository_snapshot_service: RepositorySnapshotService | None = None,
        repository_evolution_analyzer: RepositoryEvolutionAnalyzer | None = None,
    ) -> None:
        """
        Initialisiert den Service mit Zugriff auf Historie und Struktur-Vault.

        Eingabeparameter:
        - job_log_repository: Repository fuer Aktions- und Clone-Historie.
        - repo_struct_service: Service fuer Struktur-Zusammenfassungen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Initialisierung.

        Wichtige interne Logik:
        - Der Service bleibt zustandslos und erhaelt Repo-Listen pro Aufruf.
        """

        self._job_log_repository = job_log_repository
        self._repo_struct_service = repo_struct_service
        self._state_repository = state_repository
        self._repo_action_resolver = repo_action_resolver or RepoActionResolver()
        self._repository_snapshot_service = repository_snapshot_service
        self._repository_evolution_analyzer = repository_evolution_analyzer

    def build_context(
        self,
        repo_ref,
        source_type: str,
        remote_repositories: list[RemoteRepo],
        local_repositories: list[LocalRepo],
    ) -> RepoContext:
        """
        Baut einen RepoContext fuer ein angefordertes Remote- oder Local-Repository.

        Eingabeparameter:
        - repo_ref: Stabile Referenz mit moeglichen Identitaetsfeldern.
        - source_type: `remote` oder `local`.
        - remote_repositories: Aktuell bekannte Remote-Repositories.
        - local_repositories: Aktuell bekannte lokale Repositories.

        Rueckgabewerte:
        - Vollstaendig bestmoeglich gefuellter RepoContext.

        Moegliche Fehlerfaelle:
        - Fehlende Gegenstuecke in Remote- oder Local-Liste werden defensiv behandelt.

        Wichtige interne Logik:
        - Bevorzugt `remote_repo_id`, danach `repo_full_name`, danach `remote_url`, danach `local_path`.
        """

        remote_repo = self._find_remote_repo(repo_ref, remote_repositories)
        local_repo = self._find_local_repo(repo_ref, local_repositories)

        if source_type == "remote" and remote_repo is not None and local_repo is None:
            local_repo = self._match_local_to_remote(remote_repo, local_repositories)
        if source_type == "local" and local_repo is not None and remote_repo is None:
            remote_repo = self._match_remote_to_local(local_repo, remote_repositories)

        state_repository = self._resolve_state_repository(repo_ref, remote_repo, local_repo)

        repo_name = (
            local_repo.name if local_repo is not None else remote_repo.name if remote_repo is not None else str(repo_ref.get("repo_name", ""))
        )
        remote_url = (
            local_repo.remote_url if local_repo is not None and local_repo.remote_url else remote_repo.html_url if remote_repo is not None else ""
        )
        clone_url = remote_repo.clone_url if remote_repo is not None else remote_url
        local_path = local_repo.full_path if local_repo is not None else ""
        repo_id = self._build_repo_id(repo_ref, remote_repo, local_repo)
        state_repo_id = int(state_repository.id or 0) if state_repository is not None and state_repository.id is not None else None
        struct_source_type = "local" if local_path else "remote_clone"
        struct_identifier = self._repo_struct_service.build_repo_identifier(
            local_path=local_path,
            remote_repo_id=(remote_repo.repo_id if remote_repo is not None else 0),
            remote_url=clone_url,
            repo_name=repo_name,
        )
        has_struct_vault_data, struct_item_count, last_struct_scan_timestamp = self._repo_struct_service.fetch_repo_summary(
            repo_identifier=struct_identifier,
            source_type=struct_source_type,
        )
        tree_items = self._repo_struct_service.fetch_repo_items(struct_identifier, struct_source_type) if has_struct_vault_data else []
        last_action = self._job_log_repository.fetch_last_general_action(
            repo_name=repo_name,
            remote_url=clone_url,
            local_path=local_path,
        )
        history_entries = self._build_history_entries(repo_name, clone_url, local_path)
        status_events = self._build_status_events(state_repository)
        diagnostic_events = [
            f"{event.created_at} | {event.severity.upper()} | {event.event_type} | {event.message or '-'}"
            for event in status_events
        ]
        recent_scan_runs = self._build_recent_scan_runs(local_path, clone_url)
        snapshots = self._build_snapshots(state_repository)
        evolution_summary, snapshot_diffs = self._build_evolution(snapshots)
        timeline_entries = self._build_timeline_entries(
            snapshots=snapshots,
            history_entries=history_entries,
            status_events=status_events,
            recent_scan_runs=recent_scan_runs,
        )
        recommended_action = "-"
        available_actions: list[str] = []
        repository_status = local_repo.remote_status if local_repo is not None else "REMOTE_ONLY" if remote_repo is not None else "unknown"
        health_state = local_repo.health_state if local_repo is not None else "healthy" if remote_repo is not None else "unknown"
        sync_state = local_repo.sync_state if local_repo is not None else "REMOTE_ONLY" if remote_repo is not None else "unknown"
        last_scan_at = None
        last_remote_check_at = None
        scan_fingerprint = ""
        status_hash = ""
        needs_rescan = False
        dirty_hint = False
        if state_repository is not None:
            recommended_action = self._repo_action_resolver.resolve_repo_primary_action(state_repository)
            available_actions = [action.action_id for action in self._repo_action_resolver.resolve_repo_actions(state_repository)]
            repository_status = state_repository.status or repository_status
            health_state = state_repository.health_state or health_state
            sync_state = state_repository.sync_state or sync_state
            last_scan_at = state_repository.last_local_scan_at or None
            last_remote_check_at = state_repository.last_remote_check_at or None
            scan_fingerprint = state_repository.scan_fingerprint
            status_hash = state_repository.status_hash
            needs_rescan = state_repository.needs_rescan
            dirty_hint = state_repository.dirty_hint

        return RepoContext(
            source_type=source_type,
            repo_id=repo_id,
            state_repo_id=state_repo_id,
            remote_repo_id=(
                local_repo.remote_repo_id if local_repo is not None and local_repo.remote_repo_id else remote_repo.repo_id if remote_repo is not None else None
            ),
            repo_name=repo_name,
            repo_full_name=remote_repo.full_name if remote_repo is not None else "",
            owner=remote_repo.owner if remote_repo is not None else "",
            description=remote_repo.description if remote_repo is not None else "",
            local_path=local_path or None,
            remote_url=remote_url or None,
            clone_url=clone_url or None,
            current_branch=local_repo.current_branch if local_repo is not None else None,
            default_branch=remote_repo.default_branch if remote_repo is not None else None,
            remote_visibility=(
                local_repo.remote_visibility if local_repo is not None and local_repo.remote_visibility else remote_repo.visibility if remote_repo is not None else "unknown"
            ),
            publish_as_public=local_repo.publish_as_public if local_repo is not None else False,
            archived=remote_repo.archived if remote_repo is not None else False,
            fork=remote_repo.fork if remote_repo is not None else False,
            has_remote=local_repo.has_remote if local_repo is not None else remote_repo is not None,
            has_local_clone=local_repo is not None,
            languages=self._build_languages(remote_repo, local_repo),
            contributors_summary=remote_repo.contributors_summary if remote_repo is not None else "-",
            last_action_type=last_action.action_type if last_action is not None else None,
            last_action_status=last_action.status if last_action is not None else None,
            last_action_timestamp=last_action.timestamp if last_action is not None else None,
            repository_status=repository_status,
            health_state=health_state,
            sync_state=sync_state,
            recommended_action=recommended_action,
            available_actions=available_actions,
            last_scan_at=last_scan_at,
            last_remote_check_at=last_remote_check_at,
            scan_fingerprint=scan_fingerprint,
            status_hash=status_hash,
            needs_rescan=needs_rescan,
            dirty_hint=dirty_hint,
            has_struct_vault_data=has_struct_vault_data,
            struct_item_count=struct_item_count,
            last_struct_scan_timestamp=last_struct_scan_timestamp,
            diagnostic_events=diagnostic_events,
            history_entries=history_entries,
            status_events=status_events,
            recent_scan_runs=recent_scan_runs,
            tree_items=tree_items,
            snapshots=snapshots,
            snapshot_diffs=snapshot_diffs,
            timeline_entries=timeline_entries,
            evolution_summary=evolution_summary,
        )

    def _resolve_state_repository(
        self,
        repo_ref,
        remote_repo: RemoteRepo | None,
        local_repo: LocalRepo | None,
    ):
        """
        Liest den passendsten persistierten RepositoryState fuer den aktuellen Kontext.

        Eingabeparameter:
        - repo_ref: Urspruengliche UI-Referenz des Repositories.
        - remote_repo: Bereits gefundenes Remote-Repository oder `None`.
        - local_repo: Bereits gefundenes Local-Repository oder `None`.

        Rueckgabewerte:
        - Passender RepositoryState oder `None`, wenn noch nichts persistiert wurde.

        Moegliche Fehlerfaelle:
        - Fehlende StateRepository-Abhaengigkeit fuehrt defensiv zu `None`.

        Wichtige interne Logik:
        - Lokale Pfade werden bevorzugt, weil sie fuer gekoppelte Repositories die genaueste
          Identitaet bilden. Danach folgt die GitHub-Repository-ID.
        """

        if self._state_repository is None:
            return None
        if local_repo is not None and local_repo.full_path:
            state = self._state_repository.fetch_repository_by_local_path(local_repo.full_path)
            if state is not None:
                return state
        remote_repo_id = 0
        if remote_repo is not None:
            remote_repo_id = remote_repo.repo_id
        elif local_repo is not None:
            remote_repo_id = int(local_repo.remote_repo_id or 0)
        else:
            remote_repo_id = int(repo_ref.get("remote_repo_id") or 0)
        if remote_repo_id:
            return self._state_repository.fetch_repository_by_github_repo_id(remote_repo_id)
        return None

    def _find_remote_repo(self, repo_ref, repositories: list[RemoteRepo]) -> RemoteRepo | None:
        """
        Sucht ein Remote-Repository anhand einer stabilen Referenz.
        """

        remote_repo_id = int(repo_ref.get("remote_repo_id") or repo_ref.get("repo_id") or 0)
        repo_full_name = str(repo_ref.get("repo_full_name") or "")
        remote_url = str(repo_ref.get("remote_url") or repo_ref.get("clone_url") or "")
        for repository in repositories:
            if remote_repo_id and repository.repo_id == remote_repo_id:
                return repository
            if repo_full_name and repository.full_name == repo_full_name:
                return repository
            if remote_url and (repository.clone_url == remote_url or repository.html_url == remote_url):
                return repository
        return None

    def _find_local_repo(self, repo_ref, repositories: list[LocalRepo]) -> LocalRepo | None:
        """
        Sucht ein lokales Repository anhand einer stabilen Referenz.
        """

        remote_repo_id = int(repo_ref.get("remote_repo_id") or 0)
        remote_url = str(repo_ref.get("remote_url") or repo_ref.get("clone_url") or "")
        local_path = str(repo_ref.get("local_path") or "")
        repo_name = str(repo_ref.get("repo_name") or "")
        for repository in repositories:
            if remote_repo_id and repository.remote_repo_id == remote_repo_id:
                return repository
            if remote_url and repository.remote_url == remote_url:
                return repository
            if local_path and repository.full_path == local_path:
                return repository
            if repo_name and repository.name == repo_name:
                return repository
        return None

    def _match_local_to_remote(self, remote_repo: RemoteRepo, repositories: list[LocalRepo]) -> LocalRepo | None:
        """
        Ordnet einem Remote-Repository nach bester verfuegbarer Identitaet ein lokales Gegenstueck zu.
        """

        return self._find_local_repo(
            {
                "remote_repo_id": remote_repo.repo_id,
                "repo_full_name": remote_repo.full_name,
                "remote_url": remote_repo.clone_url,
                "repo_name": remote_repo.name,
            },
            repositories,
        )

    def _match_remote_to_local(self, local_repo: LocalRepo, repositories: list[RemoteRepo]) -> RemoteRepo | None:
        """
        Ordnet einem lokalen Repository nach bester verfuegbarer Identitaet ein Remote-Gegenstueck zu.
        """

        return self._find_remote_repo(
            {
                "remote_repo_id": local_repo.remote_repo_id,
                "remote_url": local_repo.remote_url,
                "repo_name": local_repo.name,
            },
            repositories,
        )

    def _build_languages(self, remote_repo: RemoteRepo | None, local_repo: LocalRepo | None) -> str:
        """
        Erstellt eine einfache Sprach-Zusammenfassung fuer den Repo-Kontext.
        """

        parts: list[str] = []
        if remote_repo is not None and remote_repo.language and remote_repo.language != "-":
            parts.append(remote_repo.language)
        if local_repo is not None and local_repo.language_guess and local_repo.language_guess != "-" and local_repo.language_guess not in parts:
            parts.append(local_repo.language_guess)
        return ", ".join(parts)

    def _build_repo_id(self, repo_ref, remote_repo: RemoteRepo | None, local_repo: LocalRepo | None) -> str | None:
        """
        Erstellt eine lesbare stabile Kontext-ID fuer Dialog und Logging.
        """

        if remote_repo is not None:
            return f"remote:{remote_repo.repo_id}"
        if local_repo is not None:
            return f"local:{local_repo.full_path}"
        if repo_ref.get("remote_url"):
            return f"remote-url:{repo_ref['remote_url']}"
        if repo_ref.get("local_path"):
            return f"local-path:{repo_ref['local_path']}"
        return None

    def _build_diagnostic_events(self, local_repo: LocalRepo | None) -> list[str]:
        """
        Erzeugt eine kompakte Textliste der juengsten State-Ereignisse eines lokalen Repositories.
        """

        if local_repo is None or self._state_repository is None:
            return []
        state_repo_id = local_repo.state_repo_id
        if not state_repo_id and local_repo.full_path:
            state = self._state_repository.fetch_repository_by_local_path(local_repo.full_path)
            state_repo_id = int(state.id or 0) if state is not None and state.id is not None else 0
        if not state_repo_id:
            return []
        events = self._state_repository.fetch_recent_events(state_repo_id, limit=5)
        return [
            f"{event.created_at} | {event.event_type} | {event.message or '-'}"
            for event in events
        ]

    def _build_history_entries(self, repo_name: str, remote_url: str, local_path: str) -> list[ActionSummary]:
        """
        Laedt die juengste Historie eines Repositories in strukturierter Form.

        Eingabeparameter:
        - repo_name: Fachlicher Repository-Name.
        - remote_url: Optionale Remote-URL fuer praeziseres Matching.
        - local_path: Optionaler lokaler Pfad.

        Rueckgabewerte:
        - Liste juengster ActionSummary-Eintraege.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Historie liefert eine leere Liste.

        Wichtige interne Logik:
        - Der RepoHistoryPanel kann damit DB-first arbeiten, ohne erneut die Jobs-DB direkt zu kennen.
        """

        return self._job_log_repository.fetch_recent_activity(
            repo_name=repo_name,
            remote_url=remote_url,
            local_path=local_path,
            limit=12,
        )

    def _build_status_events(self, repository) -> list:
        """
        Laedt die juengsten Statusereignisse eines persistierten Repositories.

        Eingabeparameter:
        - repository: Passender RepositoryState oder `None`.

        Rueckgabewerte:
        - Liste juengster RepoStatusEvent-Eintraege.

        Moegliche Fehlerfaelle:
        - Fehlender State-Layer oder fehlende Repository-ID liefern defensiv eine leere Liste.

        Wichtige interne Logik:
        - Das Diagnosepanel arbeitet damit direkt auf den append-only Events des State-Layers.
        """

        if repository is None or self._state_repository is None or repository.id is None:
            return []
        return self._state_repository.fetch_recent_events(int(repository.id), limit=25)

    def _build_recent_scan_runs(self, local_path: str, clone_url: str) -> list:
        """
        Laedt passende juengste Scan-Laeufe fuer das Diagnosepanel.

        Eingabeparameter:
        - local_path: Lokaler Pfad des Repositories.
        - clone_url: Remote-Clone-URL des Repositories.

        Rueckgabewerte:
        - Liste relevanter ScanRunRecord-Eintraege.

        Moegliche Fehlerfaelle:
        - Fehlender State-Layer liefert defensiv eine leere Liste.

        Wichtige interne Logik:
        - Lokale Kontexte erhalten bevorzugt lokale Refresh-Laeufe, reine Remote-Kontexte
          stattdessen die juengsten Remote-Refreshes.
        """

        if self._state_repository is None:
            return []
        if local_path:
            return self._state_repository.fetch_recent_scan_runs(scan_type="local_normal_refresh", limit=5)
        if clone_url:
            return self._state_repository.fetch_recent_scan_runs(scan_type="remote_refresh", limit=5)
        return self._state_repository.fetch_recent_scan_runs(limit=5)

    def _build_snapshots(self, repository) -> list:
        """
        Laedt die Snapshot-Reihe des aktuellen Repositories fuer Time-Travel und Evolution.

        Eingabeparameter:
        - repository: Persistierter RepositoryState oder `None`.

        Rueckgabewerte:
        - Chronologisch sortierte Snapshot-Liste.

        Moegliche Fehlerfaelle:
        - Fehlender Snapshot-Service oder fehlender `repo_key` liefern defensiv eine leere Liste.

        Wichtige interne Logik:
        - Die Methode bleibt rein lesend und verwendet den stabilen `repo_key` als Hauptidentitaet.
        """

        if repository is None or self._repository_snapshot_service is None or not repository.repo_key:
            return []
        return self._repository_snapshot_service.fetch_snapshots(repository.repo_key, limit=24)

    def _build_evolution(self, snapshots: list) -> tuple[RepositoryEvolutionSummary | None, list[SnapshotDiffResult]]:
        """
        Leitet aus der Snapshot-Reihe die kompakte Evolutionszusammenfassung ab.

        Eingabeparameter:
        - snapshots: Chronologisch sortierte Snapshot-Liste.

        Rueckgabewerte:
        - Tupel aus EvolutionSummary und aufeinanderfolgenden Snapshot-Diffs.

        Moegliche Fehlerfaelle:
        - Fehlender Analyzer liefert defensiv `None` und eine leere Diff-Liste.

        Wichtige interne Logik:
        - Der RepoViewer kann damit Timeline und Evolution auf derselben Snapshot-Grundlage aufbauen.
        """

        if self._repository_evolution_analyzer is None:
            return None, []
        return self._repository_evolution_analyzer.analyze(snapshots)

    def _build_timeline_entries(
        self,
        snapshots: list,
        history_entries: list[ActionSummary],
        status_events: list,
        recent_scan_runs: list,
    ) -> list[RepositoryTimelineEntry]:
        """
        Vereinheitlicht Snapshots, Aktionen, Diagnosen und Scan-Laeufe zu einer Timeline.

        Eingabeparameter:
        - snapshots: Repository-Snapshots aus dem Time-Travel-System.
        - history_entries: Juengste Job- und Aktionsereignisse.
        - status_events: Juengste State-Diagnoseereignisse.
        - recent_scan_runs: Juengste Scan-Lauf-Zusammenfassungen.

        Rueckgabewerte:
        - Absteigend sortierte Timeline-Eintraege.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Teilquellen fuehren nur zu weniger Timeline-Zeilen.

        Wichtige interne Logik:
        - Jede Quelle wird in ein gemeinsames Timeline-Modell normalisiert, damit die UI
          keine Spezialfaelle fuer die verschiedenen Datenbanken kennen muss.
        """

        entries: list[RepositoryTimelineEntry] = []
        for snapshot in snapshots:
            entries.append(
                RepositoryTimelineEntry(
                    timestamp=snapshot.snapshot_timestamp,
                    entry_type="snapshot",
                    title=f"Snapshot | {snapshot.action_type}",
                    details=(
                        f"Branch={snapshot.branch or '-'} | Commit={snapshot.head_commit[:12] or '-'} | "
                        f"Dateien={snapshot.file_count} | Aenderungen={snapshot.change_count}"
                    ),
                    severity="info",
                )
            )
        for action in history_entries:
            entries.append(
                RepositoryTimelineEntry(
                    timestamp=action.timestamp or "",
                    entry_type="action",
                    title=action.action_type or "Aktion",
                    details=action.message or "-",
                    severity="error" if action.status == "error" else "info",
                )
            )
        for event in status_events:
            entries.append(
                RepositoryTimelineEntry(
                    timestamp=event.created_at,
                    entry_type="diagnostic",
                    title=event.event_type,
                    details=event.message or "-",
                    severity=event.severity or "info",
                )
            )
        for run in recent_scan_runs:
            entries.append(
                RepositoryTimelineEntry(
                    timestamp=run.started_at,
                    entry_type="scan_run",
                    title=run.scan_type,
                    details=(
                        f"Dauer={run.duration_ms} ms | Changed={run.changed_count} | "
                        f"Unchanged={run.unchanged_count} | Errors={run.error_count}"
                    ),
                    severity="warning" if run.error_count else "info",
                )
            )
        entries.sort(key=lambda item: item.timestamp, reverse=True)
        return entries[:40]
