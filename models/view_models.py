"""UI-nahe Hilfsmodelle."""

from __future__ import annotations

from dataclasses import dataclass, field

from models.evolution_models import RepositoryEvolutionSummary, RepositorySnapshot, RepositoryTimelineEntry, SnapshotDiffResult
from models.job_models import ActionSummary
from models.state_models import RepoStatusEvent, ScanRunRecord
from models.struct_models import RepoTreeItem


@dataclass(slots=True)
class RepoContext:
    """
    Zusammengefuehrtes Sichtmodell fuer den RepoViewer in MVP Phase II.

    Eingabeparameter:
    - Die Felder kombinieren Remote-, Local-, State-, Struktur- und Historiedaten.

    Rueckgabewerte:
    - Keine; das Objekt dient als View-Model zwischen Services und RepoViewer-UI.

    Moegliche Fehlerfaelle:
    - Keine direkt im Modell.

    Wichtige interne Logik:
    - Das Modell bleibt flach genug fuer Tests und Dialoge, traegt aber jetzt bereits
      die wichtigsten Dashboard-, Explorer-, Historien- und Diagnoseinformationen.
    """

    source_type: str
    repo_id: str | None = None
    remote_repo_id: int | None = None
    state_repo_id: int | None = None
    repo_name: str = ""
    repo_full_name: str = ""
    owner: str = ""
    description: str = ""
    local_path: str | None = None
    remote_url: str | None = None
    clone_url: str | None = None
    current_branch: str | None = None
    default_branch: str | None = None
    remote_visibility: str = "unknown"
    publish_as_public: bool = False
    archived: bool = False
    fork: bool = False
    has_remote: bool = False
    has_local_clone: bool = False
    languages: str = ""
    contributors_summary: str = ""
    last_action_type: str | None = None
    last_action_status: str | None = None
    last_action_timestamp: str | None = None
    repository_status: str = "unknown"
    health_state: str = "unknown"
    sync_state: str = "unknown"
    recommended_action: str = "-"
    available_actions: list[str] = field(default_factory=list)
    last_scan_at: str | None = None
    last_remote_check_at: str | None = None
    scan_fingerprint: str = ""
    status_hash: str = ""
    needs_rescan: bool = False
    dirty_hint: bool = False
    has_struct_vault_data: bool = False
    struct_item_count: int = 0
    last_struct_scan_timestamp: str | None = None
    diagnostic_events: list[str] = field(default_factory=list)
    history_entries: list[ActionSummary] = field(default_factory=list)
    status_events: list[RepoStatusEvent] = field(default_factory=list)
    recent_scan_runs: list[ScanRunRecord] = field(default_factory=list)
    tree_items: list[RepoTreeItem] = field(default_factory=list)
    snapshots: list[RepositorySnapshot] = field(default_factory=list)
    snapshot_diffs: list[SnapshotDiffResult] = field(default_factory=list)
    timeline_entries: list[RepositoryTimelineEntry] = field(default_factory=list)
    evolution_summary: RepositoryEvolutionSummary | None = None


@dataclass(slots=True)
class StatusSnapshot:
    """Fasst die in der Statuszeile angezeigten Werte in einem Objekt zusammen."""

    github_text: str
    remote_count: int
    local_count: int
    rate_limit_text: str
    target_dir_text: str
