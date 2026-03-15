"""Persistente Zustandsmodelle fuer lokal indexierte Repositories."""

from __future__ import annotations

from dataclasses import dataclass

from models.repo_models import RateLimitInfo, RemoteRepo


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
    repo_key: str = ""
    name: str = ""
    source_type: str = "local"
    local_path: str = ""
    remote_url: str = ""
    github_repo_id: int = 0
    default_branch: str = ""
    visibility: str = "unknown"
    is_archived: bool = False
    is_deleted: bool = False
    is_missing: bool = False
    last_seen_at: str = ""
    last_changed_at: str = ""
    last_checked_at: str = ""
    scan_fingerprint: str = ""
    status_hash: str = ""
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
    language: str = "-"
    description: str = ""
    topics_json: str = "[]"
    contributors_count: int = 0
    contributors_summary: str = ""
    created_at: str = ""
    updated_at: str = ""
    pushed_at: str = ""
    size_kb: int = 0
    is_fork: bool = False
    remote_exists_online: int | None = None
    remote_visibility: str = "unknown"
    exists_local: bool = True
    exists_remote: bool | None = None
    git_initialized: bool = False
    remote_configured: bool = False
    has_uncommitted_changes: bool = False
    ahead_count: int = 0
    behind_count: int = 0
    is_diverged: bool = False
    auth_state: str = "unknown"
    sync_state: str = "NOT_INITIALIZED"
    health_state: str = "unknown"
    dirty_hint: bool = False
    needs_rescan: bool = True
    status: str = "NOT_INITIALIZED"
    last_local_scan_at: str = ""
    last_remote_check_at: str = ""
    linked_repo_key: str = ""
    linked_local_path: str = ""
    link_type: str = ""
    link_confidence: int = 0
    recommended_action: str = "-"
    available_actions_json: str = "[]"
    local_head_commit: str = ""
    remote_head_commit: str = ""
    merge_base_commit: str = ""
    last_sync_decision: str = ""
    sync_policy: str = "manual"


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
    path_type: str = "file"
    size_bytes: int = 0
    modified_at: str = ""
    content_hash: str = ""
    is_tracked: bool = False
    is_ignored: bool = False
    is_deleted: bool = False
    last_seen_at: str = ""
    last_seen_scan_at: str = ""


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
    severity: str = "info"
    message: str = ""
    payload_json: str = ""
    created_at: str = ""


@dataclass(slots=True)
class ScanRunRecord:
    """
    Beschreibt einen einzelnen Backend-Refresh-Lauf fuer lokale oder Remote-Repositories.

    Eingabeparameter:
    - scan_type: Technischer Typ wie `local_normal_refresh` oder `local_hard_refresh`.
    - started_at: Beginn des Scan-Laufs.
    - finished_at: Ende des Scan-Laufs.
    - duration_ms: Gesamtdauer in Millisekunden.
    - changed_count: Anzahl veraenderter Datensaetze.
    - unchanged_count: Anzahl uebersprungener unveraenderter Datensaetze.
    - error_count: Anzahl registrierter Fehler.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Modell dient als kompakte Persistenzform fuer spaetere Diagnose- und Performance-
      Auswertungen rund um Delta-Scans.
    """

    id: int | None = None
    scan_type: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    error_count: int = 0


@dataclass(slots=True)
class RepoFileDeltaStats:
    """
    Beschreibt das Ergebnis eines Delta-Updates fuer den Dateiindex eines Repositories.

    Eingabeparameter:
    - inserted_count: Anzahl neu angelegter Dateieintraege.
    - updated_count: Anzahl aktualisierter Dateieintraege.
    - deleted_count: Anzahl als geloescht markierter Dateieintraege.
    - unchanged_count: Anzahl unveraenderter Dateieintraege.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Die Stats erlauben Tests und Logging fuer Delta-Updates, ohne den eigentlichen
      Dateiscan mit UI-spezifischen Details zu vermischen.
    """

    inserted_count: int = 0
    updated_count: int = 0
    deleted_count: int = 0
    unchanged_count: int = 0


@dataclass(slots=True)
class RepositorySyncSnapshot:
    """
    Fasst einen orchestrierten Synchronisationslauf ueber lokale und Remote-Repositories zusammen.

    Eingabeparameter:
    - local_repositories: Lokal synchronisierte Repository-Zustaende.
    - remote_repositories: Remote-Repository-Sicht fuer die UI.
    - rate_limit: Aktueller GitHub-Rate-Limit-Stand.
    - hard_refresh: Kennzeichnet einen erzwungenen Vollscan.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Modell dient dem neuen RepositorySyncOrchestrator als klarer Rueckgabevertrag,
      ohne Controller oder UI bereits auf konkrete Scan-Implementierungen festzunageln.
    """

    local_repositories: list[RepositoryState]
    remote_repositories: list[RemoteRepo]
    rate_limit: RateLimitInfo
    hard_refresh: bool = False


@dataclass(slots=True)
class RepoLink:
    """
    Beschreibt die persistierte Verknuepfung zwischen lokalem und entferntem Repository.

    Eingabeparameter:
    - state_repo_id: Zugehoerige lokale Repository-ID aus `igitty_state.db`.
    - github_repo_id: Zugehoerige GitHub-Repository-ID.
    - local_path: Lokaler Repository-Pfad.
    - remote_url: Verknuepfte Remote-URL.
    - remote_owner: GitHub-Owner des verknuepften Remotes.
    - remote_name: GitHub-Repository-Name des verknuepften Remotes.
    - link_type: Technischer Link-Typ wie `exact`, `url_match`, `github_id_match`, `name_match` oder `manual`.
    - link_confidence: Fachliche Vertrauensstufe des Matches.
    - is_active: Kennzeichnet die aktuell gueltige Verknuepfung.
    - last_verified_at: Zeitpunkt der letzten Pairing-Pruefung.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Unsichere Namensmatches koennen mit niedrigerer Confidence oder inaktiv markiert
      werden, ohne die bisherige stabile Kopplung zu ueberschreiben.
    """

    id: int | None = None
    state_repo_id: int = 0
    github_repo_id: int = 0
    local_path: str = ""
    remote_url: str = ""
    remote_owner: str = ""
    remote_name: str = ""
    link_type: str = ""
    link_confidence: int = 0
    is_active: bool = True
    last_verified_at: str = ""
