"""Controller fuer das Laden und Anzeigen von Remote-Repositories."""

from __future__ import annotations

from uuid import uuid4

from pathlib import Path

from PySide6.QtCore import QObject

from core.app_state import AppState
from core.logger import AppLogger
from db.job_log_repository import JobLogRepository
from models.job_models import JobLogEntry
from models.repo_models import RemoteRepo
from models.view_models import StatusSnapshot
from services.clone_service import CloneService
from services.github_service import GitHubService
from services.remote_visibility_service import RemoteVisibilityService
from ui.main_window import MainWindow
from ui.workers.clone_worker import CloneWorker
from ui.workers.github_load_worker import GitHubLoadWorker
from ui.workers.remote_visibility_worker import RemoteVisibilityWorker


class RemoteRepoController(QObject):
    """Koordiniert UI-Aktionen fuer die Remote-GitHub-Liste."""

    def __init__(
        self,
        window: MainWindow,
        github_service: GitHubService,
        clone_service: CloneService,
        remote_visibility_service: RemoteVisibilityService,
        state: AppState,
        logger: AppLogger,
        job_log_repository: JobLogRepository,
        post_clone_callback=None,
    ) -> None:
        """
        Verbindet UI-Signale mit dem GitHub-Service und dem Laufzeitstatus.

        Eingabeparameter:
        - window: Hauptfenster mit den benoetigten Widgets.
        - github_service: Service fuer GitHub-Anfragen.
        - state: Zentraler Laufzeitstatus.
        - logger: Zentraler Anwendungslogger.
        - job_log_repository: Persistentes Job-Logging.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler treten erst bei Benutzeraktionen oder Worker-Ausfuehrung auf.

        Wichtige interne Logik:
        - Haelt keine direkte Fachlogik in der UI, sondern kapselt alle Ablaufschritte zentral.
        """

        super().__init__()
        self._window = window
        self._github_service = github_service
        self._clone_service = clone_service
        self._remote_visibility_service = remote_visibility_service
        self._state = state
        self._logger = logger
        self._job_log_repository = job_log_repository
        self._post_clone_callback = post_clone_callback
        self._current_worker: GitHubLoadWorker | None = None
        self._clone_worker: CloneWorker | None = None
        self._visibility_worker: RemoteVisibilityWorker | None = None
        self._pending_visibility_repository: RemoteRepo | None = None

        self._window.refresh_remote_requested.connect(self.load_remote_repositories)
        self._window.remote_filter_changed.connect(self._window.set_remote_filter_text)
        self._window.clone_requested.connect(self.clone_selected_repositories)
        self._window.remote_repo_action_requested.connect(self.handle_remote_repo_action)

    def load_remote_repositories(self) -> None:
        """
        Startet das asynchrone Laden der Remote-Repositories.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Parallel gestartete Worker werden unterbunden.

        Wichtige interne Logik:
        - Das Laden laeuft in einem Worker-Thread, damit die UI reaktionsfaehig bleibt.
        """

        if self._current_worker is not None and self._current_worker.isRunning():
            return

        self._window.set_remote_loading(True)
        self._logger.info("Starte Laden der Remote-Repositories von GitHub.")
        self._current_worker = GitHubLoadWorker(self._github_service)
        self._current_worker.repositories_loaded.connect(self._on_repositories_loaded)
        self._current_worker.loading_failed.connect(self._on_loading_failed)
        self._current_worker.start()

    def _on_repositories_loaded(self, repositories, rate_limit) -> None:
        """
        Uebernimmt erfolgreich geladene Repositories in UI, Status und Job-Log.

        Eingabeparameter:
        - repositories: Geladene RemoteRepo-Instanzen.
        - rate_limit: Geladene Rate-Limit-Informationen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler beim Schreiben des Job-Logs.

        Wichtige interne Logik:
        - Aktualisiert die UI atomar erst nach erfolgreichem Worker-Ende.
        """

        self._state.remote_repo_count = len(repositories)
        self._state.github_status_text = (
            f"GitHub: {self._github_service.last_authenticated_login}"
            if self._github_service.last_authenticated_login
            else "GitHub verbunden"
        )
        self._state.rate_limit = rate_limit
        self._window.populate_remote_repositories(repositories)
        self._window.set_remote_loading(False)
        self._window.update_status(self._build_status_snapshot())
        self._logger.info(f"{len(repositories)} Remote-Repositories erfolgreich geladen.")
        self._job_log_repository.add_entry(
            JobLogEntry(
                job_id=str(uuid4()),
                action_type="github_load",
                source_type="remote",
                repo_name="*",
                status="success",
                message=f"{len(repositories)} Repositories geladen",
            )
        )

    def _on_loading_failed(self, error_message: str) -> None:
        """
        Reagiert auf einen fehlgeschlagenen Ladeversuch aus dem Worker.

        Eingabeparameter:
        - error_message: Fachlich aufbereitete Fehlermeldung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler beim Schreiben des Job-Logs.

        Wichtige interne Logik:
        - Setzt den UI-Zustand auch im Fehlerfall sauber zurueck.
        """

        self._state.github_status_text = "GitHub Fehler"
        self._window.set_remote_loading(False)
        self._window.update_status(self._build_status_snapshot())
        self._logger.info(f"Remote-Laden fehlgeschlagen: {error_message}")
        self._job_log_repository.add_entry(
            JobLogEntry(
                job_id=str(uuid4()),
                action_type="github_load",
                source_type="remote",
                repo_name="*",
                status="error",
                message=error_message,
            )
        )
        self._window.append_log_line(f"Fehler: {error_message}")

    def clone_selected_repositories(self) -> None:
        """
        Startet den Batch-Clone fuer die aktuell markierten Remote-Repositories.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine Auswahl.
        - Bereits laufender Clone-Worker.

        Wichtige interne Logik:
        - Die UI liefert nur die Auswahl; die eigentliche Clone-Logik bleibt komplett in Service und Worker.
        """

        if self._clone_worker is not None and self._clone_worker.isRunning():
            return

        repositories = self._window.selected_remote_repositories()
        if not repositories:
            self._window.append_log_line("Kein Remote-Repository zum Klonen ausgewaehlt.")
            return

        job_id = str(uuid4())
        self._window.set_clone_loading(True)
        self._logger.info(f"Starte Clone fuer {len(repositories)} ausgewaehlte Remote-Repositories.")
        self._clone_worker = CloneWorker(
            clone_service=self._clone_service,
            repositories=repositories,
            target_root=Path(self._state.current_target_dir),
            job_id=job_id,
        )
        self._clone_worker.clone_finished.connect(self._on_clone_finished)
        self._clone_worker.clone_failed.connect(self._on_clone_failed)
        self._clone_worker.start()

    def _on_clone_finished(self, results: list) -> None:
        """
        Uebernimmt die Ergebnisse eines abgeschlossenen Batch-Clones.

        Eingabeparameter:
        - results: Liste der einzelnen CloneRecord-Ergebnisse.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler beim Schreiben der Datenbankhistorie.

        Wichtige interne Logik:
        - Persistiert jedes Repo-Ergebnis einzeln fuer spaetere Sicherheitslogik.
        """

        self._window.set_clone_loading(False)
        success_count = 0
        for result in results:
            self._job_log_repository.add_clone_record(result)
            self._job_log_repository.add_entry(
                JobLogEntry(
                    job_id=str(uuid4()),
                    action_type="clone",
                    source_type="remote",
                    repo_name=result.repo_name,
                    repo_owner=result.repo_owner,
                    local_path=result.local_path,
                    remote_url=result.remote_url,
                    status=result.status,
                    message=result.message,
                    reversible_flag=result.reversible_flag,
                )
            )
            self._window.append_log_line(f"Clone {result.repo_name}: {result.status} - {result.message}")
            if result.status == "success":
                success_count += 1

        self._logger.info(f"Clone abgeschlossen: {success_count}/{len(results)} erfolgreich.")
        if success_count > 0 and callable(self._post_clone_callback):
            self._window.append_log_line("Starte automatischen Refresh der lokalen Repository-Liste.")
            self._post_clone_callback()

    def _on_clone_failed(self, error_message: str) -> None:
        """
        Reagiert auf einen schwerwiegenden Batch-Clone-Fehler.

        Eingabeparameter:
        - error_message: Fachlich aufbereitete Fehlermeldung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine weiteren; die Methode stellt nur den UI-Zustand wieder her.

        Wichtige interne Logik:
        - Gesamtfehler unterscheiden sich von Einzelrepo-Fehlern, die bereits im Ergebnisobjekt landen.
        """

        self._window.set_clone_loading(False)
        self._logger.info(f"Clone-Worker fehlgeschlagen: {error_message}")
        self._window.append_log_line(f"Fehler: {error_message}")

    def handle_remote_repo_action(self, repo_ref, action_name: str) -> None:
        """
        Fuehrt eine Kontextaktion fuer genau ein Remote-Repository aus.

        Eingabeparameter:
        - repo_ref: Stabile Referenz aus der Remote-Tabelle.
        - action_name: Technischer Aktionsname aus dem Kontextmenue.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Nicht aufloesbare Referenzen.
        - Bereits laufende Sichtbarkeitsaenderung.
        - GitHub-API-Fehler.

        Wichtige interne Logik:
        - Die eigentliche API-Aenderung laeuft bewusst im Worker, damit das Hauptfenster
          waehrenddessen bedienbar bleibt.
        """

        repository = self._resolve_remote_repository(repo_ref)
        if repository is None:
            self._window.append_log_line("Kontextaktion konnte keinem Remote-Repository zugeordnet werden.")
            return

        if self._visibility_worker is not None and self._visibility_worker.isRunning():
            self._window.append_log_line("Es laeuft bereits eine Sichtbarkeitsaenderung fuer ein Remote-Repository.")
            return

        target_visibility = self._resolve_target_visibility(action_name)
        if not target_visibility:
            self._window.append_log_line(f"Unbekannte Remote-Kontextaktion: {action_name}")
            return

        if repository.visibility == target_visibility:
            self._window.append_log_line(
                f"'{repository.name}' ist bereits als {target_visibility} markiert."
            )
            return

        self._pending_visibility_repository = repository
        self._logger.event(
            "action",
            "remote_context_action_requested",
            (
                f"repo_name={repository.name} | repo_id={repository.repo_id} | "
                f"old_visibility={repository.visibility} | target_visibility={target_visibility}"
            ),
            level=20,
        )
        self._window.append_log_line(
            f"Sichtbarkeit fuer '{repository.name}' wird auf {target_visibility} umgestellt..."
        )
        self._visibility_worker = RemoteVisibilityWorker(
            service=self._remote_visibility_service,
            repository=repository,
            target_visibility=target_visibility,
            job_id=str(uuid4()),
        )
        self._visibility_worker.finished_with_result.connect(self._on_visibility_result)
        self._visibility_worker.failed.connect(self._on_visibility_failed)
        self._visibility_worker.start()

    def _on_visibility_result(self, result, updated_repository: RemoteRepo | None) -> None:
        """
        Verarbeitet das Ergebnis einer abgeschlossenen Sichtbarkeitsaenderung.

        Eingabeparameter:
        - result: Allgemeines Aktionsergebnis aus dem Visibility-Service.
        - updated_repository: Optional aktualisiertes Remote-Repository aus der GitHub-API.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehler in Historie oder UI werden wie ueblich an ihren Stellen sichtbar.

        Wichtige interne Logik:
        - Bei Erfolg wird nur der betroffene Tabellen-Eintrag aktualisiert statt die
          komplette Remote-Liste neu von GitHub zu laden.
        """

        previous_repository = self._pending_visibility_repository
        self._pending_visibility_repository = None
        self._visibility_worker = None
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

        if result.status == "success" and updated_repository is not None:
            self._window.upsert_remote_repository(updated_repository)
            old_visibility = previous_repository.visibility if previous_repository is not None else "unknown"
            self._logger.event(
                "state",
                "remote_entry_updated",
                (
                    f"repo_name={updated_repository.name} | repo_id={updated_repository.repo_id} | "
                    f"visibility={old_visibility}->{updated_repository.visibility}"
                ),
                level=20,
            )

    def _on_visibility_failed(self, error_message: str) -> None:
        """
        Reagiert auf einen schwerwiegenden Worker-Fehler bei der Sichtbarkeitsaenderung.

        Eingabeparameter:
        - error_message: Fachlich aufbereitete Fehlermeldung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine weiteren; die Methode stellt nur den sichtbaren Zustand wieder her.

        Wichtige interne Logik:
        - Unerwartete Thread-/Objektfehler werden getrennt von regulaeren GitHub-Antworten behandelt.
        """

        self._pending_visibility_repository = None
        self._visibility_worker = None
        self._logger.info(f"Sichtbarkeits-Worker fehlgeschlagen: {error_message}")
        self._window.append_log_line(f"Fehler: {error_message}")

    def _resolve_remote_repository(self, repo_ref) -> RemoteRepo | None:
        """
        Ordnet eine Tabellenreferenz dem aktuellen RemoteRepo-Objekt zu.

        Eingabeparameter:
        - repo_ref: Referenzdictionary aus MainWindow.

        Rueckgabewerte:
        - Passendes RemoteRepo oder `None`.

        Moegliche Fehlerfaelle:
        - Keine; nicht aufloesbare Referenzen liefern `None`.

        Wichtige interne Logik:
        - Bevorzugt die GitHub-Repository-ID als stabilen Schluessel gegenueber sichtbaren Namen.
        """

        repo_id = int(repo_ref.get("repo_id") or 0)
        for repository in self._window.get_remote_repositories():
            if repository.repo_id == repo_id:
                return repository
        return None

    def _resolve_target_visibility(self, action_name: str) -> str:
        """
        Uebersetzt einen technischen Kontextaktionsnamen in die Ziel-Sichtbarkeit.

        Eingabeparameter:
        - action_name: Technischer Aktionsname wie `set_public` oder `set_private`.

        Rueckgabewerte:
        - Ziel-Sichtbarkeit als `public`, `private` oder Leerstring bei unbekannten Aktionen.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte Aktionen liefern nur einen leeren String.

        Wichtige interne Logik:
        - Haelt die Menuebezeichnungen und die fachliche Zielabbildung entkoppelt.
        """

        mapping = {
            "set_public": "public",
            "set_private": "private",
        }
        return mapping.get(action_name, "")

    def _build_status_snapshot(self) -> StatusSnapshot:
        """
        Baut ein UI-taugliches Statusobjekt aus dem aktuellen Laufzeitstatus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - StatusSnapshot mit allen darzustellenden Werten.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Formatiert das Rate-Limit zentral, damit die UI keine Fachlogik enthaelt.
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

    def shutdown(self) -> None:
        """
        Wartet beim App-Shutdown auf laufende Remote- und Clone-Worker.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; das Herunterfahren bleibt defensiv.

        Wichtige interne Logik:
        - Verhindert Worker-Abbrueche waehrend Qt die zugehoerigen Objekte zerstoert.
        """

        if self._current_worker is not None and self._current_worker.isRunning():
            self._logger.event("app", "shutdown_wait_for_remote_load_worker", level=20)
            self._current_worker.wait()
        if self._clone_worker is not None and self._clone_worker.isRunning():
            self._logger.event("app", "shutdown_wait_for_clone_worker", level=20)
            self._clone_worker.wait()
        if self._visibility_worker is not None and self._visibility_worker.isRunning():
            self._logger.event("app", "shutdown_wait_for_remote_visibility_worker", level=20)
            self._visibility_worker.wait()
