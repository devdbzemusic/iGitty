"""Initialisierung der SQLite-Datenbanken fuer iGitty."""

from __future__ import annotations

from core.paths import RuntimePaths
from db.sqlite_manager import sqlite_connection


JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    repo_name TEXT,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clone_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    repo_id INTEGER,
    repo_name TEXT NOT NULL,
    remote_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    local_path TEXT,
    remote_url TEXT,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

REPO_STRUCT_SCHEMA = """
CREATE TABLE IF NOT EXISTS repo_tree_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_identifier TEXT NOT NULL,
    source_type TEXT NOT NULL,
    root_path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    item_type TEXT NOT NULL,
    size INTEGER DEFAULT 0,
    extension TEXT,
    last_modified TEXT,
    git_status TEXT,
    last_commit_hash TEXT,
    version_scan_timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def initialize_databases(paths: RuntimePaths) -> None:
    """
    Legt die benoetigten SQLite-Schemata an, falls sie noch nicht existieren.

    Eingabeparameter:
    - paths: Laufzeitpfade mit den Zielorten der Datenbanken.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Nicht beschreibbare Datenbankdateien.
    - Schemafehler im SQL-Skript.

    Wichtige interne Logik:
    - Initialisiert beide MVP-Datenbanken separat, damit spaetere Migrationen klar getrennt bleiben.
    """

    with sqlite_connection(paths.jobs_db_file) as connection:
        connection.executescript(JOBS_SCHEMA)
        _ensure_column(connection, "clone_history", "repo_id", "INTEGER")

    with sqlite_connection(paths.repo_struct_db_file) as connection:
        connection.executescript(REPO_STRUCT_SCHEMA)


def _ensure_column(connection, table_name: str, column_name: str, definition: str) -> None:
    """
    Ergaenzt eine fehlende Spalte defensiv in einer bestehenden SQLite-Tabelle.

    Eingabeparameter:
    - connection: Bereits geoeffnete SQLite-Verbindung.
    - table_name: Name der zu pruefenden Tabelle.
    - column_name: Erwartete Spalte.
    - definition: SQLite-Spaltendefinition fuer ein moegliches `ALTER TABLE`.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Unerwartete SQLite-Fehler beim Schema-Update.

    Wichtige interne Logik:
    - Diese kleine Migration reicht fuer MVP-Schritte, ohne ein volles Migrationssystem einzufuehren.
    """

    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in existing_columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
