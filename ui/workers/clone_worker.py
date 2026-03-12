"""Worker-Thread fuer Batch-Clone-Vorgaenge."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from models.repo_models import RemoteRepo
from services.clone_service import CloneService


class CloneWorker(QThread):
    """Fuehrt Batch-Clones ausserhalb des UI-Threads aus."""

    clone_finished = Signal(list)
    clone_failed = Signal(str)

    def __init__(self, clone_service: CloneService, repositories: list[RemoteRepo], target_root: Path, job_id: str) -> None:
        """
        Speichert alle noetigen Eingaben fuer den spaeteren Clone-Lauf.

        Eingabeparameter:
        - clone_service: Fachservice fuer die Clone-Orchestrierung.
        - repositories: Ausgewaehlte Remote-Repositories.
        - target_root: Lokaler Zielordner fuer die Clones.
        - job_id: Uebergeordnete Job-ID fuer alle Clone-Ergebnisse.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Hellt nur Transportzustand; die Ergebnisverarbeitung bleibt im Controller.
        """

        super().__init__()
        self._clone_service = clone_service
        self._repositories = repositories
        self._target_root = target_root
        self._job_id = job_id

    def run(self) -> None:
        """
        Fuehrt den Batch-Clone im Hintergrundthread aus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Unerwartete Gesamtfehler werden als String-Signal zur UI zurueckgereicht.

        Wichtige interne Logik:
        - Einzelne Repo-Fehler werden vom Service bereits in Ergebnisobjekte transformiert.
        """

        try:
            results = self._clone_service.clone_repositories(
                repositories=self._repositories,
                target_root=self._target_root,
                job_id=self._job_id,
            )
            self.clone_finished.emit(results)
        except Exception as error:  # noqa: BLE001
            self.clone_failed.emit(str(error))
