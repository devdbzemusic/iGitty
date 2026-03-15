"""Dataklassen fuer Remote- und spaetere lokale Repositories."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RateLimitInfo:
    """Speichert die fuer die UI relevanten Rate-Limit-Informationen von GitHub."""

    limit: int = 0
    remaining: int = 0
    reset_at: str = "-"


@dataclass(slots=True)
class RemoteRepo:
    """
    Repraesentiert ein einzelnes Remote-GitHub-Repository fuer UI und Services.

    Eingabeparameter:
    - repo_id: Stabile numerische GitHub-Repository-ID.
    - name: Kurzer Repository-Name.
    - full_name: Kombination aus Owner und Name.
    - owner: GitHub-Owner des Repositories.
    - visibility: Sichtbarkeit des Remote-Repositories.
    - default_branch: Standardbranch auf GitHub.
    - language: Dominante Sprache laut GitHub.
    - archived: Kennzeichnet archivierte Repositories.
    - fork: Kennzeichnet Forks.
    - clone_url: HTTPS-Clone-URL.
    - ssh_url: SSH-Clone-URL.
    - html_url: Browser-URL des Repositories.
    - description: Freitextbeschreibung.
    - topics: Themenliste aus GitHub.
    - contributors_count: Optionale Beitragsanzahl.
    - contributors_summary: Kompakte Beitragszusammenfassung.
    - created_at: Erstellungszeitpunkt.
    - updated_at: Letzte allgemeine Aktualisierung.
    - pushed_at: Letzter Push-Zeitpunkt.
    - size: Repository-Groesse in KB.
    - available_actions: Bereits aufgeloeste technische Aktions-IDs fuer Menues und Kontextaktionen.
    - recommended_action: Lesbare Primaerempfehlung fuer das Repository.
    - sync_state: Berechneter Synchronisationszustand gegen ein eventuell gekoppeltes lokales Repository.
    - health_state: Kompakter Gesundheitszustand fuer Ampel- und Diagnoseansichten.
    - linked_local_path: Optional verknuepfter lokaler Pfad aus dem Pairing-Layer.
    - ahead_count: Anzahl lokaler Commits vor dem Remote-Stand, sofern gepaart.
    - behind_count: Anzahl fehlender lokaler Commits gegenueber dem Remote-Stand, sofern gepaart.
    - last_checked_at: Letzter technischer Pruefzeitpunkt.
    - link_type: Art der aktuell bekannten Verknuepfung.
    - link_confidence: Vertrauensstufe der aktuellen Verknuepfung.
    - state_status_hash: Persistierter Delta-Hash fuer gezielte UI-Updates.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Modell enthaelt neben GitHub-Metadaten auch die wichtigsten Pairing- und
      Sync-Informationen, damit die Remote-Tabelle DB-first und dennoch zustandsreich
      arbeiten kann.
    """

    repo_id: int
    name: str
    full_name: str
    owner: str
    visibility: str
    default_branch: str
    language: str
    archived: bool
    fork: bool
    clone_url: str
    ssh_url: str
    html_url: str
    description: str
    topics: list[str] = field(default_factory=list)
    contributors_count: int | None = None
    contributors_summary: str = ""
    created_at: str = ""
    updated_at: str = ""
    pushed_at: str = ""
    size: int = 0
    available_actions: list[str] = field(default_factory=list)
    recommended_action: str = "-"
    sync_state: str = "REMOTE_ONLY"
    health_state: str = "unknown"
    linked_local_path: str = ""
    ahead_count: int = 0
    behind_count: int = 0
    last_checked_at: str = ""
    link_type: str = ""
    link_confidence: int = 0
    state_status_hash: str = ""


@dataclass(slots=True)
class LocalRepo:
    """
    Repraesentiert ein lokal erkanntes Git-Repository fuer UI und Services.

    Eingabeparameter:
    - name: Sichtbarer Repository-Name.
    - full_path: Vollstaendiger lokaler Pfad.
    - current_branch: Aktueller lokaler Branch.
    - has_remote: Kennzeichnet eine konfigurierte Remote-Beziehung.
    - remote_url: Aktuelle URL des Hauptremotes.
    - has_changes: Kennzeichnet lokale Arbeitsbaum-Aenderungen.
    - untracked_count: Anzahl unversionierter Dateien.
    - modified_count: Anzahl geaenderter getrackter Dateien.
    - last_commit_hash: Letzter lokaler Commit.
    - last_commit_date: Datum des letzten Commits.
    - last_commit_message: Nachricht des letzten Commits.
    - remote_visibility: Bekannte Sichtbarkeit des entfernten Repositories.
    - publish_as_public: Lokale Default-Vorgabe fuer neue Remote-Repositories.
    - remote_repo_id: Bekannte GitHub-Repository-ID.
    - language_guess: Leichtgewichtige Sprachheuristik.
    - state_repo_id: Zugehoerige State-Repository-ID.
    - remote_status: Rueckwaertskompatible Statusspalte fuer bestehende UI-Teile.
    - remote_exists_online: Online-Zustand des Remotes.
    - recommended_action: Lesbare Primaerempfehlung.
    - available_actions: Bereits aufgeloeste technische Aktions-IDs.
    - exists_local: Kennzeichnet einen aktuell vorhandenen lokalen Pfad.
    - needs_rescan: Markiert einen noetigen Tiefenscan.
    - health_state: Kompakter Gesundheitszustand.
    - sync_state: Berechneter Synchronisationszustand.
    - owner: Optional bekannter GitHub-Owner des gepaarten Remotes.
    - remote_name: Optional bekannter GitHub-Repository-Name des gepaarten Remotes.
    - ahead_count: Anzahl lokaler Commits vor dem Remote.
    - behind_count: Anzahl lokaler Commits hinter dem Remote.
    - last_checked_at: Letzte technische Pruefung.
    - link_type: Art der aktuell bekannten Verknuepfung.
    - link_confidence: Vertrauensstufe der Verknuepfung.
    - sync_policy: Konfigurierte sichere Sync-Policy.
    - local_head_commit: Aktueller lokaler HEAD-Commit fuer Diagnose und Aktionen.
    - remote_head_commit: Bekannter Remote-HEAD-Commit fuer Diagnose und Aktionen.
    - merge_base_commit: Letzter gemeinsamer Commit zwischen lokal und Remote.
    - state_status_hash: Persistierter Delta-Hash fuer gezielte UI-Updates.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Modell bleibt kompakt genug fuer Tabellen und Kontextmenues, traegt jetzt aber
      die wichtigsten Pairing- und Sync-Daten direkt aus dem State-Layer mit.
    """

    name: str
    full_path: str
    current_branch: str
    has_remote: bool
    remote_url: str
    has_changes: bool
    untracked_count: int
    modified_count: int
    last_commit_hash: str
    last_commit_date: str
    last_commit_message: str
    remote_visibility: str = "not_published"
    publish_as_public: bool = True
    remote_repo_id: int = 0
    language_guess: str = "-"
    state_repo_id: int = 0
    remote_status: str = "LOCAL_ONLY"
    remote_exists_online: int | None = None
    recommended_action: str = "-"
    available_actions: list[str] = field(default_factory=list)
    exists_local: bool = True
    needs_rescan: bool = False
    health_state: str = "unknown"
    sync_state: str = "NOT_INITIALIZED"
    owner: str = ""
    remote_name: str = ""
    ahead_count: int = 0
    behind_count: int = 0
    last_checked_at: str = ""
    link_type: str = ""
    link_confidence: int = 0
    sync_policy: str = "manual"
    local_head_commit: str = ""
    remote_head_commit: str = ""
    merge_base_commit: str = ""
    state_status_hash: str = ""
