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
from models.view_models import StatusSnapshot
from services.commit_service import CommitService
from services.git_service import GitService
from services.clone_service import CloneService
from services.delete_service import DeleteService
from services.github_service import GitHubService
from services.local_repo_service import LocalRepoService
from services.push_service import PushService
from services.repo_struct_service import RepoStructService
from ui.dialogs.repo_viewer_dialog import RepoViewerDialog
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
        self._logger.subscribe(self._window.append_log_line)
        self._window.set_target_directory(str(config.default_repo_dir))
        self._window.target_directory_change_requested.connect(self._change_target_directory)
        self._window.remote_repo_open_requested.connect(self.open_repo_context)
        self._window.local_repo_open_requested.connect(self.open_repo_context)

        github_service = GitHubService(env_settings)
        git_service = GitService()
        clone_service = CloneService(git_service=git_service)
        commit_service = CommitService(git_service=git_service)
        push_service = PushService(git_service=git_service, github_service=github_service)
        delete_service = DeleteService(github_service=github_service)
        local_repo_service = LocalRepoService(git_service=git_service, github_service=github_service)
        job_log_repository = JobLogRepository(paths.jobs_db_file)
        repo_struct_service = RepoStructService(self._repo_struct_repository)
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

    def open_repo_context(self, repo_ref: str, source_type: str) -> None:
        """
        Reservierter Einstiegspunkt fuer den spaeteren RepoViewer aus Teil 2.

        Eingabeparameter:
        - repo_ref: Eindeutige Referenz auf das ausgewaehlte Repository.
        - source_type: Herkunft des Repositories, zum Beispiel `remote` oder `local`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine im aktuellen MVP, da nur ein Stub ausgefuehrt wird.

        Wichtige interne Logik:
        - Haltet die zentrale Oeffnungslogik bereits jetzt an genau einer Stelle vor.
        """

        items = self._repo_struct_repository.fetch_repo_items(repo_ref, "local" if source_type == "local" else "remote_clone")
        viewer = RepoViewerDialog(repo_name=repo_ref, source_type=source_type, items=items, parent=self._window)
        viewer.exec()

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
