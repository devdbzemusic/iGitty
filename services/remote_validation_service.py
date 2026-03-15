"""Validiert konfigurierte GitHub-Remotes gegen die GitHub-API und aktualisiert den State-Layer."""

from __future__ import annotations

from datetime import datetime, timezone

from db.state_repository import StateRepository
from models.state_models import RepositoryState
from services.github_service import GitHubService
from services.state_db import compute_repository_status


class RemoteValidationService:
    """Prueft, ob ein konfiguriertes Remote-Repository online noch existiert."""

    def __init__(self, github_service: GitHubService, state_repository: StateRepository) -> None:
        """
        Verbindet GitHub-API und State-Datenbank fuer Remote-Checks.

        Eingabeparameter:
        - github_service: Service fuer authentifizierte GitHub-REST-Aufrufe.
        - state_repository: Persistente Ablage des Repositorystatus.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Service kapselt die Online-Pruefung vollstaendig, damit Scans und Pushes
          dieselbe Quelle fuer `remote_exists_online` verwenden.
        """

        self._github_service = github_service
        self._state_repository = state_repository

    def validate_repository(self, repository: RepositoryState) -> RepositoryState:
        """
        Validiert den Remote eines bekannten Repositories und schreibt das Ergebnis zurueck.

        Eingabeparameter:
        - repository: Bereits persistierter oder vorbereiteter Repository-Zustand.

        Rueckgabewerte:
        - Aktualisierte RepositoryState-Instanz.

        Moegliche Fehlerfaelle:
        - API-Fehler fuehren zu `REMOTE_UNREACHABLE`, statt den Gesamtscan abzubrechen.

        Wichtige interne Logik:
        - Nicht-GitHub-Remotes werden defensiv als online unbekannt behandelt.
        """

        if not repository.has_remote or not repository.remote_url:
            repository.remote_exists_online = None
            repository.remote_visibility = "not_published"
            repository.status = compute_repository_status(repository.is_git_repo, repository.has_remote, repository.remote_exists_online)
            repository.exists_remote = None
            repository.sync_state = repository.status
            repository.health_state = "local_only" if repository.status == "LOCAL_ONLY" else "unknown"
            repository.last_remote_check_at = self._utc_now()
            return self._state_repository.upsert_repository(repository)

        owner_repo = self._github_service.parse_github_remote(repository.remote_url)
        if owner_repo is None:
            repository.remote_exists_online = None
            repository.remote_visibility = "unknown"
            repository.status = compute_repository_status(repository.is_git_repo, repository.has_remote, repository.remote_exists_online)
            repository.exists_remote = None
            repository.sync_state = repository.status
            repository.health_state = "remote_unknown"
            repository.last_remote_check_at = self._utc_now()
            return self._state_repository.upsert_repository(repository)

        owner, repo_name = owner_repo
        repository.remote_owner = owner
        repository.remote_repo_name = repo_name
        repository.last_remote_check_at = self._utc_now()

        try:
            status_code, payload = self._github_service.fetch_repository_metadata(owner, repo_name)
        except Exception:  # noqa: BLE001
            repository.remote_exists_online = None
            repository.remote_visibility = "unknown"
            repository.status = compute_repository_status(repository.is_git_repo, repository.has_remote, repository.remote_exists_online)
            repository.exists_remote = None
            repository.sync_state = repository.status
            repository.health_state = "remote_unreachable"
            return self._state_repository.upsert_repository(repository)

        if status_code == 200:
            repository.remote_exists_online = 1
            repository.exists_remote = True
            visibility = payload.get("visibility")
            if not visibility:
                visibility = "private" if payload.get("private") else "public"
            repository.remote_visibility = str(visibility or "unknown")
            repository.visibility = repository.remote_visibility
            repository.github_repo_id = int(payload.get("id") or repository.github_repo_id or 0)
            repository.default_branch = str(payload.get("default_branch") or repository.default_branch or repository.current_branch or "")
            repository.is_archived = bool(payload.get("archived", repository.is_archived))
        elif status_code == 404:
            repository.remote_exists_online = 0
            repository.exists_remote = False
            repository.remote_visibility = "unknown"
        else:
            repository.remote_exists_online = None
            repository.exists_remote = None
            repository.remote_visibility = "unknown"

        repository.status = compute_repository_status(repository.is_git_repo, repository.has_remote, repository.remote_exists_online)
        repository.sync_state = repository.status
        if repository.status == "REMOTE_OK":
            repository.health_state = "healthy"
        elif repository.status == "REMOTE_MISSING":
            repository.health_state = "missing_remote"
        else:
            repository.health_state = "remote_unreachable"
        return self._state_repository.upsert_repository(repository)

    def _utc_now(self) -> str:
        """
        Erzeugt einen konsistenten UTC-Zeitstempel fuer State-Eintraege.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - ISO-Zeitstempel mit Zeitzone.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Einheitliche UTC-Werte vereinfachen spaetere Vergleiche und Tests.
        """

        return datetime.now(timezone.utc).isoformat()
