"""Worker-Thread fuer Struktur-Scans lokaler Repositories."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from models.repo_models import LocalRepo
from services.repo_struct_service import RepoStructService


class StructScanWorker(QThread):
    """Fuehrt Struktur-Scans ausserhalb des UI-Threads aus."""

    finished_with_results = Signal(list)
    failed = Signal(str)

    def __init__(self, service: RepoStructService, repositories: list[LocalRepo], job_id: str) -> None:
        """
        Speichert die fuer den Struktur-Batch benoetigten Eingaben.
        """

        super().__init__()
        self._service = service
        self._repositories = repositories
        self._job_id = job_id

    def run(self) -> None:
        """
        Fuehrt den Struktur-Batch im Hintergrundthread aus.
        """

        try:
            self.finished_with_results.emit(self._service.scan_repositories(self._repositories, self._job_id))
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))
