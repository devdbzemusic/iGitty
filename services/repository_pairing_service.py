"""Zentrale Verknuepfungslogik zwischen lokalen und entfernten Repositories."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from core.logger import AppLogger
from db.state_repository import StateRepository
from models.state_models import RepoLink, RepositoryState


class RepositoryPairingService:
    """Ermittelt und persistiert stabile Verknuepfungen zwischen lokalen und Remote-Repositories."""

    def __init__(self, state_repository: StateRepository, logger: AppLogger | None = None) -> None:
        """
        Initialisiert den Pairing-Service mit Zugriff auf den persistierten State-Layer.

        Eingabeparameter:
        - state_repository: SQLite-Zugriff fuer Repositories und persistierte Pairing-Links.
        - logger: Optionaler zentraler Logger fuer Diagnose und Nachvollziehbarkeit.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Service arbeitet ausschliesslich lesend und schreibend auf dem State-Layer
          und fuehrt keine Git- oder Netzwerkaktionen aus.
        """

        self._state_repository = state_repository
        self._logger = logger

    def resolve_links(
        self,
        local_repositories: list[RepositoryState] | None = None,
        remote_repositories: list[RepositoryState] | None = None,
        verified_at: str | None = None,
    ) -> list[RepoLink]:
        """
        Loest stabile Pairings zwischen lokalen und entfernten Repository-Zustaenden auf.

        Eingabeparameter:
        - local_repositories: Optional bereits geladene lokale Repository-Zustaende.
        - remote_repositories: Optional bereits geladene Remote-Repository-Zustaende.
        - verified_at: Optionaler Zeitstempel fuer die persistierten Link-Pruefungen.

        Rueckgabewerte:
        - Liste aller in diesem Lauf bestaetigten aktiven oder diagnostisch interessanten Links.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Lesen oder Schreiben der Pairing-Links.

        Wichtige interne Logik:
        - Sichere Matches ueber URL oder GitHub-ID werden aktiv gespeichert.
        - Owner/Name-Matches gelten als brauchbare, aber schwachere Kopplung.
        - Reine Namensmatches werden nur als inaktive Diagnosehinweise gespeichert und
          niemals stillschweigend wie sichere Kopplungen behandelt.
        """

        local_states = local_repositories or self._state_repository.fetch_local_repositories()
        remote_states = remote_repositories or self._state_repository.fetch_remote_repositories()
        verification_timestamp = verified_at or self._utc_now()

        remote_by_id = {
            repository.github_repo_id: repository
            for repository in remote_states
            if repository.github_repo_id > 0
        }
        remote_by_url = {
            self._normalize_remote_url(repository.remote_url): repository
            for repository in remote_states
            if repository.remote_url
        }
        remote_by_owner_name = {
            self._owner_name_key(repository.remote_owner, repository.remote_repo_name or repository.name): repository
            for repository in remote_states
            if repository.remote_owner and (repository.remote_repo_name or repository.name)
        }

        resolved_links: list[RepoLink] = []
        for local_repository in local_states:
            if local_repository.id is None:
                continue

            existing_link = self._state_repository.fetch_active_repo_link_for_state_repo_id(int(local_repository.id))
            if existing_link is not None and existing_link.link_type == "manual":
                remote_repository = remote_by_id.get(existing_link.github_repo_id)
                if remote_repository is not None:
                    existing_link.is_active = True
                    existing_link.last_verified_at = verification_timestamp
                    resolved_links.append(self._state_repository.upsert_repo_link(existing_link))
                    continue

            candidate_link = self._build_candidate_link(
                local_repository=local_repository,
                remote_by_id=remote_by_id,
                remote_by_url=remote_by_url,
                remote_by_owner_name=remote_by_owner_name,
                remote_repositories=remote_states,
                verified_at=verification_timestamp,
            )
            if candidate_link is None:
                self._state_repository.deactivate_repo_links_for_state_repo(int(local_repository.id))
                continue

            if candidate_link.is_active:
                self._state_repository.deactivate_repo_links_for_state_repo(int(local_repository.id))
            persisted_link = self._state_repository.upsert_repo_link(candidate_link)
            resolved_links.append(persisted_link)

            if self._logger is not None:
                self._logger.event(
                    "pairing",
                    "repo_link_resolved",
                    (
                        f"repo_name={local_repository.name} | local_path={local_repository.local_path} | "
                        f"github_repo_id={persisted_link.github_repo_id} | link_type={persisted_link.link_type} | "
                        f"confidence={persisted_link.link_confidence} | active={persisted_link.is_active}"
                    ),
                    level=20,
                )

        return resolved_links

    def _build_candidate_link(
        self,
        local_repository: RepositoryState,
        remote_by_id: dict[int, RepositoryState],
        remote_by_url: dict[str, RepositoryState],
        remote_by_owner_name: dict[str, RepositoryState],
        remote_repositories: list[RepositoryState],
        verified_at: str,
    ) -> RepoLink | None:
        """
        Baut fuer ein lokales Repository den bestmoeglichen Pairing-Kandidaten auf.

        Eingabeparameter:
        - local_repository: Lokaler Repository-Zustand als Ausgangsbasis.
        - remote_by_id: Remote-Lookup nach GitHub-ID.
        - remote_by_url: Remote-Lookup nach normalisierter URL.
        - remote_by_owner_name: Remote-Lookup nach Owner/Repository-Schluessel.
        - remote_repositories: Vollstaendige Remote-Liste fuer unsichere Namensmatches.
        - verified_at: Zeitstempel der aktuellen Pairing-Pruefung.

        Rueckgabewerte:
        - RepoLink fuer sichere oder diagnostisch interessante Zuordnungen oder `None`.

        Moegliche Fehlerfaelle:
        - Keine; unaufloesbare Faelle liefern `None`.

        Wichtige interne Logik:
        - Die Priorisierung folgt strikt URL, GitHub-ID, Owner/Name und zuletzt reinem
          Repository-Namen als unsicherem Hinweis.
        """

        normalized_remote_url = self._normalize_remote_url(local_repository.remote_url)
        if normalized_remote_url:
            exact_remote = remote_by_url.get(normalized_remote_url)
            if exact_remote is not None and exact_remote.id is not None:
                return self._build_repo_link(local_repository, exact_remote, "exact", 100, True, verified_at)

        if local_repository.github_repo_id > 0:
            remote_by_repo_id = remote_by_id.get(local_repository.github_repo_id)
            if remote_by_repo_id is not None and remote_by_repo_id.id is not None:
                return self._build_repo_link(
                    local_repository,
                    remote_by_repo_id,
                    "github_id_match",
                    100,
                    True,
                    verified_at,
                )

        owner_name_key = self._owner_name_key(local_repository.remote_owner, local_repository.remote_repo_name)
        if owner_name_key:
            owner_name_match = remote_by_owner_name.get(owner_name_key)
            if owner_name_match is not None and owner_name_match.id is not None:
                return self._build_repo_link(
                    local_repository,
                    owner_name_match,
                    "url_match",
                    90,
                    True,
                    verified_at,
                )

        same_name_matches = [
            repository
            for repository in remote_repositories
            if repository.name.strip().lower() == local_repository.name.strip().lower()
        ]
        if len(same_name_matches) == 1 and same_name_matches[0].id is not None:
            return self._build_repo_link(
                local_repository,
                same_name_matches[0],
                "name_match",
                60,
                False,
                verified_at,
            )

        return None

    def _build_repo_link(
        self,
        local_repository: RepositoryState,
        remote_repository: RepositoryState,
        link_type: str,
        link_confidence: int,
        is_active: bool,
        verified_at: str,
    ) -> RepoLink:
        """
        Baut aus einem lokalen und einem entfernten Repository einen persistierbaren Link.

        Eingabeparameter:
        - local_repository: Lokaler Repository-Zustand.
        - remote_repository: Entfernter Repository-Zustand.
        - link_type: Fachlicher Typ des Matches.
        - link_confidence: Vertrauensstufe des Matches.
        - is_active: Kennzeichnet, ob der Link fachlich als aktive Kopplung gilt.
        - verified_at: Zeitstempel der aktuellen Pruefung.

        Rueckgabewerte:
        - Vollstaendig aufgebauter RepoLink.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Methode sammelt alle relevanten Link-Metadaten an einer Stelle, damit
          die Priorisierung zuvor getrennt von der Persistenzlogik bleibt.
        """

        return RepoLink(
            state_repo_id=int(local_repository.id or 0),
            github_repo_id=remote_repository.github_repo_id,
            local_path=local_repository.local_path,
            remote_url=remote_repository.remote_url,
            remote_owner=remote_repository.remote_owner,
            remote_name=remote_repository.remote_repo_name or remote_repository.name,
            link_type=link_type,
            link_confidence=link_confidence,
            is_active=is_active,
            last_verified_at=verified_at,
        )

    def _normalize_remote_url(self, remote_url: str) -> str:
        """
        Normalisiert GitHub-Remote-URLs fuer robuste URL-Vergleiche.

        Eingabeparameter:
        - remote_url: Beliebige GitHub-Remote-URL aus HTTPS- oder SSH-Form.

        Rueckgabewerte:
        - Normalisierte Form `host/owner/repo` in Kleinbuchstaben oder Leerstring.

        Moegliche Fehlerfaelle:
        - Nicht interpretierbare Formate liefern einen Leerstring.

        Wichtige interne Logik:
        - Durch die gemeinsame Normalform koennen SSH- und HTTPS-URLs desselben
          GitHub-Repositories als exakter Match erkannt werden.
        """

        normalized = remote_url.strip()
        if not normalized:
            return ""
        if normalized.startswith("git@") and ":" in normalized:
            host_part, path_part = normalized.split(":", 1)
            host = host_part.split("@", 1)[-1].strip().lower()
            owner_repo = path_part.strip().lower()
        else:
            parsed = urlparse(normalized)
            if not parsed.netloc:
                return ""
            host = parsed.netloc.strip().lower()
            owner_repo = parsed.path.lstrip("/").strip().lower()

        if owner_repo.endswith(".git"):
            owner_repo = owner_repo[:-4]
        owner_repo = owner_repo.strip("/")
        if not host or owner_repo.count("/") < 1:
            return ""
        return f"{host}/{owner_repo}"

    def _owner_name_key(self, owner: str, repo_name: str) -> str:
        """
        Erzeugt einen stabilen Vergleichsschluessel aus Owner und Repository-Namen.

        Eingabeparameter:
        - owner: GitHub-Owner.
        - repo_name: Repository-Name.

        Rueckgabewerte:
        - Kleingeschriebener Vergleichsschluessel oder Leerstring.

        Moegliche Fehlerfaelle:
        - Leere Werte liefern einen Leerstring.

        Wichtige interne Logik:
        - Die Hilfsmethode vermeidet mehrfach verteilte String-Normalisierung in den
          eigentlichen Pairing-Regeln.
        """

        normalized_owner = owner.strip().lower()
        normalized_repo_name = repo_name.strip().lower()
        if not normalized_owner or not normalized_repo_name:
            return ""
        return f"{normalized_owner}/{normalized_repo_name}"

    def _utc_now(self) -> str:
        """
        Liefert einen konsistenten UTC-Zeitstempel fuer Pairing-Pruefungen.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - ISO-8601-Zeitstempel in UTC.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Einheitliche Zeitstempel erleichtern Diagnose, Tests und Delta-Auswertungen.
        """

        return datetime.now(timezone.utc).isoformat()
