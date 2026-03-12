"""Technische Git-Inspektion fuer lokale Repositories."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from services.git_service import GitService


class GitInspectorService:
    """Liest stabile Git-Basisinformationen fuer den persistenten State-Layer aus."""

    def __init__(self, git_service: GitService) -> None:
        """
        Initialisiert den Inspektionsservice mit einer Git-Abhaengigkeit.

        Eingabeparameter:
        - git_service: Kapselt alle direkten Git-CLI-Aufrufe.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Service bleibt rein lesend und veraendert nie Repository-Zustand.
        """

        self._git_service = git_service

    def inspect_repository(self, repo_path: Path) -> dict[str, object]:
        """
        Untersucht einen lokalen Ordner und extrahiert Git-Metadaten fuer die State-Datenbank.

        Eingabeparameter:
        - repo_path: Pfad des zu inspizierenden Repository-Ordners.

        Rueckgabewerte:
        - Dictionary mit Name, Pfad, Git-Status, Branch, Commit und Remote-Angaben.

        Moegliche Fehlerfaelle:
        - Defekte Repositories koennen unvollstaendige Werte liefern.

        Wichtige interne Logik:
        - Die Methode verwendet bewusst nur Git-CLI-Abfragen, damit das Verhalten dem
          echten lokalen Zustand entspricht und keine implizite Git-Bibliothek noetig ist.
        """

        self._git_service.ensure_git_available()
        is_git_repo = self._git_service.is_git_repository(repo_path)
        remote_names = self._git_service.get_remote_names(repo_path) if is_git_repo else []
        remote_name = "origin" if "origin" in remote_names else (remote_names[0] if remote_names else "")
        remote_url = self._git_service.get_remote_url(repo_path, remote_name) if remote_name else ""
        branch_name = self._git_service.get_repo_details(repo_path).get("branch", "") if is_git_repo else ""
        status_lines = self._git_service.get_status_porcelain(repo_path) if is_git_repo else []
        remote_host, remote_owner, remote_repo_name = self._parse_remote_details(remote_url)

        return {
            "name": repo_path.name,
            "local_path": str(repo_path),
            "is_git_repo": is_git_repo,
            "branch": str(branch_name or ""),
            "head_commit": self._git_service.get_head_commit_hash(repo_path) if is_git_repo else "",
            "head_commit_date": self._git_service.get_last_commit_date(repo_path) if is_git_repo else "",
            "has_remote": bool(remote_url),
            "remote_name": remote_name,
            "remote_url": remote_url,
            "remote_host": remote_host,
            "remote_owner": remote_owner,
            "remote_repo_name": remote_repo_name,
            "has_uncommitted_changes": bool(status_lines),
        }

    def _parse_remote_details(self, remote_url: str) -> tuple[str, str, str]:
        """
        Zerlegt eine Remote-URL in Host, Owner und Repository-Namen.

        Eingabeparameter:
        - remote_url: HTTPS- oder SSH-URL des Remotes.

        Rueckgabewerte:
        - Tupel aus Host, Owner und Repository-Name.

        Moegliche Fehlerfaelle:
        - Unbekannte Formate liefern leere Werte statt Fehlern.

        Wichtige interne Logik:
        - Unterstuetzt die in GitHub-Workflows ueblichen HTTPS- und SSH-Formate.
        """

        if not remote_url:
            return "", "", ""

        normalized = remote_url.strip()
        if normalized.startswith("git@") and ":" in normalized:
            host_part, path_part = normalized.split(":", 1)
            host = host_part.split("@", 1)[-1]
            owner, repo_name = self._split_owner_repo(path_part)
            return host, owner, repo_name

        parsed = urlparse(normalized)
        if parsed.scheme and parsed.netloc:
            owner, repo_name = self._split_owner_repo(parsed.path.lstrip("/"))
            return parsed.netloc, owner, repo_name

        return "", "", ""

    def _split_owner_repo(self, path_text: str) -> tuple[str, str]:
        """
        Trennt einen URL-Pfad in Owner- und Repository-Segment.

        Eingabeparameter:
        - path_text: URL-Pfad ohne fuehrenden Slash.

        Rueckgabewerte:
        - Tupel aus Owner und bereinigtem Repository-Namen.

        Moegliche Fehlerfaelle:
        - Zu kurze Pfade liefern leere Werte.

        Wichtige interne Logik:
        - Entfernt ein optionales `.git`, damit spaetere Vergleiche stabil bleiben.
        """

        segments = [segment for segment in path_text.split("/") if segment]
        if len(segments) < 2:
            return "", ""
        repo_name = segments[1][:-4] if segments[1].endswith(".git") else segments[1]
        return segments[0], repo_name
