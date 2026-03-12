"""Controller fuer lokale Commit-, Push- und Struktur-Aktionen."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from PySide6.QtWidgets import QMessageBox

from db.job_log_repository import JobLogRepository
from models.job_models import ActionRecord, JobLogEntry
from services.commit_service import CommitService
from services.git_service import GitService
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
        git_service: GitService,
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
        self._git_service = git_service
        self._repo_struct_service = repo_struct_service
        self._job_log_repository = job_log_repository
        self._post_action_refresh_callback = post_action_refresh_callback
        self._commit_worker: CommitWorker | None = None
        self._push_worker: PushWorker | None = None
        self._struct_worker: StructScanWorker | None = None

        self._window.commit_requested.connect(self.commit_selected_repositories)
        self._window.push_requested.connect(self.push_selected_repositories)
        self._window.struct_scan_requested.connect(self.scan_selected_repositories_structure)
        self._window.local_repo_action_requested.connect(self.handle_local_repo_action)

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
        if not self._handle_push_preconditions(repositories):
            return
        remote_private = False
        description = ""
        if create_remote:
            dialog = CreateRemoteDialog(
                repositories[0].name,
                initial_private=not repositories[0].publish_as_public,
                parent=self._window,
            )
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
                    repo_owner=result.repo_owner,
                    local_path=result.local_path,
                    remote_url=result.remote_url,
                    status=result.status,
                    message=result.message,
                    reversible_flag=result.reversible_flag,
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

    def handle_local_repo_action(self, repo_ref, action_name: str) -> None:
        """
        Fuehrt eine lokale Kontextaktion fuer genau ein Repository aus.

        Eingabeparameter:
        - repo_ref: Stabile Referenz aus der Tabelle.
        - action_name: Technischer Aktionsname aus dem Kontextmenue.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Unbekannte Repository-Referenzen oder Git-/GitHub-Fehler.

        Wichtige interne Logik:
        - Die Methode buendelt Reparaturpfade zentral, statt Fachlogik in der UI zu verteilen.
        """

        repository = self._resolve_local_repository(repo_ref)
        if repository is None:
            self._window.append_log_line("Kontextaktion konnte keinem lokalen Repository zugeordnet werden.")
            return

        try:
            if action_name == "remove_remote":
                self._push_service.remove_remote_and_keep_local(repository)
                self._window.append_log_line(f"Remote fuer '{repository.name}' wurde entfernt.")
            elif action_name == "reinitialize_repository":
                self._push_service.reinitialize_repository(repository)
                self._window.append_log_line(f"Repository '{repository.name}' wurde neu initialisiert.")
            elif action_name in {"repair_remote", "create_remote"}:
                dialog = CreateRemoteDialog(
                    repository.name,
                    initial_private=not repository.publish_as_public,
                    parent=self._window,
                )
                if dialog.exec() == 0:
                    return
                remote_private, description = dialog.get_values()
                repository_for_push = repository
                if repository.has_remote and repository.remote_status == "REMOTE_MISSING":
                    self._push_service.remove_remote_and_keep_local(repository)
                    repository_for_push = replace(
                        repository,
                        has_remote=False,
                        remote_url="",
                        remote_status="LOCAL_ONLY",
                    )
                results = self._push_service.push_repositories(
                    [repository_for_push],
                    create_remote=True,
                    remote_private=remote_private,
                    description=description,
                    job_id=str(uuid4()),
                )
                self._on_action_results(results)
                return
            else:
                self._window.append_log_line(f"Unbekannte Kontextaktion: {action_name}")
                return
        except Exception as error:  # noqa: BLE001
            self._window.append_log_line(f"Fehler bei Kontextaktion '{action_name}': {error}")
            return

        if callable(self._post_action_refresh_callback):
            self._post_action_refresh_callback()

    def _handle_push_preconditions(self, repositories) -> bool:
        """
        Prueft kritische Push-Vorbedingungen und bietet bei Problemfaellen passende Folgeaktionen an.

        Eingabeparameter:
        - repositories: Vom Benutzer ausgewaehlte lokale Repositories.

        Rueckgabewerte:
        - `True`, wenn der Push normal fortgesetzt werden darf, sonst `False`.

        Moegliche Fehlerfaelle:
        - Dialogabbrueche oder unbekannte Stati stoppen den Push defensiv.

        Wichtige interne Logik:
        - Mehrdeutige Sammelfaelle werden nicht automatisch aufgeloest, um unerwuenschte Seiteneffekte zu vermeiden.
        """

        problematic = [repo for repo in repositories if repo.remote_status in {"REMOTE_MISSING", "BROKEN_GIT"}]
        if not problematic:
            return True
        if len(problematic) > 1 or len(repositories) > 1:
            QMessageBox.warning(
                self._window,
                "Push",
                "Repositories mit REMOTE_MISSING oder BROKEN_GIT bitte einzeln ueber das Kontextmenue reparieren.",
            )
            return False

        repository = problematic[0]
        if repository.remote_status == "BROKEN_GIT":
            answer = QMessageBox.question(
                self._window,
                "Repository reparieren",
                f"'{repository.name}' ist als BROKEN_GIT markiert. Soll `git init` zur Reparatur versucht werden?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.handle_local_repo_action({"local_path": repository.full_path}, "reinitialize_repository")
            return False

        message_box = QMessageBox(self._window)
        message_box.setWindowTitle("Remote fehlt")
        message_box.setText(
            f"Das Remote von '{repository.name}' existiert online nicht mehr. "
            "Waehle einen Wiederherstellungspfad."
        )
        remove_button = message_box.addButton("Remote entfernen", QMessageBox.ButtonRole.AcceptRole)
        create_button = message_box.addButton("Neues GitHub-Repo", QMessageBox.ButtonRole.ActionRole)
        keep_button = message_box.addButton("Lokal behalten", QMessageBox.ButtonRole.RejectRole)
        message_box.exec()

        clicked = message_box.clickedButton()
        if clicked == remove_button:
            self.handle_local_repo_action({"local_path": repository.full_path}, "remove_remote")
        elif clicked == create_button:
            self.handle_local_repo_action({"local_path": repository.full_path}, "create_remote")
        elif clicked == keep_button:
            self._window.append_log_line(f"'{repository.name}' bleibt vorerst lokal unveraendert.")
        return False

    def _resolve_local_repository(self, repo_ref) -> object | None:
        """
        Ordnet eine Tabellenreferenz dem aktuellen LocalRepo-Objekt zu.

        Eingabeparameter:
        - repo_ref: Referenzdictionary aus MainWindow.

        Rueckgabewerte:
        - Passendes LocalRepo oder `None`.

        Moegliche Fehlerfaelle:
        - Keine; nicht aufloesbare Referenzen liefern `None`.

        Wichtige interne Logik:
        - Bevorzugt den lokalen Pfad als stabilen Schluessel statt sichtbarer Tabellenwerte.
        """

        local_path = str(repo_ref.get("local_path") or "")
        for repository in self._window.get_local_repositories():
            if repository.full_path == local_path:
                return repository
        return None

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
