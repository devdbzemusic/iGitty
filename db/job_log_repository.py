"""Repository fuer einfache Job-Log-Eintraege."""

from __future__ import annotations

from pathlib import Path

from db.sqlite_manager import sqlite_connection
from models.job_models import ActionRecord, CloneRecord, JobLogEntry


class JobLogRepository:
    """Kapselt die persistente Speicherung von Job-Eintraegen."""

    def __init__(self, database_file: Path) -> None:
        """
        Speichert den Datenbankpfad fuer spaetere Schreibvorgaenge.

        Eingabeparameter:
        - database_file: Pfad zur `igitty_jobs.db`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine direkte Validierung; Fehler treten erst beim Zugriff auf.

        Wichtige interne Logik:
        - Die Klasse bleibt bewusst schmal, weil der MVP vor allem Nachvollziehbarkeit braucht.
        """

        self._database_file = database_file

    def add_entry(self, entry: JobLogEntry) -> None:
        """
        Schreibt einen einzelnen Job-Eintrag in die Datenbank.

        Eingabeparameter:
        - entry: Fachlich bereits befuellter Logeintrag.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Doppelte `job_id` verletzt den Primaerschluessel.

        Wichtige interne Logik:
        - Das SQL bleibt zentral gekapselt, damit spaetere Schema-Erweiterungen lokal bleiben.
        """

        with sqlite_connection(self._database_file) as connection:
            connection.execute(
                """
                INSERT INTO jobs (job_id, action_type, source_type, repo_name, status, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.job_id,
                    entry.action_type,
                    entry.source_type,
                    entry.repo_name,
                    entry.status,
                    entry.message,
                ),
            )

    def add_clone_record(self, record: CloneRecord) -> None:
        """
        Schreibt das Ergebnis eines Clone-Vorgangs in die Clone-Historie.

        Eingabeparameter:
        - record: Vollstaendig befuellter Clone-Datensatz.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Einfuegen des Historieneintrags.

        Wichtige interne Logik:
        - Trennt die feingranulare Clone-Historie von der allgemeinen Job-Uebersicht.
        """

        with sqlite_connection(self._database_file) as connection:
            connection.execute(
                """
                INSERT INTO clone_history (job_id, repo_id, repo_name, remote_url, local_path, status, message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.repo_id,
                    record.repo_name,
                    record.remote_url,
                    record.local_path,
                    record.status,
                    record.message,
                ),
            )

    def has_successful_clone(self, repo_name: str, remote_url: str = "", repo_id: int = 0) -> bool:
        """
        Prueft, ob fuer ein Repository bereits ein erfolgreicher Clone protokolliert ist.

        Eingabeparameter:
        - repo_name: Name des zu pruefenden Repositories.
        - remote_url: Clone-URL oder HTML-URL des Repositories.
        - repo_id: GitHub-Repository-ID, falls bekannt.

        Rueckgabewerte:
        - `True`, wenn mindestens ein erfolgreicher Clone-Eintrag existiert.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen der Historie.

        Wichtige interne Logik:
        - Die Abfrage verwendet zusaetzlich `remote_url` und `repo_id`, damit Namensgleichheit allein nicht ausreicht.
        """

        with sqlite_connection(self._database_file) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM clone_history
                WHERE status = 'success'
                  AND (
                    repo_name = ?
                    OR (? <> '' AND remote_url = ?)
                    OR (? <> 0 AND repo_id = ?)
                  )
                LIMIT 1
                """,
                (repo_name, remote_url, remote_url, repo_id, repo_id),
            ).fetchone()
        return row is not None

    def add_action_record(self, record: ActionRecord) -> None:
        """
        Schreibt ein allgemeines Aktionsresultat in die Verlaufstabelle.

        Eingabeparameter:
        - record: Vollstaendig befuelltes Ergebnisobjekt einer Aktion.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Schreiben des Verlaufs.

        Wichtige interne Logik:
        - Vereinheitlicht Commit-, Push-, Delete- und Struktur-Logs in einem Schema.
        """

        with sqlite_connection(self._database_file) as connection:
            connection.execute(
                """
                INSERT INTO action_history
                (job_id, action_type, repo_name, source_type, local_path, remote_url, status, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.action_type,
                    record.repo_name,
                    record.source_type,
                    record.local_path,
                    record.remote_url,
                    record.status,
                    record.message,
                ),
            )
