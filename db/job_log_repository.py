"""Repository fuer einfache Job-Log-Eintraege."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from db.sqlite_manager import sqlite_connection
from models.evolution_models import RepositorySnapshot, RepositorySnapshotFile
from models.job_models import (
    ActionRecord,
    ActionSummary,
    CloneRecord,
    JobLogEntry,
    JobStepRecord,
    RepoSnapshotRecord,
)


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
                INSERT OR REPLACE INTO jobs
                (job_id, action_type, source_type, repo_name, repo_owner, local_path, remote_url, status, message, reversible_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.job_id,
                    entry.action_type,
                    entry.source_type,
                    entry.repo_name,
                    entry.repo_owner,
                    entry.local_path,
                    entry.remote_url,
                    entry.status,
                    entry.message,
                    int(entry.reversible_flag),
                ),
            )
        self.add_job_step(
            JobStepRecord(
                job_id=entry.job_id,
                step_name=entry.action_type,
                status=entry.status,
                message=entry.message,
                step_index=0,
            )
        )
        self.add_repo_snapshot(
            RepoSnapshotRecord(
                job_id=entry.job_id,
                action_type=entry.action_type,
                source_type=entry.source_type,
                repo_name=entry.repo_name,
                repo_owner=entry.repo_owner,
                local_path=entry.local_path,
                remote_url=entry.remote_url,
                status=entry.status,
                reversible_flag=entry.reversible_flag,
            )
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
                INSERT INTO clone_history (job_id, repo_id, repo_name, repo_owner, remote_url, local_path, status, message, reversible_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.repo_id,
                    record.repo_name,
                    record.repo_owner,
                    record.remote_url,
                    record.local_path,
                    record.status,
                    record.message,
                    int(record.reversible_flag),
                ),
            )
        self.add_job_step(
            JobStepRecord(
                job_id=record.job_id,
                step_name="clone",
                status=record.status,
                message=record.message,
                step_index=1,
            )
        )
        self.add_repo_snapshot(
            RepoSnapshotRecord(
                job_id=record.job_id,
                action_type="clone",
                source_type="remote",
                repo_name=record.repo_name,
                repo_owner=record.repo_owner,
                local_path=record.local_path,
                remote_url=record.remote_url,
                status=record.status,
                reversible_flag=record.reversible_flag,
            )
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
                (job_id, action_type, repo_name, source_type, repo_owner, local_path, remote_url, status, message, reversible_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.action_type,
                    record.repo_name,
                    record.source_type,
                    record.repo_owner,
                    record.local_path,
                    record.remote_url,
                    record.status,
                    record.message,
                    int(record.reversible_flag),
                ),
            )
        self.add_job_step(
            JobStepRecord(
                job_id=record.job_id,
                step_name=record.action_type,
                status=record.status,
                message=record.message,
                step_index=1,
            )
        )
        self.add_repo_snapshot(
            RepoSnapshotRecord(
                job_id=record.job_id,
                action_type=record.action_type,
                source_type=record.source_type,
                repo_name=record.repo_name,
                repo_owner=record.repo_owner,
                local_path=record.local_path,
                remote_url=record.remote_url,
                status=record.status,
                reversible_flag=record.reversible_flag,
            )
        )
        self._add_specialized_history_record(record)

    def add_job_step(self, record: JobStepRecord) -> None:
        """
        Schreibt einen feingranularen Schritt in `job_steps`.

        Eingabeparameter:
        - record: Vollstaendig befuellter Schritt innerhalb eines Jobs.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Einfuegen.

        Wichtige interne Logik:
        - Die Tabelle erlaubt spaeter detailliertere Ablaufanalysen, ohne bestehende Logs zu ersetzen.
        """

        with sqlite_connection(self._database_file) as connection:
            connection.execute(
                """
                INSERT INTO job_steps (job_id, step_index, step_name, status, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.step_index,
                    record.step_name,
                    record.status,
                    record.message,
                ),
            )

    def add_repo_snapshot(self, record: RepoSnapshotRecord) -> None:
        """
        Schreibt einen Repository-Snapshot fuer einen protokollierten Job.

        Eingabeparameter:
        - record: Snapshot mit Repository-Kontext und Reversibilitaetsflag.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Einfuegen.

        Wichtige interne Logik:
        - Die Tabelle liegt naeher an der urspruenglichen Prompt-Struktur und ergaenzt die Aktionshistorie um Kontextdaten.
        """

        with sqlite_connection(self._database_file) as connection:
            connection.execute(
                """
                INSERT INTO repo_snapshots
                (
                    job_id,
                    action_type,
                    source_type,
                    repo_name,
                    repo_owner,
                    local_path,
                    remote_url,
                    status,
                    reversible_flag,
                    snapshot_timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.action_type,
                    record.source_type,
                    record.repo_name,
                    record.repo_owner,
                    record.local_path,
                    record.remote_url,
                    record.status,
                    int(record.reversible_flag),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def add_repository_snapshot(self, snapshot: RepositorySnapshot) -> RepositorySnapshot:
        """
        Schreibt einen vollstaendigen Repository-Snapshot inklusive Dateimenge in die Datenbank.

        Eingabeparameter:
        - snapshot: Vollstaendig vorbereiteter Repository-Snapshot.

        Rueckgabewerte:
        - Persistierter Snapshot inklusive vergebener Datenbank-ID.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Schreiben des Snapshot-Kopfes oder der Dateieintraege.

        Wichtige interne Logik:
        - Die Methode nutzt bewusst dieselbe `repo_snapshots`-Tabelle wie die bestehenden
          Job-Snapshots und erweitert sie damit zu einer Zeitreise- und Evolutionsquelle.
        """

        with sqlite_connection(self._database_file) as connection:
            cursor = connection.execute(
                """
                INSERT INTO repo_snapshots
                (
                    job_id,
                    action_type,
                    source_type,
                    repo_name,
                    repo_owner,
                    local_path,
                    remote_url,
                    status,
                    reversible_flag,
                    repo_key,
                    snapshot_timestamp,
                    branch,
                    head_commit,
                    file_count,
                    change_count,
                    scan_fingerprint,
                    structure_hash,
                    structure_item_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.job_id,
                    snapshot.action_type,
                    snapshot.source_type,
                    snapshot.repo_name,
                    snapshot.repo_owner,
                    snapshot.local_path,
                    snapshot.remote_url,
                    snapshot.status,
                    0,
                    snapshot.repo_key,
                    snapshot.snapshot_timestamp,
                    snapshot.branch,
                    snapshot.head_commit,
                    snapshot.file_count,
                    snapshot.change_count,
                    snapshot.scan_fingerprint,
                    snapshot.structure_hash,
                    snapshot.structure_item_count,
                ),
            )
            snapshot.id = int(cursor.lastrowid)
            if snapshot.files:
                connection.executemany(
                    """
                    INSERT INTO repo_snapshot_files
                    (snapshot_id, relative_path, path_type, extension, content_hash, git_status, is_deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            int(snapshot.id),
                            file_entry.relative_path,
                            file_entry.path_type,
                            file_entry.extension,
                            file_entry.content_hash,
                            file_entry.git_status,
                            int(file_entry.is_deleted),
                        )
                        for file_entry in snapshot.files
                    ],
                )
        return snapshot

    def fetch_recent_repository_snapshot(self, repo_key: str) -> RepositorySnapshot | None:
        """
        Laedt den juengsten Repository-Snapshot zu einem stabilen `repo_key`.

        Eingabeparameter:
        - repo_key: Interner Repository-Schluessel aus dem State-Layer.

        Rueckgabewerte:
        - Juengster Snapshot oder `None`.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Nur Snapshot-Eintraege mit gesetztem `repo_key` werden beruecksichtigt, damit
          alte Job-Snapshots ohne Evolutionsdaten nicht versehentlich gemischt werden.
        """

        with sqlite_connection(self._database_file) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM repo_snapshots
                WHERE repo_key = ?
                  AND COALESCE(snapshot_timestamp, '') <> ''
                ORDER BY snapshot_timestamp DESC, id DESC
                LIMIT 1
                """,
                (repo_key,),
            ).fetchone()
        return self._map_repository_snapshot(row) if row is not None else None

    def fetch_repository_snapshots(self, repo_key: str, limit: int = 32, include_files: bool = True) -> list[RepositorySnapshot]:
        """
        Laedt die juengste Snapshot-Reihe eines Repositories fuer Timeline und Analyse.

        Eingabeparameter:
        - repo_key: Interner Repository-Schluessel aus dem State-Layer.
        - limit: Maximale Anzahl geladener Snapshots.
        - include_files: Laedt bei Bedarf zusaetzlich die Dateimenge fuer Diff-Analysen.

        Rueckgabewerte:
        - Liste der Snapshots in aufsteigender zeitlicher Reihenfolge.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Die Rueckgabe wird chronologisch sortiert, damit Timeline und Evolutionsanalyse
          direkt aufeinanderfolgende Vergleichspaare bilden koennen.
        """

        with sqlite_connection(self._database_file) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM repo_snapshots
                WHERE repo_key = ?
                  AND COALESCE(snapshot_timestamp, '') <> ''
                ORDER BY snapshot_timestamp DESC, id DESC
                LIMIT ?
                """,
                (repo_key, limit),
            ).fetchall()
        snapshots = [self._map_repository_snapshot(row) for row in rows]
        snapshots.reverse()
        if include_files:
            for snapshot in snapshots:
                if snapshot.id is None:
                    continue
                snapshot.files = self.fetch_snapshot_files(int(snapshot.id))
        return snapshots

    def fetch_snapshot_files(self, snapshot_id: int) -> list[RepositorySnapshotFile]:
        """
        Laedt die zu einem Snapshot gehoerige persistierte Dateimenge.

        Eingabeparameter:
        - snapshot_id: Datenbank-ID des Snapshot-Kopfes.

        Rueckgabewerte:
        - Liste der zugehoerigen Snapshot-Dateieintraege.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Die Dateitabelle bleibt absichtlich separat, damit Kopfabfragen klein und schnell bleiben.
        """

        with sqlite_connection(self._database_file) as connection:
            rows = connection.execute(
                """
                SELECT relative_path, path_type, extension, content_hash, git_status, is_deleted
                FROM repo_snapshot_files
                WHERE snapshot_id = ?
                ORDER BY relative_path
                """,
                (snapshot_id,),
            ).fetchall()
        return [
            RepositorySnapshotFile(
                relative_path=str(row["relative_path"] or ""),
                path_type=str(row["path_type"] or "file"),
                extension=str(row["extension"] or ""),
                content_hash=str(row["content_hash"] or ""),
                git_status=str(row["git_status"] or "clean"),
                is_deleted=bool(row["is_deleted"]),
            )
            for row in rows
        ]

    def fetch_last_clone_action(self, repo_name: str, remote_url: str = "", repo_id: int = 0) -> ActionSummary | None:
        """
        Laedt die letzte bekannte Clone-Aktion fuer ein Repository.

        Eingabeparameter:
        - repo_name: Fachlicher Repository-Name.
        - remote_url: Optionale Remote-URL fuer praeziseres Matching.
        - repo_id: Optionale Remote-Repository-ID.

        Rueckgabewerte:
        - ActionSummary der letzten Clone-Aktion oder `None`.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Nutzt dieselbe robuste Identitaetslogik wie die Delete-Sicherheitspruefung.
        """

        with sqlite_connection(self._database_file) as connection:
            row = connection.execute(
                """
                SELECT 'clone' AS action_type, status, created_at AS timestamp, message
                FROM clone_history
                WHERE repo_name = ?
                   OR (? <> '' AND remote_url = ?)
                   OR (? <> 0 AND repo_id = ?)
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (repo_name, remote_url, remote_url, repo_id, repo_id),
            ).fetchone()
        return self._map_summary(row)

    def fetch_last_action_by_type(
        self,
        action_type: str,
        repo_name: str,
        remote_url: str = "",
        local_path: str = "",
    ) -> ActionSummary | None:
        """
        Laedt die letzte bekannte Aktion eines bestimmten Typs aus `action_history`.

        Eingabeparameter:
        - action_type: Gesuchter Aktionsname wie `commit`, `push` oder `delete_remote`.
        - repo_name: Fachlicher Repository-Name.
        - remote_url: Optionale Remote-URL fuer praeziseres Matching.
        - local_path: Optionaler lokaler Pfad fuer lokale Repositories.

        Rueckgabewerte:
        - ActionSummary oder `None`.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Verwendet mehrere Matching-Felder, damit Kontextdaten nicht nur am Namen haengen.
        """

        table_name = self._resolve_history_table(action_type)
        with sqlite_connection(self._database_file) as connection:
            row = connection.execute(
                f"""
                SELECT ? AS action_type, status, created_at AS timestamp, message
                FROM {table_name}
                WHERE (
                    repo_name = ?
                    OR (? <> '' AND remote_url = ?)
                    OR (? <> '' AND local_path = ?)
                  )
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (action_type, repo_name, remote_url, remote_url, local_path, local_path),
            ).fetchone()
        return self._map_summary(row)

    def fetch_last_commit_action(self, repo_name: str, remote_url: str = "", local_path: str = "") -> ActionSummary | None:
        """
        Laedt die letzte Commit-Aktion eines Repositories.
        """

        return self.fetch_last_action_by_type("commit", repo_name=repo_name, remote_url=remote_url, local_path=local_path)

    def fetch_last_push_action(self, repo_name: str, remote_url: str = "", local_path: str = "") -> ActionSummary | None:
        """
        Laedt die letzte Push-Aktion eines Repositories.
        """

        return self.fetch_last_action_by_type("push", repo_name=repo_name, remote_url=remote_url, local_path=local_path)

    def fetch_last_delete_action(self, repo_name: str, remote_url: str = "", local_path: str = "") -> ActionSummary | None:
        """
        Laedt die letzte Delete-Aktion eines Repositories.
        """

        return self.fetch_last_action_by_type("delete_remote", repo_name=repo_name, remote_url=remote_url, local_path=local_path)

    def fetch_last_general_action(self, repo_name: str, remote_url: str = "", local_path: str = "") -> ActionSummary | None:
        """
        Laedt die letzte bekannte allgemeine Aktion aus `action_history` oder `clone_history`.

        Eingabeparameter:
        - repo_name: Fachlicher Repository-Name.
        - remote_url: Optionale Remote-URL fuer praeziseres Matching.
        - local_path: Optionaler lokaler Pfad.

        Rueckgabewerte:
        - Neueste ActionSummary oder `None`.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Vergleicht die letzten Kandidaten aus beiden Tabellen und waehlt den juengsten Eintrag.
        """

        candidates = [
            self.fetch_last_clone_action(repo_name=repo_name, remote_url=remote_url),
            self.fetch_last_action_by_type("commit", repo_name=repo_name, remote_url=remote_url, local_path=local_path),
            self.fetch_last_action_by_type("push", repo_name=repo_name, remote_url=remote_url, local_path=local_path),
            self.fetch_last_action_by_type("delete_remote", repo_name=repo_name, remote_url=remote_url, local_path=local_path),
            self.fetch_last_action_by_type("struct_scan", repo_name=repo_name, remote_url=remote_url, local_path=local_path),
        ]
        valid_candidates = [candidate for candidate in candidates if candidate is not None]
        if not valid_candidates:
            return None
        return max(valid_candidates, key=lambda item: item.timestamp or "")

    def fetch_recent_activity(self, repo_name: str, remote_url: str = "", local_path: str = "", limit: int = 8) -> list[ActionSummary]:
        """
        Laedt die juengsten bekannten Aktivitaeten eines Repositories aus Clone- und Aktionshistorie.

        Eingabeparameter:
        - repo_name: Fachlicher Repository-Name.
        - remote_url: Optionale Remote-URL fuer praeziseres Matching.
        - local_path: Optionaler lokaler Pfad.
        - limit: Maximale Anzahl zurueckzugebender Eintraege.

        Rueckgabewerte:
        - Liste kompakter ActionSummary-Eintraege in absteigender zeitlicher Reihenfolge.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Kombiniert Clone- und allgemeine Aktionseintraege in einer einzigen kompakten Liste
          fuer UI-Historien, ohne die Speichertabellen selbst zu vermischen.
        """

        with sqlite_connection(self._database_file) as connection:
            rows = connection.execute(
                """
                SELECT action_type, status, timestamp, message
                FROM (
                    SELECT 'clone' AS action_type, status, created_at AS timestamp, message
                    FROM clone_history
                    WHERE repo_name = ?
                       OR (? <> '' AND remote_url = ?)
                    UNION ALL
                    SELECT action_type, status, created_at AS timestamp, message
                    FROM action_history
                    WHERE repo_name = ?
                       OR (? <> '' AND remote_url = ?)
                       OR (? <> '' AND local_path = ?)
                )
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (
                    repo_name,
                    remote_url,
                    remote_url,
                    repo_name,
                    remote_url,
                    remote_url,
                    local_path,
                    local_path,
                    limit,
                ),
            ).fetchall()
        summaries: list[ActionSummary] = []
        for row in rows:
            summary = self._map_summary(row)
            if summary is not None:
                summaries.append(summary)
        return summaries

    def _map_summary(self, row) -> ActionSummary | None:
        """
        Wandelt eine SQLite-Zeile in eine ActionSummary um.

        Eingabeparameter:
        - row: SQLite-Row oder `None`.

        Rueckgabewerte:
        - ActionSummary oder `None`.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Kapselt das Mapping an einer Stelle, damit alle Lese-Methoden konsistent bleiben.
        """

        if row is None:
            return None
        return ActionSummary(
            action_type=row["action_type"],
            status=row["status"],
            timestamp=row["timestamp"],
            message=row["message"] or "",
        )

    def _map_repository_snapshot(self, row) -> RepositorySnapshot:
        """
        Wandelt eine SQLite-Zeile aus `repo_snapshots` in das Evolutionsmodell um.

        Eingabeparameter:
        - row: Bereits geladene SQLite-Row.

        Rueckgabewerte:
        - Vollstaendig gemappter RepositorySnapshot.

        Moegliche Fehlerfaelle:
        - Fehlende Spalten werden ueber bestehende Defaultwerte defensiv behandelt.

        Wichtige interne Logik:
        - Alte Job-Snapshots ohne erweiterte Felder bleiben lesbar und liefern einfach
          leere Evolutionsfelder statt die Analyse zu blockieren.
        """

        row_keys = set(row.keys())
        return RepositorySnapshot(
            id=int(row["id"]),
            job_id=str(row["job_id"] or ""),
            repo_key=str(row["repo_key"] or ""),
            snapshot_timestamp=str(row["snapshot_timestamp"] or row["created_at"] or ""),
            branch=str(row["branch"] or ""),
            head_commit=str(row["head_commit"] or ""),
            file_count=int(row["file_count"] or 0) if "file_count" in row_keys else 0,
            change_count=int(row["change_count"] or 0) if "change_count" in row_keys else 0,
            scan_fingerprint=str(row["scan_fingerprint"] or ""),
            structure_hash=str(row["structure_hash"] or ""),
            action_type=str(row["action_type"] or "snapshot"),
            source_type=str(row["source_type"] or "local"),
            repo_name=str(row["repo_name"] or ""),
            repo_owner=str(row["repo_owner"] or ""),
            local_path=str(row["local_path"] or ""),
            remote_url=str(row["remote_url"] or ""),
            status=str(row["status"] or "success"),
            structure_item_count=int(row["structure_item_count"] or 0) if "structure_item_count" in row_keys else 0,
        )

    def _add_specialized_history_record(self, record: ActionRecord) -> None:
        """
        Schreibt Aktionen zusaetzlich in ihre spezialisierte History-Tabelle.

        Eingabeparameter:
        - record: Allgemeiner Aktionsdatensatz.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Einfuegen.

        Wichtige interne Logik:
        - Commit, Push und Delete erhalten dadurch die im Langprompt geforderten Spezialtabellen,
          waehrend `action_history` als gemeinsame Rueckfallhistorie erhalten bleibt.
        """

        table_name = self._resolve_history_table(record.action_type)
        if table_name == "action_history":
            return

        with sqlite_connection(self._database_file) as connection:
            if table_name == "push_history":
                connection.execute(
                    """
                    INSERT INTO push_history
                    (job_id, repo_name, repo_owner, local_path, remote_url, status, message, reversible_flag)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.job_id,
                        record.repo_name,
                        record.repo_owner,
                        record.local_path,
                        record.remote_url,
                        record.status,
                        record.message,
                        int(record.reversible_flag),
                    ),
                )
            else:
                connection.execute(
                    f"""
                    INSERT INTO {table_name}
                    (job_id, repo_name, repo_owner, local_path, remote_url, status, message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.job_id,
                        record.repo_name,
                        record.repo_owner,
                        record.local_path,
                        record.remote_url,
                        record.status,
                        record.message,
                    ),
                )

    def _resolve_history_table(self, action_type: str) -> str:
        """
        Ordnet einen Aktionsnamen der passenden spezialisierten History-Tabelle zu.

        Eingabeparameter:
        - action_type: Fachlicher Aktionsname wie `commit`, `push` oder `delete_remote`.

        Rueckgabewerte:
        - Tabellenname fuer die letzte-Aktion-Abfrage oder Spezialhistorie.

        Moegliche Fehlerfaelle:
        - Unbekannte Aktionen fallen auf `action_history` zurueck.

        Wichtige interne Logik:
        - Die Zuordnung haelt die SQL-Auswahl zentral und vermeidet verstreute Tabellenlogik.
        """

        mapping = {
            "commit": "commit_history",
            "push": "push_history",
            "delete_remote": "delete_history",
        }
        return mapping.get(action_type, "action_history")
