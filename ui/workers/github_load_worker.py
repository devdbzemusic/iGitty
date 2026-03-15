"""Worker-Thread fuer das Laden von GitHub-Repositories."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from services.remote_repo_service import RemoteRepoService


class GitHubLoadWorker(QThread):
    """Fuehrt GitHub-Ladevorgaenge ausserhalb des UI-Threads aus."""

    repositories_loaded = Signal(list, object)
    loading_failed = Signal(str)

    def __init__(self, remote_repo_service: RemoteRepoService) -> None:
        """
        Speichert den auszufuehrenden GitHub-Service fuer den Threadlauf.

        Eingabeparameter:
        - remote_repo_service: Serviceinstanz fuer GitHub-Zugriff plus SQLite-Delta-Sync.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Worker kennt nur den Service und emittiert rohe Ergebnisse an den Controller.
        """

        super().__init__()
        self._remote_repo_service = remote_repo_service

    def run(self) -> None:
        """
        Fuehrt den GitHub-Ladevorgang im Hintergrundthread aus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fachliche oder technische Fehler werden als String-Signal weitergereicht.

        Wichtige interne Logik:
        - Die Exception-Behandlung bleibt bewusst schmal, damit der Controller den UI-Zustand sauber pflegen kann.
        """

        try:
            repositories, rate_limit = self._remote_repo_service.sync_repositories()
            self.repositories_loaded.emit(repositories, rate_limit)
        except Exception as error:  # noqa: BLE001
            self.loading_failed.emit(str(error))
