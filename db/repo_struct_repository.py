"""Repository fuer den Struktur-Vault der lokalen Repositories."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from db.sqlite_manager import sqlite_connection
from models.struct_models import RepoStructureScanStats, RepoTreeItem


class RepoStructRepository:
    """Kapselt Schreibzugriffe auf `repo_struct_vault.db`."""

    def __init__(self, database_file: Path) -> None:
        """
        Speichert den Zielpfad fuer spaetere Strukturzugriffe.

        Eingabeparameter:
        - database_file: Pfad zur `repo_struct_vault.db`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Initialisierung.

        Wichtige interne Logik:
        - Die Datenbank wird spaeter ueber gezielte Methoden beschrieben statt direkt aus Services heraus.
        """

        self.database_file = database_file

    def replace_repo_items(self, repo_identifier: str, source_type: str, root_path: str, items: list[RepoTreeItem]) -> None:
        """
        Ersetzt alle gespeicherten Struktur-Eintraege eines Repositories durch einen neuen Scan.

        Eingabeparameter:
        - repo_identifier: Eindeutige Kennung des Repositories.
        - source_type: Herkunft des Scans, etwa `local` oder `remote_clone`.
        - root_path: Root-Pfad des gescannten Repositories.
        - items: Vollstaendig vorbereitete Strukturknoten.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Loeschen oder Einfuegen.

        Wichtige interne Logik:
        - Ein kompletter Replace-Ansatz ist fuer den MVP robuster als differenzielle Upserts.
        """

        with sqlite_connection(self.database_file) as connection:
            connection.execute(
                "DELETE FROM repo_tree_items WHERE repo_identifier = ? AND source_type = ?",
                (repo_identifier, source_type),
            )
            connection.executemany(
                """
                INSERT INTO repo_tree_items
                (
                    repo_identifier,
                    source_type,
                    root_path,
                    relative_path,
                    item_type,
                    size,
                    extension,
                    last_modified,
                    git_status,
                    last_commit_hash,
                    version_scan_timestamp,
                    is_deleted,
                    content_hash,
                    last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.repo_identifier,
                        source_type,
                        root_path,
                        item.relative_path,
                        item.item_type,
                        getattr(item, "size", 0),
                        getattr(item, "extension", ""),
                        getattr(item, "last_modified", ""),
                        getattr(item, "git_status", ""),
                        getattr(item, "last_commit_hash", ""),
                        getattr(item, "version_scan_timestamp", ""),
                        int(getattr(item, "is_deleted", False)),
                        self._build_item_hash(item),
                        getattr(item, "version_scan_timestamp", ""),
                    )
                    for item in items
                ],
            )

    def update_repo_items_delta(
        self,
        repo_identifier: str,
        source_type: str,
        root_path: str,
        items: list[RepoTreeItem],
        scan_timestamp: str,
    ) -> RepoStructureScanStats:
        """
        Aktualisiert Strukturknoten per Delta statt den kompletten Vault-Eintrag zu ersetzen.

        Eingabeparameter:
        - repo_identifier: Stabiler technischer Repository-Schluessel.
        - source_type: Herkunft des Repositories.
        - root_path: Aktueller Root-Pfad des gescannten Repositories.
        - items: Vollstaendige aktuelle Sicht des Strukturbaums.
        - scan_timestamp: Zeitstempel des aktuellen Struktur-Scans.

        Rueckgabewerte:
        - Detaillierte Delta-Statistik fuer Logging, Tests und Diagnosen.

        Moegliche Fehlerfaelle:
        - SQLite-Fehler bei Insert, Update oder Soft-Delete.

        Wichtige interne Logik:
        - Vorhandene Knoten werden ueber `relative_path` identifiziert.
        - Verschwundene Knoten werden nur weich als geloescht markiert.
        - Unveraenderte Knoten bleiben unangetastet und werden nur als gesehen markiert.
        """

        stats = RepoStructureScanStats(scan_timestamp=scan_timestamp)
        current_items_by_path = {
            item.relative_path: item
            for item in items
        }

        with sqlite_connection(self.database_file) as connection:
            rows = connection.execute(
                """
                SELECT id, relative_path, content_hash, is_deleted
                FROM repo_tree_items
                WHERE repo_identifier = ? AND source_type = ?
                """,
                (repo_identifier, source_type),
            ).fetchall()
            existing_by_path = {str(row["relative_path"]): row for row in rows}

            for relative_path, item in current_items_by_path.items():
                item_hash = self._build_item_hash(item)
                existing_row = existing_by_path.get(relative_path)
                if existing_row is None:
                    connection.execute(
                        """
                        INSERT INTO repo_tree_items
                        (
                            repo_identifier,
                            source_type,
                            root_path,
                            relative_path,
                            item_type,
                            size,
                            extension,
                            last_modified,
                            git_status,
                            last_commit_hash,
                            version_scan_timestamp,
                            is_deleted,
                            content_hash,
                            last_seen_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            repo_identifier,
                            source_type,
                            root_path,
                            item.relative_path,
                            item.item_type,
                            item.size,
                            item.extension,
                            item.last_modified,
                            item.git_status,
                            item.last_commit_hash,
                            scan_timestamp,
                            0,
                            item_hash,
                            scan_timestamp,
                        ),
                    )
                    stats.inserted_count += 1
                    continue

                if str(existing_row["content_hash"] or "") != item_hash or bool(existing_row["is_deleted"]):
                    connection.execute(
                        """
                        UPDATE repo_tree_items
                        SET root_path = ?,
                            item_type = ?,
                            size = ?,
                            extension = ?,
                            last_modified = ?,
                            git_status = ?,
                            last_commit_hash = ?,
                            version_scan_timestamp = ?,
                            is_deleted = 0,
                            content_hash = ?,
                            last_seen_at = ?
                        WHERE id = ?
                        """,
                        (
                            root_path,
                            item.item_type,
                            item.size,
                            item.extension,
                            item.last_modified,
                            item.git_status,
                            item.last_commit_hash,
                            scan_timestamp,
                            item_hash,
                            scan_timestamp,
                            int(existing_row["id"]),
                        ),
                    )
                    stats.updated_count += 1
                else:
                    connection.execute(
                        """
                        UPDATE repo_tree_items
                        SET last_seen_at = ?, is_deleted = 0
                        WHERE id = ?
                        """,
                        (scan_timestamp, int(existing_row["id"])),
                    )
                    stats.unchanged_count += 1

            for relative_path, existing_row in existing_by_path.items():
                if relative_path in current_items_by_path or bool(existing_row["is_deleted"]):
                    continue
                connection.execute(
                    """
                    UPDATE repo_tree_items
                    SET is_deleted = 1,
                        version_scan_timestamp = ?,
                        last_seen_at = ?
                    WHERE id = ?
                    """,
                    (scan_timestamp, scan_timestamp, int(existing_row["id"])),
                )
                stats.deleted_count += 1

            row = connection.execute(
                """
                SELECT COUNT(*) AS total_count
                FROM repo_tree_items
                WHERE repo_identifier = ? AND source_type = ? AND is_deleted = 0
                """,
                (repo_identifier, source_type),
            ).fetchone()
        stats.total_count = int(row["total_count"] or 0) if row is not None else 0
        return stats

    def fetch_repo_items(self, repo_identifier: str, source_type: str, include_deleted: bool = False) -> list[RepoTreeItem]:
        """
        Laedt alle gespeicherten Strukturknoten eines Repositories aus dem Vault.

        Eingabeparameter:
        - repo_identifier: Eindeutige Kennung des Repositories.
        - source_type: Herkunft des Repositories, etwa `local`.

        Rueckgabewerte:
        - Liste der gespeicherten Strukturknoten.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Die Rueckgabe bleibt als Dataklassenliste, damit der RepoViewer sauber typisiert arbeiten kann.
        """

        with sqlite_connection(self.database_file) as connection:
            rows = connection.execute(
                """
                SELECT repo_identifier, relative_path, item_type, size, extension, last_modified,
                       git_status, last_commit_hash, version_scan_timestamp, is_deleted
                FROM repo_tree_items
                WHERE repo_identifier = ? AND source_type = ?
                  AND (? = 1 OR is_deleted = 0)
                ORDER BY relative_path
                """,
                (repo_identifier, source_type, int(include_deleted)),
            ).fetchall()
        return [
            RepoTreeItem(
                repo_identifier=row["repo_identifier"],
                relative_path=row["relative_path"],
                item_type=row["item_type"],
                size=row["size"] or 0,
                extension=row["extension"] or "",
                last_modified=row["last_modified"] or "",
                git_status=row["git_status"] or "",
                last_commit_hash=row["last_commit_hash"] or "",
                version_scan_timestamp=row["version_scan_timestamp"] or "",
                is_deleted=bool(row["is_deleted"]),
            )
            for row in rows
        ]

    def fetch_repo_summary(self, repo_identifier: str, source_type: str) -> tuple[bool, int, str | None]:
        """
        Laedt eine kompakte Zusammenfassung vorhandener Strukturdaten fuer ein Repository.

        Eingabeparameter:
        - repo_identifier: Eindeutige Kennung des Repositories.
        - source_type: Herkunft des Repositories.

        Rueckgabewerte:
        - Tupel aus Vorhandensein, Anzahl der Eintraege und letztem Scan-Zeitpunkt.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Liefert bewusst nur Summenwerte fuer den Repo-Kontext und keinen Baum.
        """

        with sqlite_connection(self.database_file) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS item_count, MAX(version_scan_timestamp) AS last_scan_timestamp
                FROM repo_tree_items
                WHERE repo_identifier = ? AND source_type = ?
                  AND is_deleted = 0
                """,
                (repo_identifier, source_type),
            ).fetchone()
        item_count = int(row["item_count"] or 0)
        return item_count > 0, item_count, row["last_scan_timestamp"]

    def _build_item_hash(self, item: RepoTreeItem) -> str:
        """
        Erzeugt einen stabilen Hash ueber die fachlich relevanten Knotenfelder.

        Eingabeparameter:
        - item: Zu persistierender Strukturknoten.

        Rueckgabewerte:
        - Hexadezimale SHA256-Darstellung.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Hash trennt echte Struktur- und Statusaenderungen von reinem `last_seen`-Touching.
        """

        payload = "|".join(
            [
                item.relative_path,
                item.item_type,
                str(item.size),
                item.extension,
                item.last_modified,
                item.git_status,
                item.last_commit_hash,
                str(int(item.is_deleted)),
            ]
        )
        return sha256(payload.encode("utf-8")).hexdigest()
