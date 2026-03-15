"""Worker-Thread fuer lokale Repository-Scans."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from services.local_repo_service import LocalRepoService


class LocalScanWorker(QThread):
    """Fuehrt den lokalen Repository-Scan ausserhalb des UI-Threads aus."""

    repositories_loaded = Signal(list)
    loading_failed = Signal(str)

    def __init__(self, local_repo_service: LocalRepoService, root_path: Path, hard_refresh: bool = False) -> None:
        """
        Speichert Service und Zielpfad fuer den spaeteren Threadlauf.

        Eingabeparameter:
        - local_repo_service: Fachservice fuer die eigentliche Repo-Erkennung.
        - root_path: Zu scannender Wurzelordner.
        - hard_refresh: Erzwingt einen vollstaendigen Tiefenscan statt Delta-Skip.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Das Worker-Objekt enthaelt bewusst nur Transportzustand, keine UI-Verantwortung.
        """

        super().__init__()
        self._local_repo_service = local_repo_service
        self._root_path = root_path
        self._hard_refresh = hard_refresh

    def run(self) -> None:
        """
        Fuehrt den lokalen Scan im Hintergrundthread aus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fachliche oder technische Fehler werden als String-Signal an den Controller gemeldet.

        Wichtige interne Logik:
        - Der Worker bleibt absichtlich schmal, damit die gesamte Ablaufsteuerung im Controller liegt.
        """

        try:
            repositories = self._local_repo_service.scan_repositories(self._root_path, hard_refresh=self._hard_refresh)
            self.repositories_loaded.emit(repositories)
        except Exception as error:  # noqa: BLE001
            self.loading_failed.emit(str(error))
