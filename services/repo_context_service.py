"""Service zum Zusammenfuehren eines sauberen Repo-Kontexts fuer Teil 2."""

from __future__ import annotations

from models.repo_models import LocalRepo, RemoteRepo
from models.view_models import RepoContext
from db.job_log_repository import JobLogRepository
from db.state_repository import StateRepository
from services.repo_struct_service import RepoStructService


class RepoContextService:
    """Erzeugt RepoContext-Modelle aus Remote-, Local-, History- und Vault-Daten."""

    def __init__(
        self,
        job_log_repository: JobLogRepository,
        repo_struct_service: RepoStructService,
        state_repository: StateRepository | None = None,
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

        repo_name = (
            local_repo.name if local_repo is not None else remote_repo.name if remote_repo is not None else str(repo_ref.get("repo_name", ""))
        )
        remote_url = (
            local_repo.remote_url if local_repo is not None and local_repo.remote_url else remote_repo.html_url if remote_repo is not None else ""
        )
        clone_url = remote_repo.clone_url if remote_repo is not None else remote_url
        local_path = local_repo.full_path if local_repo is not None else ""
        repo_id = self._build_repo_id(repo_ref, remote_repo, local_repo)
        struct_source_type = "local" if local_repo is not None else "remote_clone"
        has_struct_vault_data, struct_item_count, last_struct_scan_timestamp = self._repo_struct_service.fetch_repo_summary(
            repo_identifier=repo_name,
            source_type=struct_source_type,
        )
        last_action = self._job_log_repository.fetch_last_general_action(
            repo_name=repo_name,
            remote_url=clone_url,
            local_path=local_path,
        )
        diagnostic_events = self._build_diagnostic_events(local_repo)

        return RepoContext(
            source_type=source_type,
            repo_id=repo_id,
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
            has_struct_vault_data=has_struct_vault_data,
            struct_item_count=struct_item_count,
            last_struct_scan_timestamp=last_struct_scan_timestamp,
            diagnostic_events=diagnostic_events,
        )

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
