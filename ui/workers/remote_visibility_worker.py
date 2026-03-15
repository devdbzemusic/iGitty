"""Worker-Thread fuer das Aendern der Remote-Sichtbarkeit."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from models.repo_models import RemoteRepo
from services.remote_visibility_service import RemoteVisibilityService


class RemoteVisibilityWorker(QThread):
    """Fuehrt die Aenderung der GitHub-Sichtbarkeit ausserhalb des UI-Threads aus."""

    finished_with_result = Signal(object, object)
    failed = Signal(str)

    def __init__(
        self,
        service: RemoteVisibilityService,
        repository: RemoteRepo,
        target_visibility: str,
        job_id: str,
    ) -> None:
        """
        Speichert Service, Ziel-Repository und gewuenschten Sichtbarkeitszustand.

        Eingabeparameter:
        - service: Fachservice fuer die Sichtbarkeitsaenderung.
        - repository: Betroffenes Remote-Repository.
        - target_visibility: Gewuenschter Zielwert `public` oder `private`.
        - job_id: Uebergeordnete Job-ID fuer Historie und Logging.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Worker transportiert rohe Ergebnisobjekte in den Controller, damit dort
          UI, Logging und Historie an einer zentralen Stelle zusammenlaufen.
        """

        super().__init__()
        self._service = service
        self._repository = repository
        self._target_visibility = target_visibility
        self._job_id = job_id

    def run(self) -> None:
        """
        Fuehrt die Sichtbarkeitsaenderung im Hintergrundthread aus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Unerwartete Fehler ausserhalb des Services werden als String-Signal emittiert.

        Wichtige interne Logik:
        - Regulaere fachliche Fehler werden bereits im Service in ein Aktionsergebnis
          umgewandelt und landen deshalb nicht im `failed`-Signal.
        """

        try:
            result, updated_repository = self._service.change_visibility(
                self._repository,
                self._target_visibility,
                self._job_id,
            )
            self.finished_with_result.emit(result, updated_repository)
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))
