"""Worker-Thread fuer sichere Remote-Delete-Batches."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from models.repo_models import RemoteRepo
from services.delete_service import DeleteService


class DeleteWorker(QThread):
    """Fuehrt Remote-Deletes ausserhalb des UI-Threads aus."""

    finished_with_results = Signal(list)
    failed = Signal(str)

    def __init__(self, service: DeleteService, repositories: list[RemoteRepo], job_id: str) -> None:
        """
        Speichert die zu loeschenden Repositories fuer den Worker.
        """

        super().__init__()
        self._service = service
        self._repositories = repositories
        self._job_id = job_id

    def run(self) -> None:
        """
        Fuehrt den Delete-Batch im Hintergrundthread aus.
        """

        try:
            self.finished_with_results.emit(self._service.delete_repositories(self._repositories, self._job_id))
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))
