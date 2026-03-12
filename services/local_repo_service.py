"""Erkennung und Aufbereitung lokaler Git-Repositories."""

from __future__ import annotations

from pathlib import Path

from models.repo_models import LocalRepo
from models.state_models import RepositoryState
from services.git_service import GitService
from services.github_service import GitHubService
from services.repo_index_service import RepoIndexService


class LocalRepoService:
    """Scannt Verzeichnisse rekursiv nach Git-Repositories und liest deren Status aus."""

    def __init__(
        self,
        git_service: GitService,
        github_service: GitHubService | None = None,
        repo_index_service: RepoIndexService | None = None,
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
        self._remote_metadata_cache: dict[str, tuple[str, int]] = {}

    def scan_repositories(self, root_path: Path) -> list[LocalRepo]:
        """
        Durchsucht einen Wurzelordner rekursiv nach Git-Repositories.

        Eingabeparameter:
        - root_path: Startordner fuer die Suche.

        Rueckgabewerte:
        - Liste aller erkannten und angereicherten lokalen Repositories.

        Moegliche Fehlerfaelle:
        - Nicht vorhandener oder unlesbarer Suchpfad.
        - Fehlende Git-CLI.

        Wichtige interne Logik:
        - Erkennt Repositories ueber `.git`-Ordner.
        - Schneidet Unterbaeume erkannter Repositories ab, um doppelte Funde zu vermeiden.
        """

        self._git_service.ensure_git_available()
        if not root_path.exists():
            return []

        if self._repo_index_service is not None:
            repository_states = self._repo_index_service.scan_root(root_path)
            return [self._map_state_to_local_repo(repository) for repository in repository_states]

        repositories: list[LocalRepo] = []
        for current_path, dir_names, _file_names in root_path.walk():
            if ".git" not in dir_names:
                continue

            repo_path = current_path
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
                    publish_as_public=(remote_visibility == "public"),
                    remote_repo_id=remote_repo_id,
                    language_guess=self._guess_language(repo_path),
                )
            )
            dir_names[:] = []

        repositories.sort(key=lambda item: item.name.lower())
        return repositories

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

        return LocalRepo(
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
            publish_as_public=(repository.remote_visibility == "public"),
            remote_repo_id=remote_repo_id,
            language_guess=self._guess_language(Path(repository.local_path)),
            state_repo_id=int(repository.id or 0),
            remote_status=repository.status,
            remote_exists_online=repository.remote_exists_online,
            recommended_action=self._build_recommended_action(repository.status),
        )

    def _build_recommended_action(self, remote_status: str) -> str:
        """
        Leitet aus dem Repository-Status eine kurze UI-Empfehlung ab.

        Eingabeparameter:
        - remote_status: Fachlicher Gesamtstatus des Repositories.

        Rueckgabewerte:
        - Kurzer Handlungshinweis fuer die lokale Tabelle.

        Moegliche Fehlerfaelle:
        - Unbekannte Stati liefern einen neutralen Platzhalter.

        Wichtige interne Logik:
        - Die Empfehlung bleibt bewusst knapp, damit die eigentliche Aktion im Controller entschieden wird.
        """

        recommendations = {
            "REMOTE_OK": "Normal pushen",
            "LOCAL_ONLY": "GitHub-Repo anlegen",
            "REMOTE_MISSING": "Remote reparieren",
            "REMOTE_UNREACHABLE": "Remote pruefen",
            "BROKEN_GIT": "Repo reparieren",
            "NOT_INITIALIZED": "Git initialisieren",
        }
        return recommendations.get(remote_status, "-")

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
            return "-"
        return max(counts.items(), key=lambda item: item[1])[0]

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
            return "not_published", 0
        if remote_url in self._remote_metadata_cache:
            return self._remote_metadata_cache[remote_url]
        if self._github_service is None:
            return "unknown", 0
        try:
            result = self._github_service.resolve_remote_metadata(remote_url)
        except Exception:  # noqa: BLE001
            result = ("unknown", 0)
        self._remote_metadata_cache[remote_url] = result
        return result
