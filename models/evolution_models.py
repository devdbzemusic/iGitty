"""Datamodelle fuer Repository-Snapshots, Timeline und Evolutionsanalyse."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RepositorySnapshotFile:
    """
    Beschreibt einen einzelnen Datei- oder Strukturknoten innerhalb eines Repository-Snapshots.

    Eingabeparameter:
    - relative_path: Relativer Pfad innerhalb des Repositories.
    - path_type: `file` oder `dir`.
    - extension: Dateiendung in Kleinbuchstaben fuer Typauswertungen.
    - content_hash: Persistierter Inhalts- oder Delta-Hash aus dem State-Layer.
    - git_status: Kompakter Git-Status wie `M`, `A`, `??` oder `clean`.
    - is_deleted: Kennzeichnet im Snapshot geloeschte oder bereits verschwundene Eintraege.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Modell haelt die fuer Snapshot-Diffs benoetigten Dateidetails getrennt vom
      eigentlichen Kopfdatensatz des Snapshots.
    """

    relative_path: str
    path_type: str
    extension: str = ""
    content_hash: str = ""
    git_status: str = "clean"
    is_deleted: bool = False


@dataclass(slots=True)
class RepositorySnapshot:
    """
    Beschreibt einen zeitlichen Snapshot eines Repository-Zustands fuer Time-Travel-Analysen.

    Eingabeparameter:
    - repo_key: Stabiler technischer Repository-Schluessel aus dem State-Layer.
    - snapshot_timestamp: Zeitstempel des Snapshot-Zeitpunkts.
    - branch: Aktueller Branch zum Snapshot-Zeitpunkt.
    - head_commit: Aktueller HEAD-Commit.
    - file_count: Anzahl bekannter Dateien im Snapshot.
    - change_count: Anzahl aktuell als veraendert erkannter Dateien oder Knoten.
    - scan_fingerprint: Persistierter Delta-Fingerprint des Repositories.
    - structure_hash: Hash ueber die bekannte Struktur des Repositories.
    - action_type: Ausloeser wie `local_scan`, `push` oder `set_private`.
    - source_type: Herkunft des Repositories, z. B. `local` oder `remote`.
    - repo_name: Lesbarer Name des Repositories.
    - local_path: Optionaler lokaler Pfad.
    - remote_url: Optionale Remote-URL.
    - status: Fachlicher Repository-Status zum Snapshot-Zeitpunkt.
    - files: Optional geladene Snapshot-Dateiliste fuer Diffs.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Die Kopfmetadaten bleiben kompakt, waehrend die Dateiliste bei Bedarf fuer Diffs
      und Evolution erst zusaetzlich geladen werden kann.
    """

    id: int | None = None
    job_id: str = ""
    repo_key: str = ""
    snapshot_timestamp: str = ""
    branch: str = ""
    head_commit: str = ""
    file_count: int = 0
    change_count: int = 0
    scan_fingerprint: str = ""
    structure_hash: str = ""
    action_type: str = "snapshot"
    source_type: str = "local"
    repo_name: str = ""
    repo_owner: str = ""
    local_path: str = ""
    remote_url: str = ""
    status: str = "success"
    structure_item_count: int = 0
    files: list[RepositorySnapshotFile] = field(default_factory=list)


@dataclass(slots=True)
class SnapshotDiffResult:
    """
    Beschreibt die Unterschiede zwischen zwei Repository-Snapshots.

    Eingabeparameter:
    - previous_snapshot_id: ID des aelteren Snapshots.
    - current_snapshot_id: ID des neueren Snapshots.
    - new_files: Neu hinzugekommene Pfade.
    - deleted_files: Verschwundene oder geloeschte Pfade.
    - structure_changes: Beschreibung struktureller Aenderungen wie Datei-zu-Ordner-Wechsel.
    - file_type_changes: Beschreibungen geaenderter Dateitypen.
    - commit_changed: Kennzeichnet einen Wechsel des HEAD-Commits.
    - previous_head_commit: Alter Commit-Hash.
    - current_head_commit: Neuer Commit-Hash.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Ergebnis ist UI-nah, aber noch generisch genug fuer Tests und spaetere Exporte.
    """

    previous_snapshot_id: int | None = None
    current_snapshot_id: int | None = None
    new_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    structure_changes: list[str] = field(default_factory=list)
    file_type_changes: list[str] = field(default_factory=list)
    commit_changed: bool = False
    previous_head_commit: str = ""
    current_head_commit: str = ""


@dataclass(slots=True)
class RepositoryEvolutionSummary:
    """
    Fasst die Entwicklung eines Repositories ueber mehrere Snapshots kompakt zusammen.

    Eingabeparameter:
    - snapshot_count: Anzahl ausgewerteter Snapshots.
    - growth_rate_per_snapshot: Durchschnittliches Dateiwachstum pro Snapshot-Schritt.
    - current_file_count: Aktuelle Dateianzahl des juengsten Snapshots.
    - peak_file_count: Bisher groesste beobachtete Dateianzahl.
    - most_common_file_types: Hauefigste Dateitypen ueber die ausgewerteten Snapshots.
    - structure_changes_per_interval: Lesbare Diff-Zusammenfassungen pro Snapshot-Intervall.
    - activity_phases: Erkannte Aktivitaetsphasen ueber die Zeit.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Die Zusammenfassung ist bewusst lesbar und direkt fuer das Evolution-Panel gedacht.
    """

    snapshot_count: int = 0
    growth_rate_per_snapshot: float = 0.0
    current_file_count: int = 0
    peak_file_count: int = 0
    most_common_file_types: list[str] = field(default_factory=list)
    structure_changes_per_interval: list[str] = field(default_factory=list)
    activity_phases: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RepositoryTimelineEntry:
    """
    Beschreibt einen einzelnen chronologischen Timeline-Eintrag fuer den RepoViewer.

    Eingabeparameter:
    - timestamp: Zeitstempel des Ereignisses.
    - entry_type: Typ wie `snapshot`, `action`, `diagnostic` oder `scan_run`.
    - title: Kurzer Titel fuer die Timeline.
    - details: Zusatzinformationen fuer Details oder Tooltips.
    - severity: Lesbare Prioritaet wie `info`, `warning` oder `error`.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Modell normalisiert sehr unterschiedliche Quellen auf eine gemeinsame Timeline-Sicht.
    """

    timestamp: str
    entry_type: str
    title: str
    details: str = ""
    severity: str = "info"
