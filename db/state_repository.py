"""SQLite-Zugriffsschicht fuer persistente Repository-Zustaende."""

from __future__ import annotations

from pathlib import Path

from db.sqlite_manager import sqlite_connection
from models.state_models import (
    RepoFileDeltaStats,
    RepoFileState,
    RepoStatusEvent,
    RepositoryState,
)


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
        Legt einen Repository-Zustand neu an oder aktualisiert ihn ueber `repo_key` und Pfade.

        Eingabeparameter:
        - repository: Vollstaendig vorbereiteter Repository-Zustand inklusive Statusfeldern.

        Rueckgabewerte:
        - Das persistierte Repository inklusive zugewiesener Datenbank-ID.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler bei Insert oder Update.

        Wichtige interne Logik:
        - Repository-Stammdaten und volatile Statusdaten werden in einer Transaktion
          konsistent ueber `repositories` und `repo_status` aktualisiert.
        """

        repository.repo_key = repository.repo_key or self._build_repo_key(repository)
        repository.last_seen_at = repository.last_seen_at or repository.last_local_scan_at or repository.last_checked_at
        repository.last_checked_at = repository.last_checked_at or repository.last_seen_at or repository.last_local_scan_at
        repository.last_changed_at = repository.last_changed_at or repository.last_checked_at
        repository.visibility = repository.visibility or repository.remote_visibility or "unknown"
        repository.default_branch = repository.default_branch or repository.current_branch or ""

        with sqlite_connection(self._database_file) as connection:
            existing = connection.execute(
                """
                SELECT id, status_hash, scan_fingerprint, is_missing, last_changed_at
                FROM repositories
                WHERE repo_key = ?
                   OR (? <> '' AND local_path = ?)
                LIMIT 1
                """,
                (repository.repo_key, repository.local_path, repository.local_path),
            ).fetchone()

            if existing is not None:
                repository.id = int(existing["id"])
                previous_status_hash = str(existing["status_hash"] or "")
                previous_scan_fingerprint = str(existing["scan_fingerprint"] or "")
                if (
                    previous_status_hash != (repository.status_hash or "")
                    or previous_scan_fingerprint != (repository.scan_fingerprint or "")
                    or bool(existing["is_missing"])
                ):
                    repository.last_changed_at = repository.last_checked_at
                else:
                    repository.last_changed_at = str(existing["last_changed_at"] or repository.last_changed_at)
            payload = (
                repository.repo_key,
                repository.name,
                repository.source_type,
                repository.local_path,
                repository.remote_url,
                repository.github_repo_id,
                repository.default_branch,
                repository.visibility,
                int(repository.is_archived),
                int(repository.is_deleted),
                int(repository.is_missing),
                repository.last_seen_at,
                repository.last_changed_at,
                repository.last_checked_at,
                repository.scan_fingerprint,
                repository.status_hash,
                int(repository.is_git_repo),
                repository.current_branch,
                repository.head_commit,
                repository.head_commit_date,
                int(repository.has_remote),
                repository.remote_name,
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
                        repo_key,
                        name,
                        source_type,
                        local_path,
                        remote_url,
                        github_repo_id,
                        default_branch,
                        visibility,
                        is_archived,
                        is_deleted,
                        is_missing,
                        last_seen_at,
                        last_changed_at,
                        last_checked_at,
                        scan_fingerprint,
                        status_hash,
                        is_git_repo,
                        current_branch,
                        head_commit,
                        head_commit_date,
                        has_remote,
                        remote_name,
                        remote_host,
                        remote_owner,
                        remote_repo_name,
                        remote_exists_online,
                        remote_visibility,
                        status,
                        last_local_scan_at,
                        last_remote_check_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
                repository.id = int(cursor.lastrowid)
            else:
                connection.execute(
                    """
                    UPDATE repositories
                    SET repo_key = ?,
                        name = ?,
                        source_type = ?,
                        local_path = ?,
                        remote_url = ?,
                        github_repo_id = ?,
                        default_branch = ?,
                        visibility = ?,
                        is_archived = ?,
                        is_deleted = ?,
                        is_missing = ?,
                        last_seen_at = ?,
                        last_changed_at = ?,
                        last_checked_at = ?,
                        scan_fingerprint = ?,
                        status_hash = ?,
                        is_git_repo = ?,
                        current_branch = ?,
                        head_commit = ?,
                        head_commit_date = ?,
                        has_remote = ?,
                        remote_name = ?,
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

            connection.execute(
                """
                INSERT INTO repo_status (
                    repo_id,
                    exists_local,
                    exists_remote,
                    git_initialized,
                    remote_configured,
                    has_uncommitted_changes,
                    ahead_count,
                    behind_count,
                    is_diverged,
                    auth_state,
                    sync_state,
                    health_state,
                    dirty_hint,
                    needs_rescan,
                    last_checked_at,
                    status_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo_id) DO UPDATE SET
                    exists_local = excluded.exists_local,
                    exists_remote = excluded.exists_remote,
                    git_initialized = excluded.git_initialized,
                    remote_configured = excluded.remote_configured,
                    has_uncommitted_changes = excluded.has_uncommitted_changes,
                    ahead_count = excluded.ahead_count,
                    behind_count = excluded.behind_count,
                    is_diverged = excluded.is_diverged,
                    auth_state = excluded.auth_state,
                    sync_state = excluded.sync_state,
                    health_state = excluded.health_state,
                    dirty_hint = excluded.dirty_hint,
                    needs_rescan = excluded.needs_rescan,
                    last_checked_at = excluded.last_checked_at,
                    status_hash = excluded.status_hash
                """,
                (
                    int(repository.id or 0),
                    int(repository.exists_local),
                    None if repository.exists_remote is None else int(repository.exists_remote),
                    int(repository.git_initialized),
                    int(repository.remote_configured),
                    int(repository.has_uncommitted_changes),
                    repository.ahead_count,
                    repository.behind_count,
                    int(repository.is_diverged),
                    repository.auth_state,
                    repository.sync_state,
                    repository.health_state,
                    int(repository.dirty_hint),
                    int(repository.needs_rescan),
                    repository.last_checked_at,
                    repository.status_hash,
                ),
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
                """
                SELECT repositories.*, repo_status.*
                FROM repositories
                LEFT JOIN repo_status ON repo_status.repo_id = repositories.id
                WHERE repositories.local_path = ?
                LIMIT 1
                """,
                (local_path,),
            ).fetchone()
        return self._map_repository(row) if row else None

    def fetch_repositories_by_root_path(self, root_path: str) -> list[RepositoryState]:
        """
        Liest alle bekannten lokalen Repository-Zustaende unterhalb eines Wurzelpfads.

        Eingabeparameter:
        - root_path: Basisverzeichnis eines lokalen Scan-Bereichs.

        Rueckgabewerte:
        - Liste aller passenden persistierten Repository-Zustaende.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Lesen.

        Wichtige interne Logik:
        - Die Methode bildet die Grundlage fuer Delta-Scans, weil bekannte Repositories
          ohne erneute Tiefeninspektion mit ihrem gespeicherten Fingerprint abgeglichen werden koennen.
        """

        normalized_root = str(Path(root_path))
        prefix = f"{normalized_root.rstrip('/\\')}%"
        with sqlite_connection(self._database_file) as connection:
            rows = connection.execute(
                """
                SELECT repositories.*, repo_status.*
                FROM repositories
                LEFT JOIN repo_status ON repo_status.repo_id = repositories.id
                WHERE repositories.source_type IN ('local', 'paired')
                  AND repositories.local_path LIKE ?
                ORDER BY repositories.local_path
                """,
                (prefix,),
            ).fetchall()
        return [self._map_repository(row) for row in rows]

    def touch_repository_seen(self, repository_id: int, seen_at: str, scan_fingerprint: str) -> RepositoryState | None:
        """
        Aktualisiert fuer ein unveraendertes Repository nur Sichtungs- und Check-Zeitstempel.

        Eingabeparameter:
        - repository_id: ID des bekannten Repositories.
        - seen_at: Zeitstempel des aktuellen Refresh-Laufs.
        - scan_fingerprint: Neu berechneter leichter Fingerprint.

        Rueckgabewerte:
        - Aktualisierter Repository-Zustand oder `None`, wenn die ID unbekannt ist.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler bei Update oder Folge-Lesezugriff.

        Wichtige interne Logik:
        - Die Methode vermeidet einen Tiefenscan, haelt aber Soft-Delete- und
          `needs_rescan`-Marker trotzdem sauber aktuell.
        """

        with sqlite_connection(self._database_file) as connection:
            connection.execute(
                """
                UPDATE repositories
                SET is_missing = 0,
                    is_deleted = 0,
                    last_seen_at = ?,
                    last_checked_at = ?,
                    last_local_scan_at = ?,
                    scan_fingerprint = ?
                WHERE id = ?
                """,
                (seen_at, seen_at, seen_at, scan_fingerprint, repository_id),
            )
            connection.execute(
                """
                UPDATE repo_status
                SET exists_local = 1,
                    needs_rescan = 0,
                    last_checked_at = ?
                WHERE repo_id = ?
                """,
                (seen_at, repository_id),
            )
            row = connection.execute(
                """
                SELECT repositories.*, repo_status.*
                FROM repositories
                LEFT JOIN repo_status ON repo_status.repo_id = repositories.id
                WHERE repositories.id = ?
                LIMIT 1
                """,
                (repository_id,),
            ).fetchone()
        return self._map_repository(row) if row else None

    def mark_missing_repositories(self, root_path: str, seen_local_paths: set[str], seen_at: str) -> int:
        """
        Markiert bekannte lokale Repositories unterhalb eines Roots als fehlend, wenn sie nicht gesehen wurden.

        Eingabeparameter:
        - root_path: Basisverzeichnis des aktuellen Refresh-Laufs.
        - seen_local_paths: Menge aller in diesem Lauf gesehenen lokalen Repository-Pfade.
        - seen_at: Zeitstempel des aktuellen Refresh-Laufs.

        Rueckgabewerte:
        - Anzahl der als fehlend markierten Repositories.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler bei Auswahl oder Update.

        Wichtige interne Logik:
        - Die Methode implementiert den geforderten Soft-Delete-/Missing-Marker statt
          Repositories bei temporaer verschwundenen Pfaden hart aus der DB zu loeschen.
        """

        normalized_root = str(Path(root_path))
        prefix = f"{normalized_root.rstrip('/\\')}%"
        missing_count = 0
        with sqlite_connection(self._database_file) as connection:
            rows = connection.execute(
                """
                SELECT id, local_path
                FROM repositories
                WHERE source_type IN ('local', 'paired')
                  AND local_path LIKE ?
                """,
                (prefix,),
            ).fetchall()
            for row in rows:
                local_path = str(row["local_path"] or "")
                if local_path in seen_local_paths:
                    continue
                repository_id = int(row["id"])
                connection.execute(
                    """
                    UPDATE repositories
                    SET is_missing = 1,
                        is_deleted = 1,
                        last_checked_at = ?
                    WHERE id = ?
                    """,
                    (seen_at, repository_id),
                )
                connection.execute(
                    """
                    UPDATE repo_status
                    SET exists_local = 0,
                        needs_rescan = 1,
                        health_state = 'missing',
                        last_checked_at = ?
                    WHERE repo_id = ?
                    """,
                    (seen_at, repository_id),
                )
                missing_count += 1
        return missing_count

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
        - Die Methode bleibt aus Rueckwaertskompatibilitaet erhalten, delegiert aber intern
          auf das neue Delta-Update, damit bestehende Aufrufer keinen Funktionsverlust haben.
        """

        self.update_repo_files_delta(repo_id, files)

    def update_repo_files_delta(self, repo_id: int, files: list[RepoFileState]) -> RepoFileDeltaStats:
        """
        Aktualisiert den Dateiindex eines Repositories per Delta statt Vollersetzung.

        Eingabeparameter:
        - repo_id: Zugehoerige Repository-ID.
        - files: Vollstaendige Dateiliste des aktuellen Tiefenscans.

        Rueckgabewerte:
        - Delta-Statistik mit Insert-, Update-, Delete- und Unchanged-Anzahlen.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler bei den Delta-Operationen.

        Wichtige interne Logik:
        - Neue Dateien werden eingefuegt, geaenderte Dateien aktualisiert, verschwundene
          Dateien nur als geloescht markiert und unveraenderte Eintraege bleiben unangetastet.
        """

        stats = RepoFileDeltaStats()
        current_files_by_path = {
            file_state.relative_path: file_state
            for file_state in files
        }
        scan_timestamp = ""
        if files:
            first_file = files[0]
            scan_timestamp = first_file.last_seen_at or first_file.last_seen_scan_at

        with sqlite_connection(self._database_file) as connection:
            rows = connection.execute(
                """
                SELECT id, relative_path, path_type, size_bytes, modified_at, content_hash,
                       is_tracked, is_ignored, is_deleted
                FROM repo_files
                WHERE repo_id = ?
                """,
                (repo_id,),
            ).fetchall()
            existing_by_path = {str(row["relative_path"]): row for row in rows}

            for relative_path, file_state in current_files_by_path.items():
                file_state.repo_id = repo_id
                existing_row = existing_by_path.get(relative_path)
                if existing_row is None:
                    connection.execute(
                        """
                        INSERT INTO repo_files (
                            repo_id,
                            relative_path,
                            path_type,
                            size_bytes,
                            modified_at,
                            content_hash,
                            is_tracked,
                            is_ignored,
                            is_deleted,
                            last_seen_at,
                            last_seen_scan_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            repo_id,
                            file_state.relative_path,
                            file_state.path_type,
                            file_state.size_bytes,
                            file_state.modified_at,
                            file_state.content_hash,
                            int(file_state.is_tracked),
                            int(file_state.is_ignored),
                            int(file_state.is_deleted),
                            file_state.last_seen_at or file_state.last_seen_scan_at,
                            file_state.last_seen_scan_at or file_state.last_seen_at,
                        ),
                    )
                    stats.inserted_count += 1
                    continue

                changed = (
                    str(existing_row["path_type"] or "file") != file_state.path_type
                    or int(existing_row["size_bytes"] or 0) != file_state.size_bytes
                    or str(existing_row["modified_at"] or "") != file_state.modified_at
                    or str(existing_row["content_hash"] or "") != file_state.content_hash
                    or bool(existing_row["is_tracked"]) != file_state.is_tracked
                    or bool(existing_row["is_ignored"]) != file_state.is_ignored
                    or bool(existing_row["is_deleted"]) != file_state.is_deleted
                )
                if changed:
                    connection.execute(
                        """
                        UPDATE repo_files
                        SET path_type = ?,
                            size_bytes = ?,
                            modified_at = ?,
                            content_hash = ?,
                            is_tracked = ?,
                            is_ignored = ?,
                            is_deleted = ?,
                            last_seen_at = ?,
                            last_seen_scan_at = ?
                        WHERE id = ?
                        """,
                        (
                            file_state.path_type,
                            file_state.size_bytes,
                            file_state.modified_at,
                            file_state.content_hash,
                            int(file_state.is_tracked),
                            int(file_state.is_ignored),
                            int(file_state.is_deleted),
                            file_state.last_seen_at or file_state.last_seen_scan_at,
                            file_state.last_seen_scan_at or file_state.last_seen_at,
                            int(existing_row["id"]),
                        ),
                    )
                    stats.updated_count += 1
                else:
                    stats.unchanged_count += 1

            seen_paths = set(current_files_by_path)
            for relative_path, existing_row in existing_by_path.items():
                if relative_path in seen_paths:
                    continue
                connection.execute(
                    """
                    UPDATE repo_files
                    SET is_deleted = 1,
                        last_seen_at = ?,
                        last_seen_scan_at = ?
                    WHERE id = ?
                    """,
                    (scan_timestamp, scan_timestamp, int(existing_row["id"])),
                )
                stats.deleted_count += 1

        return stats

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
                INSERT INTO repo_status_events (repo_id, event_type, severity, message, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.repo_id,
                    event.event_type,
                    event.severity,
                    event.message,
                    event.payload_json,
                    event.created_at,
                ),
            )

    def create_scan_run(self, scan_type: str, started_at: str) -> int:
        """
        Legt einen neuen Eintrag fuer einen Scan-Lauf an.

        Eingabeparameter:
        - scan_type: Technischer Typ des Refresh-Laufs.
        - started_at: Startzeitpunkt des Laufs.

        Rueckgabewerte:
        - Datenbank-ID des angelegten Scan-Laufs.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Insert.

        Wichtige interne Logik:
        - Die Lauf-ID erlaubt spaeteres vervollstaendigen der Statistik erst nach Scan-Ende.
        """

        with sqlite_connection(self._database_file) as connection:
            cursor = connection.execute(
                "INSERT INTO scan_runs (scan_type, started_at) VALUES (?, ?)",
                (scan_type, started_at),
            )
            return int(cursor.lastrowid)

    def complete_scan_run(
        self,
        run_id: int,
        finished_at: str,
        duration_ms: int,
        changed_count: int,
        unchanged_count: int,
        error_count: int,
    ) -> None:
        """
        Vervollstaendigt die Statistik eines bereits angelegten Scan-Laufs.

        Eingabeparameter:
        - run_id: ID des zuvor angelegten Scan-Laufs.
        - finished_at: Endzeitpunkt des Laufs.
        - duration_ms: Gesamtdauer in Millisekunden.
        - changed_count: Anzahl veraenderter Repositories.
        - unchanged_count: Anzahl unveraenderter Repositories.
        - error_count: Anzahl registrierter Fehler.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler beim Update.

        Wichtige interne Logik:
        - Die zweistufige Speicherung vermeidet unvollstaendige Laufdaten nur bei erfolgreichem Scanstart.
        """

        with sqlite_connection(self._database_file) as connection:
            connection.execute(
                """
                UPDATE scan_runs
                SET finished_at = ?,
                    duration_ms = ?,
                    changed_count = ?,
                    unchanged_count = ?,
                    error_count = ?
                WHERE id = ?
                """,
                (finished_at, duration_ms, changed_count, unchanged_count, error_count, run_id),
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
            SELECT repo_id, event_type, severity, message, payload_json, created_at
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
            severity=str(row["severity"] or "info"),
            message=str(row["message"] or ""),
            payload_json=str(row["payload_json"] or ""),
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
                SELECT repo_id, event_type, severity, message, payload_json, created_at
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
                event_type=str(row["event_type"] or ""),
                severity=str(row["severity"] or "info"),
                message=str(row["message"] or ""),
                payload_json=str(row["payload_json"] or ""),
                created_at=str(row["created_at"] or ""),
            )
            for row in rows
        ]

    def _build_repo_key(self, repository: RepositoryState) -> str:
        """
        Erzeugt einen stabilen internen Schluessel fuer lokale, Remote- oder gemischte Repositories.

        Eingabeparameter:
        - repository: Zu persistierender Repository-Zustand.

        Rueckgabewerte:
        - Stabiler String-Schluessel fuer spaetere Upserts.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Lokale Repositories werden vorzugsweise ueber ihren Pfad identifiziert, Remote-Repositories
          ueber GitHub-ID oder URL, damit spaetere DB-first-Workflows keine reinen Namensschluessel nutzen muessen.
        """

        if repository.local_path:
            return f"local::{repository.local_path.lower()}"
        if repository.github_repo_id:
            return f"remote::{repository.github_repo_id}"
        if repository.remote_url:
            return f"remote_url::{repository.remote_url.lower()}"
        return f"repo::{repository.source_type}::{repository.name.lower()}"

    def _map_repository(self, row) -> RepositoryState:
        """
        Wandelt eine SQLite-Zeile in das fachliche RepositoryState-Modell um.

        Eingabeparameter:
        - row: SQLite-Row aus `repositories` plus optional `repo_status`.

        Rueckgabewerte:
        - Vollstaendig gemappte RepositoryState-Instanz.

        Moegliche Fehlerfaelle:
        - Fehlende Spalten wuerden als `KeyError` sichtbar werden.

        Wichtige interne Logik:
        - Das Mapping zentralisiert Bool- und Null-Konvertierung fuer alle Leser.
        """

        row_keys = set(row.keys())
        return RepositoryState(
            id=int(row["id"]),
            repo_key=str(row["repo_key"] or ""),
            name=str(row["name"] or ""),
            source_type=str(row["source_type"] or "local"),
            local_path=str(row["local_path"] or ""),
            remote_url=str(row["remote_url"] or ""),
            github_repo_id=int(row["github_repo_id"] or 0),
            default_branch=str(row["default_branch"] or ""),
            visibility=str(row["visibility"] or "unknown"),
            is_archived=bool(row["is_archived"]),
            is_deleted=bool(row["is_deleted"]),
            is_missing=bool(row["is_missing"]),
            last_seen_at=str(row["last_seen_at"] or ""),
            last_changed_at=str(row["last_changed_at"] or ""),
            last_checked_at=str(row["last_checked_at"] or ""),
            scan_fingerprint=str(row["scan_fingerprint"] or ""),
            status_hash=str(row["status_hash"] or ""),
            is_git_repo=bool(row["is_git_repo"]),
            current_branch=str(row["current_branch"] or ""),
            head_commit=str(row["head_commit"] or ""),
            head_commit_date=str(row["head_commit_date"] or ""),
            has_remote=bool(row["has_remote"]),
            remote_name=str(row["remote_name"] or ""),
            remote_host=str(row["remote_host"] or ""),
            remote_owner=str(row["remote_owner"] or ""),
            remote_repo_name=str(row["remote_repo_name"] or ""),
            remote_exists_online=None if row["remote_exists_online"] is None else int(row["remote_exists_online"]),
            remote_visibility=str(row["remote_visibility"] or "unknown"),
            exists_local=bool(row["exists_local"]) if "exists_local" in row_keys and row["exists_local"] is not None else True,
            exists_remote=None if "exists_remote" not in row_keys or row["exists_remote"] is None else bool(row["exists_remote"]),
            git_initialized=bool(row["git_initialized"]) if "git_initialized" in row_keys and row["git_initialized"] is not None else bool(row["is_git_repo"]),
            remote_configured=bool(row["remote_configured"]) if "remote_configured" in row_keys and row["remote_configured"] is not None else bool(row["has_remote"]),
            has_uncommitted_changes=bool(row["has_uncommitted_changes"]) if "has_uncommitted_changes" in row_keys and row["has_uncommitted_changes"] is not None else False,
            ahead_count=int(row["ahead_count"] or 0) if "ahead_count" in row_keys else 0,
            behind_count=int(row["behind_count"] or 0) if "behind_count" in row_keys else 0,
            is_diverged=bool(row["is_diverged"]) if "is_diverged" in row_keys and row["is_diverged"] is not None else False,
            auth_state=str(row["auth_state"] or "unknown") if "auth_state" in row_keys else "unknown",
            sync_state=str(row["sync_state"] or row["status"] or "NOT_INITIALIZED") if "sync_state" in row_keys else str(row["status"] or "NOT_INITIALIZED"),
            health_state=str(row["health_state"] or "unknown") if "health_state" in row_keys else "unknown",
            dirty_hint=bool(row["dirty_hint"]) if "dirty_hint" in row_keys and row["dirty_hint"] is not None else False,
            needs_rescan=bool(row["needs_rescan"]) if "needs_rescan" in row_keys and row["needs_rescan"] is not None else True,
            status=str(row["status"] or "NOT_INITIALIZED"),
            last_local_scan_at=str(row["last_local_scan_at"] or ""),
            last_remote_check_at=str(row["last_remote_check_at"] or ""),
        )
