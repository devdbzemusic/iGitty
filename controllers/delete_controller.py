"""Controller fuer sichere Remote-Loeschvorgaenge."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from db.job_log_repository import JobLogRepository
from models.job_models import JobLogEntry
from services.delete_service import DeleteService
from ui.dialogs.delete_confirm_dialog import DeleteConfirmDialog
from ui.main_window import MainWindow
from ui.workers.delete_worker import DeleteWorker


class DeleteController:
    """Koordiniert die Sicherheitslogik vor einem Remote-Delete."""

    def __init__(self, window: MainWindow, delete_service: DeleteService, job_log_repository: JobLogRepository, post_delete_callback=None) -> None:
        """
        Verdrahtet den Delete-Button mit Clone-Nachweis und Bestaetigungsdialog.
        """

        self._window = window
        self._delete_service = delete_service
        self._job_log_repository = job_log_repository
        self._post_delete_callback = post_delete_callback
        self._worker: DeleteWorker | None = None
        self._window.delete_remote_requested.connect(self.delete_selected_remote_repositories)

    def delete_selected_remote_repositories(self) -> None:
        """
        Startet einen sicheren Delete-Batch fuer ausgewaehlte Remote-Repositories.
        """

        repositories = self._window.selected_remote_repositories()
        if not repositories:
            self._window.append_log_line("Kein Remote-Repository zum Loeschen ausgewaehlt.")
            return

        deletable = []
        for repository in repositories:
            if not self._job_log_repository.has_successful_clone(
                repo_name=repository.name,
                remote_url=repository.clone_url or repository.html_url,
                repo_id=repository.repo_id,
            ):
                self._window.append_log_line(
                    f"Delete verweigert fuer {repository.name}: Kein erfolgreicher Clone-Nachweis ueber Name, URL oder Repo-ID in SQLite vorhanden."
                )
                continue
            dialog = DeleteConfirmDialog(repository.name, str(Path.cwd() / repository.name), self._window)
            if dialog.exec() == 0 or not dialog.is_confirmation_valid():
                self._window.append_log_line(f"Delete fuer {repository.name} abgebrochen oder nicht bestaetigt.")
                continue
            deletable.append(repository)

        if not deletable:
            return

        self._window.set_delete_loading(True)
        self._worker = DeleteWorker(self._delete_service, deletable, str(uuid4()))
        self._worker.finished_with_results.connect(self._on_delete_results)
        self._worker.failed.connect(self._on_delete_failed)
        self._worker.start()

    def _on_delete_results(self, results: list) -> None:
        """
        Verarbeitet die Ergebnisliste eines abgeschlossenen Delete-Batches.
        """

        self._window.set_delete_loading(False)
        success_found = False
        for result in results:
            self._job_log_repository.add_action_record(result)
            self._job_log_repository.add_entry(
                JobLogEntry(
                    job_id=str(uuid4()),
                    action_type=result.action_type,
                    source_type=result.source_type,
                    repo_name=result.repo_name,
                    status=result.status,
                    message=result.message,
                )
            )
            self._window.append_log_line(f"delete_remote {result.repo_name}: {result.status} - {result.message}")
            success_found = success_found or result.status == "success"
        if success_found and callable(self._post_delete_callback):
            self._post_delete_callback()

    def _on_delete_failed(self, error_message: str) -> None:
        """
        Reagiert auf einen schwerwiegenden Delete-Worker-Fehler.
        """

        self._window.set_delete_loading(False)
        self._window.append_log_line(f"Fehler: {error_message}")
