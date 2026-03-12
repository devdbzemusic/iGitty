"""Worker-Thread fuer das Laden von GitHub-Repositories."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from services.github_service import GitHubService


class GitHubLoadWorker(QThread):
    """Fuehrt GitHub-Ladevorgaenge ausserhalb des UI-Threads aus."""

    repositories_loaded = Signal(list, object)
    loading_failed = Signal(str)

    def __init__(self, github_service: GitHubService) -> None:
        """
        Speichert den auszufuehrenden GitHub-Service fuer den Threadlauf.

        Eingabeparameter:
        - github_service: Serviceinstanz fuer den eigentlichen API-Zugriff.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Worker kennt nur den Service und emittiert rohe Ergebnisse an den Controller.
        """

        super().__init__()
        self._github_service = github_service

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
            repositories, rate_limit = self._github_service.fetch_remote_repositories()
            self.repositories_loaded.emit(repositories, rate_limit)
        except Exception as error:  # noqa: BLE001
            self.loading_failed.emit(str(error))
