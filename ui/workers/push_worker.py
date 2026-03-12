"""Worker-Thread fuer Push-Batches."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from models.repo_models import LocalRepo
from services.push_service import PushService


class PushWorker(QThread):
    """Fuehrt Push-Aktionen ausserhalb des UI-Threads aus."""

    finished_with_results = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        service: PushService,
        repositories: list[LocalRepo],
        create_remote: bool,
        remote_private: bool,
        description: str,
        job_id: str,
    ) -> None:
        """
        Speichert den Push-Batch fuer die spaetere Worker-Ausfuehrung.
        """

        super().__init__()
        self._service = service
        self._repositories = repositories
        self._create_remote = create_remote
        self._remote_private = remote_private
        self._description = description
        self._job_id = job_id

    def run(self) -> None:
        """
        Fuehrt den Push-Batch im Hintergrundthread aus.
        """

        try:
            self.finished_with_results.emit(
                self._service.push_repositories(
                    self._repositories,
                    self._create_remote,
                    self._remote_private,
                    self._description,
                    self._job_id,
                )
            )
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))
