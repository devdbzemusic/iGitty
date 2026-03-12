"""Controller fuer lokale Commit-, Push- und Struktur-Aktionen."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtWidgets import QMessageBox

from db.job_log_repository import JobLogRepository
from models.job_models import ActionRecord, JobLogEntry
from services.commit_service import CommitService
from services.push_service import PushService
from services.repo_struct_service import RepoStructService
from ui.dialogs.commit_dialog import CommitDialog
from ui.dialogs.create_remote_dialog import CreateRemoteDialog
from ui.main_window import MainWindow
from ui.workers.commit_worker import CommitWorker
from ui.workers.push_worker import PushWorker
from ui.workers.struct_scan_worker import StructScanWorker


class ActionController:
    """Koordiniert lokale Batch-Aktionen ausserhalb des Repo-Scans."""

    def __init__(
        self,
        window: MainWindow,
        commit_service: CommitService,
        push_service: PushService,
        repo_struct_service: RepoStructService,
        job_log_repository: JobLogRepository,
        post_action_refresh_callback=None,
    ) -> None:
        """
        Verdrahtet lokale Buttons mit den zugehoerigen Batch-Workflows.
        """

        self._window = window
        self._commit_service = commit_service
        self._push_service = push_service
        self._repo_struct_service = repo_struct_service
        self._job_log_repository = job_log_repository
        self._post_action_refresh_callback = post_action_refresh_callback
        self._commit_worker: CommitWorker | None = None
        self._push_worker: PushWorker | None = None
        self._struct_worker: StructScanWorker | None = None

        self._window.commit_requested.connect(self.commit_selected_repositories)
        self._window.push_requested.connect(self.push_selected_repositories)
        self._window.struct_scan_requested.connect(self.scan_selected_repositories_structure)

    def commit_selected_repositories(self) -> None:
        """
        Startet einen Commit-Batch fuer die ausgewaehlten lokalen Repositories.
        """

        repositories = self._window.selected_local_repositories()
        if not repositories:
            self._window.append_log_line("Kein lokales Repository fuer Commit ausgewaehlt.")
            return

        dialog = CommitDialog(self._window)
        if dialog.exec() == 0:
            return
        message, stage_all = dialog.get_values()
        if not message:
            QMessageBox.warning(self._window, "Commit", "Eine Commit-Nachricht ist erforderlich.")
            return

        self._window.set_commit_loading(True)
        self._commit_worker = CommitWorker(self._commit_service, repositories, message, stage_all, str(uuid4()))
        self._commit_worker.finished_with_results.connect(self._on_action_results)
        self._commit_worker.failed.connect(self._on_commit_failed)
        self._commit_worker.start()

    def push_selected_repositories(self) -> None:
        """
        Startet einen Push-Batch fuer die ausgewaehlten lokalen Repositories.
        """

        repositories = self._window.selected_local_repositories()
        if not repositories:
            self._window.append_log_line("Kein lokales Repository fuer Push ausgewaehlt.")
            return

        create_remote = any(not repository.has_remote for repository in repositories)
        remote_private = False
        description = ""
        if create_remote:
            dialog = CreateRemoteDialog(repositories[0].name, self._window)
            if dialog.exec() == 0:
                return
            remote_private, description = dialog.get_values()

        self._window.set_push_loading(True)
        self._push_worker = PushWorker(
            self._push_service,
            repositories,
            create_remote,
            remote_private,
            description,
            str(uuid4()),
        )
        self._push_worker.finished_with_results.connect(self._on_action_results)
        self._push_worker.failed.connect(self._on_push_failed)
        self._push_worker.start()

    def scan_selected_repositories_structure(self) -> None:
        """
        Startet einen Struktur-Scan fuer die ausgewaehlten lokalen Repositories.
        """

        repositories = self._window.selected_local_repositories()
        if not repositories:
            self._window.append_log_line("Kein lokales Repository fuer Struktur-Scan ausgewaehlt.")
            return

        self._window.set_struct_scan_loading(True)
        self._struct_worker = StructScanWorker(self._repo_struct_service, repositories, str(uuid4()))
        self._struct_worker.finished_with_results.connect(self._on_action_results)
        self._struct_worker.failed.connect(self._on_struct_failed)
        self._struct_worker.start()

    def _on_action_results(self, results: list[ActionRecord]) -> None:
        """
        Verarbeitet generische Ergebnislisten aus Commit-, Push- und Struktur-Workern.
        """

        self._window.set_commit_loading(False)
        self._window.set_push_loading(False)
        self._window.set_struct_scan_loading(False)
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
            self._window.append_log_line(f"{result.action_type} {result.repo_name}: {result.status} - {result.message}")

        if callable(self._post_action_refresh_callback):
            self._post_action_refresh_callback()

    def _on_commit_failed(self, error_message: str) -> None:
        """
        Reagiert auf einen schwerwiegenden Commit-Worker-Fehler.
        """

        self._window.set_commit_loading(False)
        self._window.append_log_line(f"Fehler: {error_message}")

    def _on_push_failed(self, error_message: str) -> None:
        """
        Reagiert auf einen schwerwiegenden Push-Worker-Fehler.
        """

        self._window.set_push_loading(False)
        self._window.append_log_line(f"Fehler: {error_message}")

    def _on_struct_failed(self, error_message: str) -> None:
        """
        Reagiert auf einen schwerwiegenden Struktur-Worker-Fehler.
        """

        self._window.set_struct_scan_loading(False)
        self._window.append_log_line(f"Fehler: {error_message}")
