"""Initialisierung und Hilfslogik fuer die persistente Repository-State-Datenbank."""

from __future__ import annotations

from pathlib import Path

from db.sqlite_manager import sqlite_connection


STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    local_path TEXT UNIQUE,
    is_git_repo INTEGER,
    current_branch TEXT,
    head_commit TEXT,
    head_commit_date TEXT,
    has_remote INTEGER,
    remote_name TEXT,
    remote_url TEXT,
    remote_host TEXT,
    remote_owner TEXT,
    remote_repo_name TEXT,
    remote_exists_online INTEGER,
    remote_visibility TEXT,
    status TEXT,
    last_local_scan_at TEXT,
    last_remote_check_at TEXT
);

CREATE TABLE IF NOT EXISTS repo_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    size_bytes INTEGER,
    modified_at TEXT,
    is_tracked INTEGER,
    is_ignored INTEGER,
    last_seen_scan_at TEXT,
    FOREIGN KEY(repo_id) REFERENCES repositories(id)
);

CREATE TABLE IF NOT EXISTS repo_status_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(repo_id) REFERENCES repositories(id)
);

CREATE INDEX IF NOT EXISTS idx_repositories_local_path ON repositories(local_path);
CREATE INDEX IF NOT EXISTS idx_repositories_remote_url ON repositories(remote_url);
CREATE INDEX IF NOT EXISTS idx_repo_files_repo_id ON repo_files(repo_id);
CREATE INDEX IF NOT EXISTS idx_repo_status_events_repo_id ON repo_status_events(repo_id);
"""


def initialize_state_database(database_file: Path) -> None:
    """
    Legt die persistente State-Datenbank fuer Repository-Scans an.

    Eingabeparameter:
    - database_file: Zielpfad der Datei `igitty_state.db`.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Die Datenbankdatei ist nicht schreibbar.
    - Das SQL-Schema ist defekt.

    Wichtige interne Logik:
    - Die State-Datenbank bleibt bewusst getrennt von Job-Log und Struktur-Vault,
      damit Scan-Zustand, Benutzeraktionen und Strukturhistorie klar getrennt bleiben.
    """

    with sqlite_connection(database_file) as connection:
        connection.executescript(STATE_SCHEMA)


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
