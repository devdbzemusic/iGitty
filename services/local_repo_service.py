"""Erkennung und Aufbereitung lokaler Git-Repositories."""

from __future__ import annotations

from pathlib import Path

from models.repo_models import LocalRepo
from services.git_service import GitService


class LocalRepoService:
    """Scannt Verzeichnisse rekursiv nach Git-Repositories und liest deren Status aus."""

    def __init__(self, git_service: GitService) -> None:
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

        repositories: list[LocalRepo] = []
        for current_path, dir_names, _file_names in root_path.walk():
            if ".git" not in dir_names:
                continue

            repo_path = current_path
            details = self._git_service.get_repo_details(repo_path)
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
                    language_guess=self._guess_language(repo_path),
                )
            )
            dir_names[:] = []

        repositories.sort(key=lambda item: item.name.lower())
        return repositories

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
