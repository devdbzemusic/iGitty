"""Worker-Thread fuer Commit-Batches."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from models.repo_models import LocalRepo
from services.commit_service import CommitService


class CommitWorker(QThread):
    """Fuehrt Commit-Aktionen ausserhalb des UI-Threads aus."""

    finished_with_results = Signal(list)
    failed = Signal(str)

    def __init__(self, service: CommitService, repositories: list[LocalRepo], message: str, stage_all: bool, job_id: str) -> None:
        """
        Speichert die fuer den Batch benoetigten Eingaben.

        Eingabeparameter:
        - service: Commit-Service fuer die eigentliche Fachlogik.
        - repositories: Ausgewaehlte lokale Repositories.
        - message: Commit-Nachricht.
        - stage_all: Stage-Modus fuer den Batch.
        - job_id: Uebergeordnete Job-ID.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Initialisierung.

        Wichtige interne Logik:
        - Der Worker enthaelt nur Transportzustand und delegiert die Fachlogik vollstaendig.
        """

        super().__init__()
        self._service = service
        self._repositories = repositories
        self._message = message
        self._stage_all = stage_all
        self._job_id = job_id

    def run(self) -> None:
        """
        Fuehrt den Commit-Batch im Hintergrundthread aus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Unerwartete Gesamtfehler werden als String zurueckgegeben.

        Wichtige interne Logik:
        - Einzelrepo-Fehler werden vom Service selbst in Ergebnisobjekte ueberfuehrt.
        """

        try:
            self.finished_with_results.emit(
                self._service.commit_repositories(self._repositories, self._message, self._stage_all, self._job_id)
            )
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))
