"""Persistente Zustandsmodelle fuer lokal indexierte Repositories."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RepositoryState:
    """
    Repraesentiert den persistierten Zustand eines lokal gefundenen Repositories.

    Eingabeparameter:
    - Alle Felder spiegeln die Spalten der State-Datenbank wider.

    Rueckgabewerte:
    - Keine; Dataklasse dient als Transportobjekt zwischen Service- und DB-Schicht.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Modell ist bewusst flach gehalten, damit SQLite-Mapping und Tests einfach bleiben.
    """

    id: int | None = None
    name: str = ""
    local_path: str = ""
    is_git_repo: bool = False
    current_branch: str = ""
    head_commit: str = ""
    head_commit_date: str = ""
    has_remote: bool = False
    remote_name: str = ""
    remote_url: str = ""
    remote_host: str = ""
    remote_owner: str = ""
    remote_repo_name: str = ""
    remote_exists_online: int | None = None
    remote_visibility: str = "unknown"
    status: str = "NOT_INITIALIZED"
    last_local_scan_at: str = ""
    last_remote_check_at: str = ""


@dataclass(slots=True)
class RepoFileState:
    """
    Beschreibt einen indexierten Dateieintrag eines Repositories.

    Eingabeparameter:
    - Die Felder entsprechen dem `repo_files`-Schema der State-Datenbank.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - `repo_id` verknuepft die Datei eindeutig mit einem bekannten Repository-Zustand.
    """

    repo_id: int
    relative_path: str
    size_bytes: int
    modified_at: str
    is_tracked: bool
    is_ignored: bool
    last_seen_scan_at: str


@dataclass(slots=True)
class RepoStatusEvent:
    """
    Beschreibt ein einzelnes Statusereignis fuer ein Repository.

    Eingabeparameter:
    - repo_id: Zugehoeriges Repository in der State-Datenbank.
    - event_type: Technischer Ereignistyp wie `LOCAL_SCAN_COMPLETED`.
    - message: Lesbare Zusatzinformation fuer Diagnose und Nachvollziehbarkeit.
    - created_at: Zeitstempel der Erzeugung.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Ereignisse sind append-only, damit Scans und Reparaturen spaeter nachvollziehbar bleiben.
    """

    repo_id: int
    event_type: str
    message: str
    created_at: str
