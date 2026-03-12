"""Controller fuer das Scannen und Anzeigen lokaler Repositories."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject

from core.app_state import AppState
from core.logger import AppLogger
from db.job_log_repository import JobLogRepository
from models.job_models import JobLogEntry
from models.view_models import StatusSnapshot
from services.local_repo_service import LocalRepoService
from ui.main_window import MainWindow
from ui.workers.local_scan_worker import LocalScanWorker


class LocalRepoController(QObject):
    """Koordiniert das rekursive Scannen lokaler Git-Repositories."""

    def __init__(
        self,
        window: MainWindow,
        local_repo_service: LocalRepoService,
        state: AppState,
        logger: AppLogger,
        job_log_repository: JobLogRepository,
    ) -> None:
        """
        Verbindet UI-Signale mit dem lokalen Scan-Service.

        Eingabeparameter:
        - window: Hauptfenster mit Zugriff auf die lokale Tabellenansicht.
        - local_repo_service: Fachservice fuer Repo-Erkennung.
        - state: Zentraler Laufzeitstatus.
        - logger: Zentraler Logger.
        - job_log_repository: Persistentes Job-Logging.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler treten erst beim Scan oder beim Job-Logging auf.

        Wichtige interne Logik:
        - Hellt denselben asynchronen Ablauf wie der Remote-Controller ein, damit das Verhalten konsistent bleibt.
        """

        super().__init__()
        self._window = window
        self._local_repo_service = local_repo_service
        self._state = state
        self._logger = logger
        self._job_log_repository = job_log_repository
        self._current_worker: LocalScanWorker | None = None

        self._window.scan_local_requested.connect(self.scan_local_repositories)
        self._window.local_filter_changed.connect(self._window.set_local_filter_text)

    def scan_local_repositories(self) -> None:
        """
        Startet das asynchrone Scannen des aktuellen Zielordners.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Parallel gestartete Worker werden verworfen.

        Wichtige interne Logik:
        - Der Scan laeuft im Worker, damit die UI auch bei grossen Verzeichnisbaeumen stabil bleibt.
        """

        if self._current_worker is not None and self._current_worker.isRunning():
            return

        self._window.set_local_loading(True)
        self._logger.info(f"Starte lokalen Repo-Scan in '{self._state.current_target_dir}'.")
        self._current_worker = LocalScanWorker(
            local_repo_service=self._local_repo_service,
            root_path=Path(self._state.current_target_dir),
        )
        self._current_worker.repositories_loaded.connect(self._on_repositories_loaded)
        self._current_worker.loading_failed.connect(self._on_loading_failed)
        self._current_worker.start()

    def _on_repositories_loaded(self, repositories: list) -> None:
        """
        Uebernimmt erfolgreich gescannte lokale Repositories in UI und Status.

        Eingabeparameter:
        - repositories: Geladene LocalRepo-Objekte.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler beim Schreiben des Job-Logs.

        Wichtige interne Logik:
        - Aktualisiert die Tabelle erst nach vollstaendigem Scan, damit das UI konsistent bleibt.
        """

        self._state.local_repo_count = len(repositories)
        self._window.populate_local_repositories(repositories)
        self._window.set_local_loading(False)
        self._window.update_status(self._build_status_snapshot())
        self._logger.info(f"{len(repositories)} lokale Repositories erfolgreich erkannt.")
        self._job_log_repository.add_entry(
            JobLogEntry(
                job_id=str(uuid4()),
                action_type="local_scan",
                source_type="local",
                repo_name="*",
                status="success",
                message=f"{len(repositories)} lokale Repositories erkannt",
            )
        )

    def _on_loading_failed(self, error_message: str) -> None:
        """
        Reagiert auf einen fehlgeschlagenen lokalen Scan.

        Eingabeparameter:
        - error_message: Fachlich aufbereitete Fehlermeldung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler beim Schreiben des Job-Logs.

        Wichtige interne Logik:
        - Setzt den Ladezustand sauber zurueck, auch wenn der Worker fehlschlaegt.
        """

        self._window.set_local_loading(False)
        self._window.update_status(self._build_status_snapshot())
        self._logger.info(f"Lokaler Repo-Scan fehlgeschlagen: {error_message}")
        self._job_log_repository.add_entry(
            JobLogEntry(
                job_id=str(uuid4()),
                action_type="local_scan",
                source_type="local",
                repo_name="*",
                status="error",
                message=error_message,
            )
        )
        self._window.append_log_line(f"Fehler: {error_message}")

    def _build_status_snapshot(self) -> StatusSnapshot:
        """
        Erstellt einen Status-Snapshot fuer die UI aus dem aktuellen Laufzeitstatus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Vollstaendig formatierter StatusSnapshot.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Nutzt dieselbe Formatierung wie der Remote-Controller fuer ein einheitliches Statusbild.
        """

        rate_limit_text = (
            f"{self._state.rate_limit.remaining}/{self._state.rate_limit.limit} "
            f"(Reset {self._state.rate_limit.reset_at})"
        )
        return StatusSnapshot(
            github_text=self._state.github_status_text,
            remote_count=self._state.remote_repo_count,
            local_count=self._state.local_repo_count,
            rate_limit_text=rate_limit_text,
            target_dir_text=str(self._state.current_target_dir),
        )
