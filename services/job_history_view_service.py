"""Lesende Aufbereitung der Job- und Aktionshistorie fuer kompakte UI-Ansichten."""

from __future__ import annotations

from db.job_log_repository import JobLogRepository


class JobHistoryViewService:
    """Bereitet die juengste Repository-Historie aus `igitty_jobs.db` fuer die UI auf."""

    def __init__(self, job_log_repository: JobLogRepository) -> None:
        """
        Initialisiert den Service mit Zugriff auf die Job-Datenbank.

        Eingabeparameter:
        - job_log_repository: Repository fuer Jobs, Clone- und Aktionshistorie.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Service bleibt rein lesend und formatiert nur bereits gespeicherte Historie.
        """

        self._job_log_repository = job_log_repository

    def build_repo_history(self, repo_name: str, remote_url: str = "", local_path: str = "") -> list[str]:
        """
        Baut eine kompakte Job-Historie fuer ein einzelnes Repository.

        Eingabeparameter:
        - repo_name: Fachlicher Repository-Name.
        - remote_url: Optionale Remote-URL fuer praeziseres Matching.
        - local_path: Optionaler lokaler Pfad.

        Rueckgabewerte:
        - Liste formatierter Textzeilen fuer die UI.

        Moegliche Fehlerfaelle:
        - Fehlende Historie liefert eine stabile Platzhalterzeile statt eines Fehlers.

        Wichtige interne Logik:
        - Die Darstellung ist absichtlich kompakt und zeigt die juengsten Aktivitaeten
          in einer fuer Diagnose und Nachvollziehbarkeit schnell lesbaren Reihenfolge.
        """

        items = self._job_log_repository.fetch_recent_activity(
            repo_name=repo_name,
            remote_url=remote_url,
            local_path=local_path,
            limit=8,
        )
        if not items:
            return ["Keine Job-Historie fuer dieses Repository vorhanden."]

        return [
            f"{item.timestamp or '-'} | {item.action_type} | {item.status} | {item.message or '-'}"
            for item in items
        ]
