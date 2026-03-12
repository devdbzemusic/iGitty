"""SQLite-Zugriffsschicht fuer persistente Repository-Zustaende."""

from __future__ import annotations

from pathlib import Path

from db.sqlite_manager import sqlite_connection
from models.state_models import RepoFileState, RepositoryState, RepoStatusEvent


class StateRepository:
    """Kapselt alle Schreib- und Lesezugriffe auf `igitty_state.db`."""

    def __init__(self, database_file: Path) -> None:
        """
        Speichert den Zielpfad der State-Datenbank fuer spaetere Zugriffe.

        Eingabeparameter:
        - database_file: Vollstaendiger Pfad zur Datei `igitty_state.db`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Die Klasse haelt selbst keine offene Verbindung, damit jeder Zugriff sauber
          transaktional und kurzlebig bleibt.
        """

        self._database_file = database_file

    def upsert_repository(self, repository: RepositoryState) -> RepositoryState:
        """
        Legt einen Repository-Zustand neu an oder aktualisiert ihn ueber `local_path`.

        Eingabeparameter:
        - repository: Vollstaendig vorbereiteter Repository-Zustand.

        Rueckgabewerte:
        - Das persistierte Repository inklusive zugewiesener Datenbank-ID.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler bei Insert oder Update.

        Wichtige interne Logik:
        - `local_path` ist der stabile Schluessel fuer lokale Repositories und erlaubt
          wiederholte Scans ohne Duplikate.
        """

        with sqlite_connection(self._database_file) as connection:
            existing = connection.execute(
                "SELECT id FROM repositories WHERE local_path = ?",
                (repository.local_path,),
            ).fetchone()

            payload = (
                repository.name,
                repository.local_path,
                int(repository.is_git_repo),
                repository.current_branch,
                repository.head_commit,
                repository.head_commit_date,
                int(repository.has_remote),
                repository.remote_name,
                repository.remote_url,
                repository.remote_host,
                repository.remote_owner,
                repository.remote_repo_name,
                repository.remote_exists_online,
                repository.remote_visibility,
                repository.status,
                repository.last_local_scan_at,
                repository.last_remote_check_at,
            )

            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO repositories (
                        name,
                        local_path,
                        is_git_repo,
                        current_branch,
                        head_commit,
                        head_commit_date,
                        has_remote,
                        remote_name,
                        remote_url,
                        remote_host,
                        remote_owner,
                        remote_repo_name,
                        remote_exists_online,
                        remote_visibility,
                        status,
                        last_local_scan_at,
                        last_remote_check_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
                repository.id = int(cursor.lastrowid)
                return repository

            repository.id = int(existing["id"])
            connection.execute(
                """
                UPDATE repositories
                SET name = ?,
                    local_path = ?,
                    is_git_repo = ?,
                    current_branch = ?,
                    head_commit = ?,
                    head_commit_date = ?,
                    has_remote = ?,
                    remote_name = ?,
                    remote_url = ?,
                    remote_host = ?,
                    remote_owner = ?,
                    remote_repo_name = ?,
                    remote_exists_online = ?,
                    remote_visibility = ?,
                    status = ?,
                    last_local_scan_at = ?,
                    last_remote_check_at = ?
                WHERE id = ?
                """,
                (*payload, repository.id),
            )
            return repository

    def fetch_repository_by_local_path(self, local_path: str) -> RepositoryState | None:
        """
        Liest einen Repository-Zustand ueber seinen lokalen Pfad aus.

        Eingabeparameter:
        - local_path: Vollstaendiger Dateisystempfad des Repositories.

        Rueckgabewerte:
        - Persistierter Zustand oder `None`, wenn noch kein Indexeintrag existiert.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Lesen.

        Wichtige interne Logik:
        - Der Lookup wird fuer Push-Vorpruefungen und UI-Anreicherung verwendet.
        """

        with sqlite_connection(self._database_file) as connection:
            row = connection.execute(
                "SELECT * FROM repositories WHERE local_path = ?",
                (local_path,),
            ).fetchone()
        return self._map_repository(row) if row else None

    def replace_repo_files(self, repo_id: int, files: list[RepoFileState]) -> None:
        """
        Ersetzt die indexierten Dateieintraege eines Repositories komplett.

        Eingabeparameter:
        - repo_id: Zugehoerige Repository-ID.
        - files: Vollstaendige neue Dateiliste des letzten Scans.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler bei Delete oder Bulk-Insert.

        Wichtige interne Logik:
        - Ein kompletter Replace haelt den MVP einfach und vermeidet komplizierte Delta-Logik.
        """

        with sqlite_connection(self._database_file) as connection:
            connection.execute("DELETE FROM repo_files WHERE repo_id = ?", (repo_id,))
            connection.executemany(
                """
                INSERT INTO repo_files (
                    repo_id,
                    relative_path,
                    size_bytes,
                    modified_at,
                    is_tracked,
                    is_ignored,
                    last_seen_scan_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        file_state.repo_id,
                        file_state.relative_path,
                        file_state.size_bytes,
                        file_state.modified_at,
                        int(file_state.is_tracked),
                        int(file_state.is_ignored),
                        file_state.last_seen_scan_at,
                    )
                    for file_state in files
                ],
            )

    def add_status_event(self, event: RepoStatusEvent) -> None:
        """
        Schreibt ein neues Statusereignis fuer ein Repository in die Event-Tabelle.

        Eingabeparameter:
        - event: Vollstaendig vorbereitetes Ereignis.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Insert.

        Wichtige interne Logik:
        - Ereignisse bleiben append-only und dienen als technische Auditspur fuer den neuen State-Layer.
        """

        with sqlite_connection(self._database_file) as connection:
            connection.execute(
                """
                INSERT INTO repo_status_events (repo_id, event_type, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event.repo_id, event.event_type, event.message, event.created_at),
            )

    def fetch_latest_event(self, repo_id: int, event_type: str | None = None) -> RepoStatusEvent | None:
        """
        Liest das neueste Statusereignis eines Repositories optional gefiltert nach Typ.

        Eingabeparameter:
        - repo_id: Zugehoerige Repository-ID.
        - event_type: Optionaler Ereignistyp fuer die Einschraenkung.

        Rueckgabewerte:
        - Neuester Event-Eintrag oder `None`.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Lesen.

        Wichtige interne Logik:
        - Die Methode wird in Tests und kuenftigen Detailansichten fuer schnelle Diagnosen genutzt.
        """

        query = """
            SELECT repo_id, event_type, message, created_at
            FROM repo_status_events
            WHERE repo_id = ?
        """
        parameters: list[object] = [repo_id]
        if event_type:
            query += " AND event_type = ?"
            parameters.append(event_type)
        query += " ORDER BY created_at DESC, id DESC LIMIT 1"

        with sqlite_connection(self._database_file) as connection:
            row = connection.execute(query, parameters).fetchone()

        if row is None:
            return None
        return RepoStatusEvent(
            repo_id=int(row["repo_id"]),
            event_type=str(row["event_type"]),
            message=str(row["message"] or ""),
            created_at=str(row["created_at"]),
        )

    def fetch_recent_events(self, repo_id: int, limit: int = 5) -> list[RepoStatusEvent]:
        """
        Liest die juengsten Statusereignisse eines Repositories in absteigender Reihenfolge.

        Eingabeparameter:
        - repo_id: Zugehoerige Repository-ID.
        - limit: Maximale Anzahl zurueckzugebender Ereignisse.

        Rueckgabewerte:
        - Liste der neuesten Statusereignisse.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Lesen.

        Wichtige interne Logik:
        - Die Methode dient dem Diagnosebereich im Repo-Kontext und bleibt bewusst kompakt.
        """

        with sqlite_connection(self._database_file) as connection:
            rows = connection.execute(
                """
                SELECT repo_id, event_type, message, created_at
                FROM repo_status_events
                WHERE repo_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (repo_id, limit),
            ).fetchall()

        return [
            RepoStatusEvent(
                repo_id=int(row["repo_id"]),
                event_type=str(row["event_type"]),
                message=str(row["message"] or ""),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def _map_repository(self, row) -> RepositoryState:
        """
        Wandelt eine SQLite-Zeile in das fachliche RepositoryState-Modell um.

        Eingabeparameter:
        - row: SQLite-Row aus der `repositories`-Tabelle.

        Rueckgabewerte:
        - Vollstaendig gemappte RepositoryState-Instanz.

        Moegliche Fehlerfaelle:
        - Fehlende Spalten wuerden als `KeyError` sichtbar werden.

        Wichtige interne Logik:
        - Das Mapping zentralisiert Bool- und Null-Konvertierung fuer alle Leser.
        """

        return RepositoryState(
            id=int(row["id"]),
            name=str(row["name"] or ""),
            local_path=str(row["local_path"] or ""),
            is_git_repo=bool(row["is_git_repo"]),
            current_branch=str(row["current_branch"] or ""),
            head_commit=str(row["head_commit"] or ""),
            head_commit_date=str(row["head_commit_date"] or ""),
            has_remote=bool(row["has_remote"]),
            remote_name=str(row["remote_name"] or ""),
            remote_url=str(row["remote_url"] or ""),
            remote_host=str(row["remote_host"] or ""),
            remote_owner=str(row["remote_owner"] or ""),
            remote_repo_name=str(row["remote_repo_name"] or ""),
            remote_exists_online=None if row["remote_exists_online"] is None else int(row["remote_exists_online"]),
            remote_visibility=str(row["remote_visibility"] or "unknown"),
            status=str(row["status"] or "NOT_INITIALIZED"),
            last_local_scan_at=str(row["last_local_scan_at"] or ""),
            last_remote_check_at=str(row["last_remote_check_at"] or ""),
        )
