"""UI-nahe Hilfsmodelle."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RepoContext:
    """Zusammengefuehrtes Sichtmodell fuer den Eintritt in Teil 2."""

    source_type: str
    repo_id: str | None = None
    remote_repo_id: int | None = None
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
    has_struct_vault_data: bool = False
    struct_item_count: int = 0
    last_struct_scan_timestamp: str | None = None
    diagnostic_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StatusSnapshot:
    """Fasst die in der Statuszeile angezeigten Werte in einem Objekt zusammen."""

    github_text: str
    remote_count: int
    local_count: int
    rate_limit_text: str
    target_dir_text: str
