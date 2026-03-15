"""Zentrale Zustandsanalyse fuer gekoppelte lokale und entfernte Repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.logger import AppLogger
from models.state_models import RepoLink, RepositoryState
from services.git_service import GitService
from services.repo_action_resolver import RepoActionResolver


@dataclass(slots=True)
class RepositoryPairAnalysis:
    """
    Beschreibt das Ergebnis einer Sync-Analyse fuer ein Repository-Paar.

    Eingabeparameter:
    - local_repository: Aktualisierter lokaler Zustand oder `None` bei Remote-only-Faellen.
    - remote_repository: Aktualisierter Remote-Zustand oder `None` bei Local-only-Faellen.
    - sync_state: Berechneter Synchronisationszustand.
    - health_state: Kompakter Gesundheitszustand fuer UI und Diagnose.
    - analysis_reason: Lesbare Kurzbegruendung fuer die Entscheidung.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Objekt erlaubt dem Orchestrator, Aktualisierungen und Diagnose-Events sauber
      pro Paar zu behandeln, ohne mehrere lose Rueckgabewerte koordinieren zu muessen.
    """

    local_repository: RepositoryState | None
    remote_repository: RepositoryState | None
    sync_state: str
    health_state: str
    analysis_reason: str


class RepositorySyncAnalyzer:
    """Berechnet technische Synchronisationszustaende fuer gekoppelte Repository-Paare."""

    def __init__(
        self,
        git_service: GitService,
        repo_action_resolver: RepoActionResolver | None = None,
        logger: AppLogger | None = None,
    ) -> None:
        """
        Initialisiert den Analyzer mit Git-Leselogik und zentraler Aktionsauflosung.

        Eingabeparameter:
        - git_service: Lesender Git-Service fuer HEAD-, Merge-Base- und Statusabfragen.
        - repo_action_resolver: Regelinstanz fuer empfohlene und verfuegbare Aktionen.
        - logger: Optionaler zentraler Logger fuer Diagnose und Nachvollziehbarkeit.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Analyzer fuehrt nur lesende Git-Abfragen aus und startet keine schreibenden
          Pull-, Push-, Merge- oder Rebase-Operationen.
        """

        self._git_service = git_service
        self._repo_action_resolver = repo_action_resolver or RepoActionResolver()
        self._logger = logger

    def analyze_repository_pair(
        self,
        local_repository: RepositoryState | None,
        remote_repository: RepositoryState | None,
        repo_link: RepoLink | None = None,
    ) -> RepositoryPairAnalysis:
        """
        Analysiert den Synchronisationszustand eines lokalen/entfernten Repository-Paares.

        Eingabeparameter:
        - local_repository: Lokaler Repository-Zustand oder `None`.
        - remote_repository: Entfernte Repository-Sicht oder `None`.
        - repo_link: Optional bestaetigter Pairing-Link zwischen beiden Seiten.

        Rueckgabewerte:
        - RepositoryPairAnalysis mit aktualisierten Zustandsobjekten und Entscheidungsgrund.

        Moegliche Fehlerfaelle:
        - Git-Lesefehler werden defensiv als Problemzustand `BROKEN_REMOTE` oder
          `NOT_INITIALIZED` modelliert, statt die Gesamtanalyse abzubrechen.

        Wichtige interne Logik:
        - Die Entscheidung basiert auf HEAD, Remote-HEAD, Merge-Base, Ahead/Behind und
          uncommitted changes statt auf unscharfen Zeitstempeln.
        """

        if local_repository is None and remote_repository is None:
            return RepositoryPairAnalysis(None, None, "NOT_INITIALIZED", "unknown", "Kein Repository vorhanden.")

        if local_repository is None and remote_repository is not None:
            sync_state = "REMOTE_ONLY"
            health_state = "warning"
            self._apply_pair_metadata(None, remote_repository, repo_link)
            self._apply_analysis(remote_repository, sync_state, health_state, "Repository existiert nur remote.")
            return RepositoryPairAnalysis(None, remote_repository, sync_state, health_state, remote_repository.last_sync_decision)

        if local_repository is not None and remote_repository is None:
            sync_state, health_state, reason = self._analyze_local_without_remote(local_repository)
            self._apply_pair_metadata(local_repository, None, repo_link)
            self._apply_analysis(local_repository, sync_state, health_state, reason)
            return RepositoryPairAnalysis(local_repository, None, sync_state, health_state, reason)

        assert local_repository is not None
        assert remote_repository is not None

        self._apply_pair_metadata(local_repository, remote_repository, repo_link)

        if not local_repository.exists_local or local_repository.is_missing:
            sync_state = "LOCAL_MISSING"
            health_state = "critical"
            reason = "Gekoppeltes lokales Repository ist nicht mehr vorhanden."
            self._apply_analysis(local_repository, sync_state, health_state, reason)
            self._apply_analysis(remote_repository, sync_state, health_state, reason)
            return RepositoryPairAnalysis(local_repository, remote_repository, sync_state, health_state, reason)

        if local_repository.auth_state in {"auth_required", "unauthorized"}:
            sync_state = "AUTH_REQUIRED"
            health_state = "critical"
            reason = "Authentifizierung fuer den Remote-Zugriff ist erforderlich."
            self._apply_analysis(local_repository, sync_state, health_state, reason)
            self._apply_analysis(remote_repository, sync_state, health_state, reason)
            return RepositoryPairAnalysis(local_repository, remote_repository, sync_state, health_state, reason)

        if remote_repository.is_missing or remote_repository.exists_remote is False or local_repository.remote_exists_online == 0:
            sync_state = "REMOTE_MISSING"
            health_state = "critical"
            reason = "Konfiguriertes Remote-Repository wurde online nicht gefunden."
            self._apply_analysis(local_repository, sync_state, health_state, reason)
            self._apply_analysis(remote_repository, sync_state, health_state, reason)
            return RepositoryPairAnalysis(local_repository, remote_repository, sync_state, health_state, reason)

        if not local_repository.is_git_repo or not local_repository.git_initialized:
            sync_state = "NOT_INITIALIZED"
            health_state = "critical"
            reason = "Lokaler Pfad ist kein gueltig initialisiertes Git-Repository."
            self._apply_analysis(local_repository, sync_state, health_state, reason)
            self._apply_analysis(remote_repository, sync_state, health_state, reason)
            return RepositoryPairAnalysis(local_repository, remote_repository, sync_state, health_state, reason)

        repo_path = Path(local_repository.local_path)
        remote_name = local_repository.remote_name or "origin"
        branch_name = local_repository.current_branch or local_repository.default_branch or remote_repository.default_branch

        if not branch_name:
            sync_state = "BROKEN_REMOTE"
            health_state = "critical"
            reason = "Es konnte kein gueltiger Branch fuer den Sync-Vergleich ermittelt werden."
            self._apply_analysis(local_repository, sync_state, health_state, reason)
            self._apply_analysis(remote_repository, sync_state, health_state, reason)
            return RepositoryPairAnalysis(local_repository, remote_repository, sync_state, health_state, reason)

        self._git_service.fetch_remote_updates(repo_path, remote_name)
        local_head_commit = self._git_service.get_head_commit_hash(repo_path)
        remote_head_commit = self._git_service.get_ref_commit_hash(repo_path, f"{remote_name}/{branch_name}")
        merge_base_commit = self._git_service.get_merge_base_commit(repo_path, "HEAD", f"{remote_name}/{branch_name}")
        ahead_count, behind_count, is_diverged = self._git_service.get_ahead_behind_counts(repo_path, branch_name, remote_name)
        has_uncommitted_changes = bool(self._git_service.get_status_porcelain(repo_path))

        local_repository.local_head_commit = local_head_commit
        local_repository.remote_head_commit = remote_head_commit
        local_repository.merge_base_commit = merge_base_commit
        local_repository.head_commit = local_head_commit or local_repository.head_commit
        local_repository.ahead_count = ahead_count
        local_repository.behind_count = behind_count
        local_repository.is_diverged = is_diverged
        local_repository.has_uncommitted_changes = has_uncommitted_changes
        local_repository.exists_remote = True
        local_repository.remote_configured = True

        remote_repository.local_head_commit = local_head_commit
        remote_repository.remote_head_commit = remote_head_commit
        remote_repository.merge_base_commit = merge_base_commit
        remote_repository.ahead_count = ahead_count
        remote_repository.behind_count = behind_count
        remote_repository.is_diverged = is_diverged
        remote_repository.exists_local = True
        remote_repository.exists_remote = True

        sync_state, health_state, reason = self._resolve_pair_state(
            local_head_commit=local_head_commit,
            remote_head_commit=remote_head_commit,
            merge_base_commit=merge_base_commit,
            ahead_count=ahead_count,
            behind_count=behind_count,
            is_diverged=is_diverged,
            has_uncommitted_changes=has_uncommitted_changes,
        )
        self._apply_analysis(local_repository, sync_state, health_state, reason)
        self._apply_analysis(remote_repository, sync_state, health_state, reason)
        return RepositoryPairAnalysis(local_repository, remote_repository, sync_state, health_state, reason)

    def _analyze_local_without_remote(self, local_repository: RepositoryState) -> tuple[str, str, str]:
        """
        Leitet fuer ein lokales Repository ohne aktives Remote-Paar einen Sync-Zustand ab.

        Eingabeparameter:
        - local_repository: Lokaler Repository-Zustand.

        Rueckgabewerte:
        - Tupel aus `sync_state`, `health_state` und lesbarer Begruendung.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte Kombinationen fallen defensiv auf `LOCAL_ONLY` oder
          `BROKEN_REMOTE` zurueck.

        Wichtige interne Logik:
        - Die Methode bildet lokale Sonderfaelle separat ab, damit die Hauptanalyse fuer
          echte Paare uebersichtlich bleibt.
        """

        if not local_repository.exists_local or local_repository.is_missing:
            return "LOCAL_MISSING", "critical", "Lokaler Pfad ist nicht erreichbar."
        if not local_repository.is_git_repo or not local_repository.git_initialized:
            return "NOT_INITIALIZED", "critical", "Der lokale Pfad ist kein gueltiges Git-Repository."
        if local_repository.auth_state in {"auth_required", "unauthorized"}:
            return "AUTH_REQUIRED", "critical", "Die Authentifizierung fuer das Remote ist ungueltig."
        if not local_repository.has_remote or not local_repository.remote_configured:
            return "LOCAL_ONLY", "warning", "Es ist kein Remote konfiguriert."
        if local_repository.remote_exists_online == 0:
            return "REMOTE_MISSING", "critical", "Das konfigurierte Remote wurde online nicht gefunden."
        if local_repository.remote_exists_online is None:
            return "BROKEN_REMOTE", "warning", "Das konfigurierte Remote konnte nicht sicher geprueft werden."
        if local_repository.has_uncommitted_changes:
            return "UNCOMMITTED_LOCAL_CHANGES", "warning", "Lokale Aenderungen sind noch nicht committet."
        return "LOCAL_ONLY", "warning", "Es wurde noch kein aktives Remote-Paar bestaetigt."

    def _resolve_pair_state(
        self,
        local_head_commit: str,
        remote_head_commit: str,
        merge_base_commit: str,
        ahead_count: int,
        behind_count: int,
        is_diverged: bool,
        has_uncommitted_changes: bool,
    ) -> tuple[str, str, str]:
        """
        Loest aus Git-Referenzen und Statuswerten den fachlichen Sync-Zustand auf.

        Eingabeparameter:
        - local_head_commit: Aktueller lokaler HEAD.
        - remote_head_commit: Bekannter Remote-HEAD des Upstream-Branchs.
        - merge_base_commit: Letzter gemeinsamer Commit zwischen lokal und Remote.
        - ahead_count: Anzahl lokaler Commits vor dem Remote.
        - behind_count: Anzahl lokaler Commits hinter dem Remote.
        - is_diverged: Kennzeichnet voneinander abweichende Historien.
        - has_uncommitted_changes: Kennzeichnet ungecommittete lokale Aenderungen.

        Rueckgabewerte:
        - Tupel aus `sync_state`, `health_state` und lesbarer Begruendung.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Git-Referenzen werden defensiv als Problemzustand behandelt.

        Wichtige interne Logik:
        - Die Entscheidung folgt explizit Git-Beziehungen ueber HEAD und Merge-Base
          statt ungenauen Zeit- oder Dateivergleichen.
        """

        if has_uncommitted_changes:
            return "UNCOMMITTED_LOCAL_CHANGES", "warning", "Lokale Arbeitsbaum-Aenderungen sind noch nicht committet."
        if not local_head_commit or not remote_head_commit:
            return "BROKEN_REMOTE", "critical", "Remote-Branch oder lokaler HEAD konnte nicht eindeutig ermittelt werden."
        if local_head_commit == remote_head_commit:
            return "IN_SYNC", "healthy", "Lokaler und entfernter HEAD zeigen auf denselben Commit."
        if is_diverged or (merge_base_commit and merge_base_commit not in {local_head_commit, remote_head_commit}):
            return "DIVERGED", "critical", "Lokale und entfernte Historie sind divergiert."
        if merge_base_commit == remote_head_commit or (ahead_count > 0 and behind_count == 0):
            return "LOCAL_AHEAD", "warning", "Lokale Historie ist dem Remote voraus."
        if merge_base_commit == local_head_commit or (behind_count > 0 and ahead_count == 0):
            return "REMOTE_AHEAD", "warning", "Remote-Historie ist dem lokalen Stand voraus."
        return "DIVERGED", "critical", "Die Commit-Beziehung ist nicht eindeutig aufloesbar."

    def _apply_pair_metadata(
        self,
        local_repository: RepositoryState | None,
        remote_repository: RepositoryState | None,
        repo_link: RepoLink | None,
    ) -> None:
        """
        Uebernimmt Pairing-Metadaten aus dem Link in die betroffenen Repository-Zustaende.

        Eingabeparameter:
        - local_repository: Optionaler lokaler Repository-Zustand.
        - remote_repository: Optionaler entfernter Repository-Zustand.
        - repo_link: Optionaler bestaetigter Pairing-Link.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Link-Metadaten werden auf beiden Seiten gespiegelt, damit lokale und
          entfernte Tabellen dieselbe Kopplungsinformation anzeigen koennen.
        """

        link_type = repo_link.link_type if repo_link is not None else ""
        link_confidence = repo_link.link_confidence if repo_link is not None else 0
        linked_repo_key = remote_repository.repo_key if remote_repository is not None else ""
        linked_local_path = local_repository.local_path if local_repository is not None else ""

        if local_repository is not None:
            local_repository.link_type = link_type
            local_repository.link_confidence = link_confidence
            local_repository.linked_repo_key = linked_repo_key
            local_repository.linked_local_path = linked_local_path
        if remote_repository is not None:
            remote_repository.link_type = link_type
            remote_repository.link_confidence = link_confidence
            remote_repository.linked_repo_key = local_repository.repo_key if local_repository is not None else ""
            remote_repository.linked_local_path = linked_local_path

    def _apply_analysis(
        self,
        repository: RepositoryState,
        sync_state: str,
        health_state: str,
        reason: str,
    ) -> None:
        """
        Uebernimmt den analysierten Sync-Zustand in einen persistierbaren RepositoryState.

        Eingabeparameter:
        - repository: Zu aktualisierender Repository-Zustand.
        - sync_state: Neuer fachlicher Synchronisationszustand.
        - health_state: Neuer Gesundheitszustand.
        - reason: Lesbare Begruendung fuer Diagnose und Historie.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Methode zentralisiert Status, Diagnosegrund und Aktionsauflosung, damit
          Persistenz und UI dieselbe konsistente Sicht erhalten.
        """

        repository.sync_state = sync_state
        repository.status = sync_state
        repository.health_state = health_state
        repository.last_sync_decision = reason
        resolved_actions = self._repo_action_resolver.resolve_repo_actions(repository)
        repository.recommended_action = self._repo_action_resolver.resolve_repo_primary_action(repository)
        repository.available_actions_json = json.dumps(
            [action.action_id for action in resolved_actions],
            ensure_ascii=True,
        )
        if self._logger is not None:
            self._logger.event(
                "sync",
                "repository_sync_analyzed",
                (
                    f"repo_key={repository.repo_key} | sync_state={sync_state} | "
                    f"health_state={health_state} | action={repository.recommended_action}"
                ),
                level=20,
            )
