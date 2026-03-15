"""Initialisierung und Hilfslogik fuer die persistente Repository-State-Datenbank."""

from __future__ import annotations

from pathlib import Path

from db.sqlite_manager import sqlite_connection


STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_key TEXT UNIQUE,
    name TEXT,
    source_type TEXT DEFAULT 'local',
    local_path TEXT UNIQUE,
    remote_url TEXT,
    github_repo_id INTEGER DEFAULT 0,
    default_branch TEXT,
    visibility TEXT,
    is_archived INTEGER DEFAULT 0,
    is_deleted INTEGER DEFAULT 0,
    is_missing INTEGER DEFAULT 0,
    last_seen_at TEXT,
    last_changed_at TEXT,
    last_checked_at TEXT,
    scan_fingerprint TEXT,
    status_hash TEXT,
    is_git_repo INTEGER,
    current_branch TEXT,
    head_commit TEXT,
    head_commit_date TEXT,
    has_remote INTEGER,
    remote_name TEXT,
    remote_host TEXT,
    remote_owner TEXT,
    remote_repo_name TEXT,
    language TEXT,
    description TEXT,
    topics_json TEXT,
    contributors_count INTEGER DEFAULT 0,
    contributors_summary TEXT,
    created_at TEXT,
    updated_at TEXT,
    pushed_at TEXT,
    size_kb INTEGER DEFAULT 0,
    is_fork INTEGER DEFAULT 0,
    remote_exists_online INTEGER,
    remote_visibility TEXT,
    status TEXT,
    last_local_scan_at TEXT,
    last_remote_check_at TEXT
);

CREATE TABLE IF NOT EXISTS repo_status (
    repo_id INTEGER PRIMARY KEY,
    exists_local INTEGER DEFAULT 0,
    exists_remote INTEGER,
    git_initialized INTEGER DEFAULT 0,
    remote_configured INTEGER DEFAULT 0,
    has_uncommitted_changes INTEGER DEFAULT 0,
    ahead_count INTEGER DEFAULT 0,
    behind_count INTEGER DEFAULT 0,
    is_diverged INTEGER DEFAULT 0,
    auth_state TEXT DEFAULT 'unknown',
    sync_state TEXT DEFAULT 'NOT_INITIALIZED',
    health_state TEXT DEFAULT 'unknown',
    dirty_hint INTEGER DEFAULT 0,
    needs_rescan INTEGER DEFAULT 1,
    last_checked_at TEXT,
    status_hash TEXT,
    FOREIGN KEY(repo_id) REFERENCES repositories(id)
);

CREATE TABLE IF NOT EXISTS repo_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    path_type TEXT DEFAULT 'file',
    size_bytes INTEGER,
    modified_at TEXT,
    content_hash TEXT,
    is_tracked INTEGER,
    is_ignored INTEGER,
    is_deleted INTEGER DEFAULT 0,
    last_seen_at TEXT,
    last_seen_scan_at TEXT,
    FOREIGN KEY(repo_id) REFERENCES repositories(id)
);

CREATE TABLE IF NOT EXISTS repo_status_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    message TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(repo_id) REFERENCES repositories(id)
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER DEFAULT 0,
    changed_count INTEGER DEFAULT 0,
    unchanged_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);
"""

STATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_repositories_local_path ON repositories(local_path);
CREATE INDEX IF NOT EXISTS idx_repositories_remote_url ON repositories(remote_url);
CREATE INDEX IF NOT EXISTS idx_repositories_repo_key ON repositories(repo_key);
CREATE INDEX IF NOT EXISTS idx_repositories_github_repo_id ON repositories(github_repo_id);
CREATE INDEX IF NOT EXISTS idx_repositories_last_checked_at ON repositories(last_checked_at);
CREATE INDEX IF NOT EXISTS idx_repo_status_repo_id ON repo_status(repo_id);
CREATE INDEX IF NOT EXISTS idx_repo_status_needs_rescan ON repo_status(needs_rescan);
CREATE INDEX IF NOT EXISTS idx_repo_files_repo_id ON repo_files(repo_id);
CREATE INDEX IF NOT EXISTS idx_repo_files_repo_id_relative_path ON repo_files(repo_id, relative_path);
CREATE UNIQUE INDEX IF NOT EXISTS idx_repo_files_unique_repo_path ON repo_files(repo_id, relative_path);
CREATE INDEX IF NOT EXISTS idx_repo_status_events_repo_id ON repo_status_events(repo_id);
CREATE INDEX IF NOT EXISTS idx_scan_runs_scan_type ON scan_runs(scan_type);
"""


def initialize_state_database(database_file: Path) -> None:
    """
    Legt die persistente State-Datenbank fuer Repository-Scans an und migriert fehlende Spalten.

    Eingabeparameter:
    - database_file: Zielpfad der Datei `igitty_state.db`.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Die Datenbankdatei ist nicht schreibbar.
    - Das SQL-Schema ist defekt.

    Wichtige interne Logik:
    - Bestehende MVP-Tabellen werden minimal-invasiv erweitert, damit fruehere lokale
      Daten erhalten bleiben und keine parallele Zweitwelt entsteht.
    """

    with sqlite_connection(database_file) as connection:
        connection.executescript(STATE_SCHEMA)

        for column_name, definition in (
            ("repo_key", "TEXT"),
            ("source_type", "TEXT DEFAULT 'local'"),
            ("remote_url", "TEXT"),
            ("github_repo_id", "INTEGER DEFAULT 0"),
            ("default_branch", "TEXT"),
            ("visibility", "TEXT"),
            ("is_archived", "INTEGER DEFAULT 0"),
            ("is_deleted", "INTEGER DEFAULT 0"),
            ("is_missing", "INTEGER DEFAULT 0"),
            ("last_seen_at", "TEXT"),
            ("last_changed_at", "TEXT"),
            ("last_checked_at", "TEXT"),
            ("scan_fingerprint", "TEXT"),
            ("status_hash", "TEXT"),
            ("current_branch", "TEXT"),
            ("head_commit", "TEXT"),
            ("head_commit_date", "TEXT"),
            ("has_remote", "INTEGER"),
            ("remote_name", "TEXT"),
            ("remote_host", "TEXT"),
            ("remote_owner", "TEXT"),
            ("remote_repo_name", "TEXT"),
            ("language", "TEXT"),
            ("description", "TEXT"),
            ("topics_json", "TEXT"),
            ("contributors_count", "INTEGER DEFAULT 0"),
            ("contributors_summary", "TEXT"),
            ("created_at", "TEXT"),
            ("updated_at", "TEXT"),
            ("pushed_at", "TEXT"),
            ("size_kb", "INTEGER DEFAULT 0"),
            ("is_fork", "INTEGER DEFAULT 0"),
            ("remote_exists_online", "INTEGER"),
            ("remote_visibility", "TEXT"),
            ("status", "TEXT"),
            ("last_local_scan_at", "TEXT"),
            ("last_remote_check_at", "TEXT"),
        ):
            _ensure_column(connection, "repositories", column_name, definition)

        for column_name, definition in (
            ("path_type", "TEXT DEFAULT 'file'"),
            ("content_hash", "TEXT"),
            ("is_deleted", "INTEGER DEFAULT 0"),
            ("last_seen_at", "TEXT"),
            ("last_seen_scan_at", "TEXT"),
        ):
            _ensure_column(connection, "repo_files", column_name, definition)

        for column_name, definition in (
            ("severity", "TEXT DEFAULT 'info'"),
            ("payload_json", "TEXT"),
        ):
            _ensure_column(connection, "repo_status_events", column_name, definition)

        connection.executescript(STATE_INDEXES)


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
    - Diese kleine Migration haelt den State-Layer upgrade-faehig, ohne ein separates
      Migrationsframework einzufuehren.
    """

    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in existing_columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def compute_repository_status(is_git_repo: bool, has_remote: bool, remote_exists_online: int | None) -> str:
    """
    Berechnet den fachlichen Gesamtstatus eines Repositories aus Basismerkmalen.

    Eingabeparameter:
    - is_git_repo: Ob der Pfad aktuell ein gueltiges Git-Repository ist.
    - has_remote: Ob ein konfigurierter Remote vorhanden ist.
    - remote_exists_online: Ergebnis der Online-Pruefung mit `1`, `0` oder `None`.

    Rueckgabewerte:
    - Einer der Statuswerte `NOT_INITIALIZED`, `LOCAL_ONLY`, `REMOTE_OK`,
      `REMOTE_MISSING` oder `REMOTE_UNREACHABLE`.

    Moegliche Fehlerfaelle:
    - Keine; unbekannte Kombinationen werden defensiv auf `REMOTE_UNREACHABLE` gemappt.

    Wichtige interne Logik:
    - Die Funktion kapselt die Statusregeln zentral, damit Scan, Push und UI dieselbe
      Fachlogik verwenden und keine widerspruechlichen Anzeigen entstehen.
    """

    if not is_git_repo:
        return "NOT_INITIALIZED"
    if not has_remote:
        return "LOCAL_ONLY"
    if remote_exists_online == 1:
        return "REMOTE_OK"
    if remote_exists_online == 0:
        return "REMOTE_MISSING"
    return "REMOTE_UNREACHABLE"
