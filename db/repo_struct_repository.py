"""Repository fuer den Struktur-Vault der lokalen Repositories."""

from __future__ import annotations

from pathlib import Path

from db.sqlite_manager import sqlite_connection
from models.struct_models import RepoTreeItem


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
                (repo_identifier, source_type, root_path, relative_path, item_type, size, extension, last_modified, git_status, last_commit_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    )
                    for item in items
                ],
            )

    def fetch_repo_items(self, repo_identifier: str, source_type: str) -> list[RepoTreeItem]:
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
                SELECT repo_identifier, relative_path, item_type, size, extension, last_modified, git_status, last_commit_hash
                FROM repo_tree_items
                WHERE repo_identifier = ? AND source_type = ?
                ORDER BY relative_path
                """,
                (repo_identifier, source_type),
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
                """,
                (repo_identifier, source_type),
            ).fetchone()
        item_count = int(row["item_count"] or 0)
        return item_count > 0, item_count, row["last_scan_timestamp"]
