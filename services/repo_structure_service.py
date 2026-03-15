"""Dateibasierte Repository-Strukturindexierung fuer die neue State-Datenbank."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.logger import AppLogger
from db.state_repository import StateRepository
from models.state_models import RepoFileState
from services.git_service import GitService


class RepoStructureService:
    """Indexiert Dateien eines lokalen Repositories in `repo_files`."""

    def __init__(
        self,
        state_repository: StateRepository,
        git_service: GitService,
        logger: AppLogger | None = None,
    ) -> None:
        """
        Verbindet Dateiscanner, Git-Status und State-Datenbank.

        Eingabeparameter:
        - state_repository: Persistente Ablage der Dateieintraege.
        - git_service: Git-Hilfsservice fuer Tracking- und Ignore-Pruefungen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Service trennt Dateisystemscan bewusst vom bisherigen Struktur-Vault, weil hier
          ein aktueller operativer Index und keine historisierte Baumansicht gebraucht wird.
        """

        self._state_repository = state_repository
        self._git_service = git_service
        self._logger = logger

    def index_repository_files(self, repo_id: int, repo_path: Path) -> int:
        """
        Scannt relevante Dateien eines Repositories und ersetzt den persistenten Dateiindex.

        Eingabeparameter:
        - repo_id: Zugehoerige Repository-ID in `repositories`.
        - repo_path: Lokaler Repository-Pfad.

        Rueckgabewerte:
        - Anzahl der indexierten Dateien.

        Moegliche Fehlerfaelle:
        - Dateisystem- oder Git-Fehler koennen einzelne Dateien betreffen.

        Wichtige interne Logik:
        - Ignoriert `.git`, `node_modules` und `__pycache__`, weil diese Pfade fuer die
          iGitty-Uebersicht keinen Mehrwert liefern und Scans unnötig verlangsamen.
        """

        if self._logger is not None:
            self._logger.event("scan", "repo_structure_begin", f"repo_id={repo_id} | repo_path={repo_path}")
        tracked_files = set(self._git_service.list_tracked_files(repo_path))
        ignored_paths = {line.rstrip("/") for line in self._git_service.list_ignored_paths(repo_path)}

        scan_timestamp = self._utc_now()
        files: list[RepoFileState] = []
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in {".git", "node_modules", "__pycache__"} for part in file_path.parts):
                continue

            relative_path = file_path.relative_to(repo_path).as_posix()
            stat = file_path.stat()
            files.append(
                RepoFileState(
                    repo_id=repo_id,
                    relative_path=relative_path,
                    size_bytes=int(stat.st_size),
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    is_tracked=relative_path in tracked_files,
                    is_ignored=self._is_ignored_path(relative_path, ignored_paths),
                    last_seen_scan_at=scan_timestamp,
                )
            )

        self._state_repository.replace_repo_files(repo_id, files)
        if self._logger is not None:
            self._logger.event(
                "scan",
                "repo_structure_complete",
                f"repo_id={repo_id} | repo_path={repo_path} | files={len(files)}",
            )
        return len(files)

    def _is_ignored_path(self, relative_path: str, ignored_paths: set[str]) -> bool:
        """
        Prueft, ob ein relativer Pfad im bekannten Ignore-Set enthalten ist.

        Eingabeparameter:
        - relative_path: Dateipfad relativ zum Repository-Wurzelordner.
        - ignored_paths: Von Git gelieferte ignorierte Dateien und Verzeichnisse.

        Rueckgabewerte:
        - `True`, wenn die Datei oder ihr Oberpfad ignoriert ist.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Git kann Verzeichnisse mit Slash melden; deshalb wird neben exakten Treffern auch
          auf Praefixe geprueft.
        """

        for ignored_path in ignored_paths:
            if not ignored_path:
                continue
            normalized = ignored_path.rstrip("/")
            if relative_path == normalized or relative_path.startswith(f"{normalized}/"):
                return True
        return False

    def _utc_now(self) -> str:
        """
        Erzeugt einen UTC-Zeitstempel fuer Dateiscans.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - ISO-Zeitstempel mit Zeitzone.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Einheitliche Zeitstempel vereinfachen spaetere Vergleiche im State-Layer.
        """

        return datetime.now(timezone.utc).isoformat()
