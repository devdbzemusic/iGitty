"""Erkennung und Aufbereitung lokaler Git-Repositories."""

from __future__ import annotations

import json
from pathlib import Path

from core.logger import AppLogger
from models.repo_models import LocalRepo
from models.state_models import RepositoryState
from services.git_service import GitService
from services.github_service import GitHubService
from services.repo_action_resolver import RepoActionResolver
from services.repo_index_service import RepoIndexService
from services.state_db import compute_repository_status


class LocalRepoService:
    """Scannt Verzeichnisse rekursiv nach Git-Repositories und liest deren Status aus."""

    def __init__(
        self,
        git_service: GitService,
        github_service: GitHubService | None = None,
        repo_index_service: RepoIndexService | None = None,
        logger: AppLogger | None = None,
        repo_action_resolver: RepoActionResolver | None = None,
    ) -> None:
        """
        Initialisiert den Service mit einer Git-Abhaengigkeit.

        Eingabeparameter:
        - git_service: Service fuer alle direkten Git-CLI-Abfragen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Die Git-spezifische Logik bleibt strikt ausserhalb dieses Scanners.
        """

        self._git_service = git_service
        self._github_service = github_service
        self._repo_index_service = repo_index_service
        self._logger = logger
        self._repo_action_resolver = repo_action_resolver or RepoActionResolver()
        self._remote_metadata_cache: dict[str, tuple[str, int]] = {}

    def load_cached_repositories(self, root_path: Path) -> list[LocalRepo]:
        """
        Laedt bereits bekannte lokale Repositories fuer einen Root sofort aus der State-Datenbank.

        Eingabeparameter:
        - root_path: Basisverzeichnis des aktuell aktiven lokalen Arbeitsbereichs.

        Rueckgabewerte:
        - Liste der aus SQLite aufgebauten lokalen Repository-View-Modelle.

        Moegliche Fehlerfaelle:
        - Ohne konfigurierten State-Index steht nur eine leere Liste zur Verfuegung.

        Wichtige interne Logik:
        - Die Methode ist die DB-first-Eintrittsschicht fuer STUFE 2 und fuehrt selbst
          keinen Tiefenscan aus.
        """

        if self._repo_index_service is None:
            return []
        repository_states = self._repo_index_service.fetch_cached_root(root_path)
        mapped_repositories = [self._map_state_to_local_repo(repository) for repository in repository_states]
        mapped_repositories.sort(key=lambda item: item.name.lower())
        return mapped_repositories

    def scan_repositories(self, root_path: Path, hard_refresh: bool = False) -> list[LocalRepo]:
        """
        Durchsucht einen Wurzelordner rekursiv nach Git-Repositories.

        Eingabeparameter:
        - root_path: Startordner fuer die Suche.
        - hard_refresh: Erzwingt einen vollstaendigen Tiefenscan im State-Index.

        Rueckgabewerte:
        - Liste aller erkannten und angereicherten lokalen Repositories.

        Moegliche Fehlerfaelle:
        - Nicht vorhandener oder unlesbarer Suchpfad.
        - Fehlende Git-CLI.

        Wichtige interne Logik:
        - Erkennt Repositories ueber `.git`-Ordner.
        - Schneidet Unterbaeume erkannter Repositories ab, um doppelte Funde zu vermeiden.
        """

        if self._logger is not None:
            self._logger.event("scan", "local_scan_begin", f"root_path={root_path}")
        self._git_service.ensure_git_available()
        if not root_path.exists():
            if self._logger is not None:
                self._logger.warning(f"Lokaler Scanpfad existiert nicht: {root_path}")
            return []

        if self._repo_index_service is not None:
            if self._logger is not None:
                self._logger.event(
                    "scan",
                    "local_scan_using_state_index",
                    f"root_path={root_path} | hard_refresh={hard_refresh}",
                )
            repository_states = self._repo_index_service.scan_root(root_path, hard_refresh=hard_refresh)
            mapped_repositories = [self._map_state_to_local_repo(repository) for repository in repository_states]
            if self._logger is not None:
                self._logger.event(
                    "scan",
                    "local_scan_complete",
                    f"root_path={root_path} | repositories={len(mapped_repositories)}",
                )
            return mapped_repositories

        repositories: list[LocalRepo] = []
        for current_path, dir_names, _file_names in root_path.walk():
            if ".git" not in dir_names:
                continue

            repo_path = current_path
            if self._logger is not None:
                self._logger.event("scan", "git_directory_found", f"repo_path={repo_path}")
            details = self._git_service.get_repo_details(repo_path)
            remote_visibility, remote_repo_id = self._resolve_remote_visibility(str(details["remote_url"]))
            repositories.append(
                LocalRepo(
                    name=repo_path.name,
                    full_path=str(repo_path),
                    current_branch=str(details["branch"]),
                    has_remote=bool(details["has_remote"]),
                    remote_url=str(details["remote_url"]),
                    has_changes=bool(details["has_changes"]),
                    untracked_count=int(details["untracked_count"]),
                    modified_count=int(details["modified_count"]),
                    last_commit_hash=str(details["last_commit_hash"]),
                    last_commit_date=str(details["last_commit_date"]),
                    last_commit_message=str(details["last_commit_message"]),
                    remote_visibility=remote_visibility,
                    publish_as_public=(not bool(details["has_remote"]) or remote_visibility == "public"),
                    remote_repo_id=remote_repo_id,
                    language_guess=self._guess_language(repo_path),
                )
            )
            dir_names[:] = []

        repositories.sort(key=lambda item: item.name.lower())
        if self._logger is not None:
            self._logger.event("scan", "local_scan_complete", f"root_path={root_path} | repositories={len(repositories)}")
        return repositories

    def refresh_repository(self, repo_path: Path) -> LocalRepo | None:
        """
        Aktualisiert gezielt genau ein lokales Repository fuer die Tabellenanzeige.

        Eingabeparameter:
        - repo_path: Vollstaendiger Pfad des zu aktualisierenden Repositories.

        Rueckgabewerte:
        - Aktualisiertes `LocalRepo` oder `None`, wenn der Pfad nicht mehr existiert.

        Moegliche Fehlerfaelle:
        - Git- oder GitHub-Probleme werden wie beim normalen Scan defensiv behandelt.

        Wichtige interne Logik:
        - Die Methode ist fuer direkte Reparaturpfade gedacht, damit ein einzelner Eintrag
          ohne kompletten Root-Scan aktualisiert werden kann.
        """

        if self._logger is not None:
            self._logger.event("scan", "local_single_refresh_begin", f"repo_path={repo_path}")
        self._git_service.ensure_git_available()
        if not repo_path.exists():
            if self._logger is not None:
                self._logger.warning(f"Einzelaktualisierung uebersprungen, Pfad existiert nicht: {repo_path}")
            return None

        if self._repo_index_service is not None:
            repository_state = self._repo_index_service.index_repository(repo_path)
            if repository_state is None:
                return None
            mapped_repository = self._map_state_to_local_repo(repository_state)
            if self._logger is not None:
                self._logger.event(
                    "scan",
                    "local_single_refresh_complete",
                    f"repo_path={repo_path} | status={mapped_repository.remote_status}",
                )
            return mapped_repository

        details = self._git_service.get_repo_details(repo_path)
        remote_visibility, remote_repo_id = self._resolve_remote_visibility(str(details["remote_url"]))
        repository = LocalRepo(
            name=repo_path.name,
            full_path=str(repo_path),
            current_branch=str(details["branch"]),
            has_remote=bool(details["has_remote"]),
            remote_url=str(details["remote_url"]),
            has_changes=bool(details["has_changes"]),
            untracked_count=int(details["untracked_count"]),
            modified_count=int(details["modified_count"]),
            last_commit_hash=str(details["last_commit_hash"]),
            last_commit_date=str(details["last_commit_date"]),
            last_commit_message=str(details["last_commit_message"]),
            remote_visibility=remote_visibility,
            publish_as_public=(not bool(details["has_remote"]) or remote_visibility == "public"),
            remote_repo_id=remote_repo_id,
            language_guess=self._guess_language(repo_path),
            remote_status=compute_repository_status(True, bool(details["has_remote"]), None),
        )
        if self._logger is not None:
            self._logger.event(
                "scan",
                "local_single_refresh_complete",
                f"repo_path={repo_path} | status={repository.remote_status}",
            )
        return repository

    def _map_state_to_local_repo(self, repository: RepositoryState) -> LocalRepo:
        """
        Wandelt einen persistierten Repository-Zustand in das UI-nahe LocalRepo-Modell um.

        Eingabeparameter:
        - repository: Persistierter Zustand aus `igitty_state.db`.

        Rueckgabewerte:
        - Vollstaendig aufbereitetes LocalRepo fuer Tabelle und Workflows.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Werte werden mit stabilen Defaults ersetzt.

        Wichtige interne Logik:
        - Das Mapping verbindet den neuen State-Layer rueckwaertskompatibel mit den
          bestehenden Controllern und Workern.
        """

        remote_repo_id = 0
        if repository.remote_owner and repository.remote_repo_name:
            visibility, resolved_repo_id = self._resolve_remote_visibility(repository.remote_url)
            if repository.remote_visibility in {"unknown", "not_published"}:
                repository.remote_visibility = visibility
            remote_repo_id = resolved_repo_id

        repo_details = {}
        if repository.is_git_repo:
            try:
                repo_details = self._git_service.get_repo_details(Path(repository.local_path))
            except Exception:  # noqa: BLE001
                repo_details = {}

        mapped_repo = LocalRepo(
            name=repository.name,
            full_path=repository.local_path,
            current_branch=repository.current_branch or "-",
            has_remote=repository.has_remote,
            remote_url=repository.remote_url,
            has_changes=bool(repo_details.get("has_changes", False)),
            untracked_count=int(repo_details.get("untracked_count", 0)),
            modified_count=int(repo_details.get("modified_count", 0)),
            last_commit_hash=repository.head_commit or "-",
            last_commit_date=repository.head_commit_date or "-",
            last_commit_message=str(repo_details.get("last_commit_message", "-")),
            remote_visibility=repository.remote_visibility,
            publish_as_public=(not repository.has_remote or repository.remote_visibility == "public"),
            remote_repo_id=remote_repo_id,
            language_guess=self._guess_language(Path(repository.local_path)),
            state_repo_id=int(repository.id or 0),
            remote_status=repository.status,
            remote_exists_online=repository.remote_exists_online,
            exists_local=repository.exists_local,
            needs_rescan=repository.needs_rescan,
            health_state=repository.health_state,
            sync_state=repository.sync_state,
            owner=repository.remote_owner,
            remote_name=repository.remote_repo_name,
            ahead_count=repository.ahead_count,
            behind_count=repository.behind_count,
            last_checked_at=repository.last_checked_at,
            link_type=repository.link_type,
            link_confidence=repository.link_confidence,
            sync_policy=repository.sync_policy,
            local_head_commit=repository.local_head_commit or repository.head_commit,
            remote_head_commit=repository.remote_head_commit,
            merge_base_commit=repository.merge_base_commit,
            state_status_hash=repository.status_hash,
        )
        mapped_repo.recommended_action = repository.recommended_action or self._repo_action_resolver.resolve_local_primary_action(mapped_repo)
        try:
            mapped_repo.available_actions = [str(action_id) for action_id in json.loads(repository.available_actions_json or "[]")]
        except json.JSONDecodeError:
            mapped_repo.available_actions = []
        if not mapped_repo.available_actions:
            mapped_repo.available_actions = [
                action.action_id
                for action in self._repo_action_resolver.resolve_local_actions(mapped_repo)
            ]
        if self._logger is not None:
            self._logger.event(
                "scan",
                "state_repository_mapped",
                f"name={mapped_repo.name} | status={mapped_repo.remote_status} | local_path={mapped_repo.full_path}",
            )
        return mapped_repo

    def _guess_language(self, repo_path: Path) -> str:
        """
        Schaetzt die dominante Sprache eines Repositories ueber Dateiendungen grob ab.

        Eingabeparameter:
        - repo_path: Pfad des lokalen Repositories.

        Rueckgabewerte:
        - Kurzbezeichnung der geschaetzten Hauptsprache.

        Moegliche Fehlerfaelle:
        - Unbekannte Dateitypen fuehren zu `-` als Rueckgabewert.

        Wichtige interne Logik:
        - Die Heuristik bleibt bewusst leichtgewichtig und schnell fuer den MVP.
        """

        extension_map = {
            ".py": "Python",
            ".cs": "C#",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".json": "JSON",
            ".md": "Markdown",
        }
        counts: dict[str, int] = {}
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            if ".git" in file_path.parts:
                continue
            language = extension_map.get(file_path.suffix.lower())
            if language:
                counts[language] = counts.get(language, 0) + 1

        if not counts:
            if self._logger is not None:
                self._logger.event("scan", "language_guess_empty", f"repo_path={repo_path}")
            return "-"
        language = max(counts.items(), key=lambda item: item[1])[0]
        if self._logger is not None:
            self._logger.event("scan", "language_guess_complete", f"repo_path={repo_path} | language={language}")
        return language

    def _resolve_remote_visibility(self, remote_url: str) -> tuple[str, int]:
        """
        Ermittelt die Remote-Sichtbarkeit eines lokalen Repositories.

        Eingabeparameter:
        - remote_url: Aktuelle `origin`-URL des lokalen Repositories.

        Rueckgabewerte:
        - Tupel aus Sichtbarkeit (`public`, `private`, `unknown`, `not_published`) und Repository-ID.

        Moegliche Fehlerfaelle:
        - GitHub-Abfragen koennen fehlschlagen und fallen dann auf `unknown` zurueck.

        Wichtige interne Logik:
        - Verwendet einen kleinen Cache, damit mehrere identische Remotes nicht doppelt aufgeloest werden.
        """

        if not remote_url:
            if self._logger is not None:
                self._logger.event("scan", "resolve_remote_visibility_skipped", "Kein Remote vorhanden.")
            return "not_published", 0
        if remote_url in self._remote_metadata_cache:
            if self._logger is not None:
                self._logger.event("scan", "resolve_remote_visibility_cache_hit", f"remote_url={remote_url}")
            return self._remote_metadata_cache[remote_url]
        if self._github_service is None:
            if self._logger is not None:
                self._logger.event("scan", "resolve_remote_visibility_no_github_service", f"remote_url={remote_url}")
            return "unknown", 0
        try:
            result = self._github_service.resolve_remote_metadata(remote_url)
        except Exception:  # noqa: BLE001
            result = ("unknown", 0)
            if self._logger is not None:
                self._logger.warning(f"Remote-Sichtbarkeit konnte nicht aufgeloest werden: {remote_url}")
        self._remote_metadata_cache[remote_url] = result
        if self._logger is not None:
            self._logger.event(
                "scan",
                "resolve_remote_visibility_complete",
                f"remote_url={remote_url} | visibility={result[0]} | repo_id={result[1]}",
            )
        return result
