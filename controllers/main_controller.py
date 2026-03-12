"""Hauptcontroller fuer die Basiskoordination der Anwendung."""

from __future__ import annotations

from pathlib import Path

from core.app_state import AppState
from core.config import AppConfig
from core.env import EnvSettings
from core.logger import AppLogger
from core.paths import RuntimePaths
from db.job_log_repository import JobLogRepository
from db.repo_struct_repository import RepoStructRepository
from db.state_repository import StateRepository
from models.view_models import RepoContext, StatusSnapshot
from services.commit_service import CommitService
from services.git_service import GitService
from services.git_inspector_service import GitInspectorService
from services.clone_service import CloneService
from services.delete_service import DeleteService
from services.github_service import GitHubService
from services.local_repo_service import LocalRepoService
from services.push_service import PushService
from services.job_history_view_service import JobHistoryViewService
from services.repo_context_service import RepoContextService
from services.repo_index_service import RepoIndexService
from services.repo_structure_service import RepoStructureService
from services.repo_struct_service import RepoStructService
from services.state_view_service import StateViewService
from services.remote_validation_service import RemoteValidationService
from ui.dialogs.repo_context_dialog import RepoContextDialog
from ui.main_window import MainWindow

from controllers.action_controller import ActionController
from controllers.delete_controller import DeleteController
from controllers.local_repo_controller import LocalRepoController
from controllers.remote_repo_controller import RemoteRepoController


class MainController:
    """Verdrahtet Hauptfenster, Zustand, Services und Teilcontroller."""

    def __init__(
        self,
        window: MainWindow,
        config: AppConfig,
        env_settings: EnvSettings,
        paths: RuntimePaths,
        logger: AppLogger,
    ) -> None:
        """
        Initialisiert die Hauptkoordination der Anwendung.

        Eingabeparameter:
        - window: Bereits erzeugtes Hauptfenster.
        - config: Zentrale Anwendungskonfiguration.
        - env_settings: Geladene Umgebungsvariablen.
        - paths: Laufzeitpfade des Projekts.
        - logger: Zentraler Logger fuer Datei und UI.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler in abhaengigen Komponenten werden an deren Stellen behandelt.

        Wichtige interne Logik:
        - Setzt zuerst den sichtbaren Grundzustand der UI.
        - Registriert danach Teilcontroller fuer konkrete Funktionsbereiche.
        """

        self._window = window
        self._state = AppState(current_target_dir=config.default_repo_dir)
        self._logger = logger
        self._repo_struct_repository = RepoStructRepository(paths.repo_struct_db_file)
        self._state_repository = StateRepository(paths.state_db_file)
        self._logger.subscribe(self._window.append_log_line)
        self._window.set_target_directory(str(config.default_repo_dir))
        self._window.target_directory_change_requested.connect(self._change_target_directory)
        self._window.remote_repo_open_requested.connect(self.open_repo_context)
        self._window.local_repo_open_requested.connect(self.open_repo_context)
        self._window.local_repo_selected.connect(self.show_local_repo_diagnostics)

        github_service = GitHubService(env_settings)
        git_service = GitService()
        git_inspector_service = GitInspectorService(git_service=git_service)
        remote_validation_service = RemoteValidationService(github_service=github_service, state_repository=self._state_repository)
        repo_structure_service = RepoStructureService(state_repository=self._state_repository, git_service=git_service)
        repo_index_service = RepoIndexService(
            state_repository=self._state_repository,
            git_inspector_service=git_inspector_service,
            remote_validation_service=remote_validation_service,
            repo_structure_service=repo_structure_service,
        )
        clone_service = CloneService(git_service=git_service)
        commit_service = CommitService(git_service=git_service)
        push_service = PushService(git_service=git_service, github_service=github_service, state_repository=self._state_repository)
        delete_service = DeleteService(github_service=github_service)
        local_repo_service = LocalRepoService(
            git_service=git_service,
            github_service=github_service,
            repo_index_service=repo_index_service,
        )
        job_log_repository = JobLogRepository(paths.jobs_db_file)
        repo_struct_service = RepoStructService(self._repo_struct_repository)
        self._state_view_service = StateViewService(self._state_repository)
        self._job_history_view_service = JobHistoryViewService(job_log_repository)
        self._repo_context_service = RepoContextService(
            job_log_repository=job_log_repository,
            repo_struct_service=repo_struct_service,
            state_repository=self._state_repository,
        )
        self._remote_repo_controller = RemoteRepoController(
            window=window,
            github_service=github_service,
            clone_service=clone_service,
            state=self._state,
            logger=logger,
            job_log_repository=job_log_repository,
            post_clone_callback=self._scan_local_after_clone,
        )
        self._local_repo_controller = LocalRepoController(
            window=window,
            local_repo_service=local_repo_service,
            state=self._state,
            logger=logger,
            job_log_repository=job_log_repository,
        )
        self._action_controller = ActionController(
            window=window,
            commit_service=commit_service,
            push_service=push_service,
            git_service=git_service,
            repo_struct_service=repo_struct_service,
            job_log_repository=job_log_repository,
            post_action_refresh_callback=self._scan_local_after_clone,
        )
        self._delete_controller = DeleteController(
            window=window,
            delete_service=delete_service,
            job_log_repository=job_log_repository,
            post_delete_callback=self._remote_repo_controller.load_remote_repositories,
        )

        self._window.update_status(self._build_status_snapshot())
        self._window.append_log_line("iGitty Grundgeruest initialisiert.")

    def _scan_local_after_clone(self) -> None:
        """
        Stoesst nach erfolgreichen Clones einen lokalen Repo-Refresh an.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Etwaige Fehler werden im LocalRepoController behandelt.

        Wichtige interne Logik:
        - Haelt die Kopplung zwischen Remote- und Local-Workflow im Hauptcontroller zentral.
        """

        self._local_repo_controller.scan_local_repositories()

    def open_repo_context(self, repo_ref, source_type: str) -> None:
        """
        Laedt zentral einen zusammengefuehrten Repo-Kontext und oeffnet den Kontextdialog.

        Eingabeparameter:
        - repo_ref: Eindeutige Referenz auf das ausgewaehlte Repository.
        - source_type: Herkunft des Repositories, zum Beispiel `remote` oder `local`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Unvollstaendige Datenquellen koennen Teilinformationen liefern; der Dialog oeffnet trotzdem.

        Wichtige interne Logik:
        - Der Controller haelt die Eintrittsschicht fuer Teil 2 bewusst zentral und UI-neutral.
        """

        try:
            context = self._repo_context_service.build_context(
                repo_ref=repo_ref,
                source_type=source_type,
                remote_repositories=self._window.get_remote_repositories(),
                local_repositories=self._window.get_local_repositories(),
            )
            dialog = RepoContextDialog(context=context, parent=self._window)
            dialog.exec()
        except Exception as error:  # noqa: BLE001
            self._logger.info(f"Repo-Kontext konnte nicht geladen werden: {error}")
            fallback_context = RepoContext(
                source_type=source_type,
                repo_name=str(repo_ref.get("repo_name") or repo_ref.get("repo_full_name") or repo_ref.get("local_path") or "unbekannt"),
                repo_id=str(repo_ref),
            )
            dialog = RepoContextDialog(context=fallback_context, parent=self._window)
            dialog.exec()

    def show_local_repo_diagnostics(self, repo_ref) -> None:
        """
        Laedt eine kompakte Diagnoseansicht fuer das aktuell selektierte lokale Repository.

        Eingabeparameter:
        - repo_ref: Stabile Referenz aus der lokalen Tabelle.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler im State-Layer fuehren zu einer sichtbaren Fehlzeile statt zu einem UI-Absturz.

        Wichtige interne Logik:
        - Die Diagnose bleibt eine lesende State-Ansicht und fuehrt keine Repository-Aktionen aus.
        """

        try:
            local_path = str(repo_ref.get("local_path") or "")
            repo_name = str(repo_ref.get("repo_name") or "")
            remote_url = str(repo_ref.get("remote_url") or "")
            lines = self._state_view_service.build_local_repo_diagnostics(local_path)
            self._window.set_local_repo_diagnostics(lines)
            history_lines = self._job_history_view_service.build_repo_history(
                repo_name=repo_name,
                remote_url=remote_url,
                local_path=local_path,
            )
            self._window.set_local_repo_history(history_lines)
        except Exception as error:  # noqa: BLE001
            self._logger.info(f"Repository-Diagnose konnte nicht geladen werden: {error}")
            self._window.set_local_repo_diagnostics([f"Fehler beim Laden der Diagnose: {error}"])
            self._window.set_local_repo_history([f"Fehler beim Laden der Job-Historie: {error}"])

    def _build_status_snapshot(self) -> StatusSnapshot:
        """
        Baut den initialen Status fuer das Hauptfenster.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - StatusSnapshot mit den Startwerten der Anwendung.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Startwerte bleiben zentral, damit MainWindow frei von Fachzustand bleibt.
        """

        return StatusSnapshot(
            github_text=self._state.github_status_text,
            remote_count=self._state.remote_repo_count,
            local_count=self._state.local_repo_count,
            rate_limit_text="0/0 (-)",
            target_dir_text=str(self._state.current_target_dir),
        )

    def _change_target_directory(self, new_directory: str) -> None:
        """
        Uebernimmt einen neu ausgewaehlten Zielordner in den Laufzeitstatus.

        Eingabeparameter:
        - new_directory: Vom UI-Dialog gemeldeter neuer Zielpfad.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Pfade werden in diesem MVP nicht vertieft validiert.

        Wichtige interne Logik:
        - Aktualisiert Statusleiste und sichtbares Feld an einer zentralen Stelle.
        """

        self._state.current_target_dir = Path(new_directory)
        self._window.set_target_directory(new_directory)
        self._window.update_status(self._build_status_snapshot())
        self._window.append_log_line(f"Zielordner auf '{new_directory}' gesetzt.")
