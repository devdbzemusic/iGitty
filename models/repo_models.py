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
    """Repraesentiert ein einzelnes Remote-GitHub-Repository fuer UI und Services."""

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
    updated_at: str = ""


@dataclass(slots=True)
class LocalRepo:
    """Repraesentiert ein lokal erkanntes Git-Repository fuer UI und Services."""

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
    publish_as_public: bool = False
    remote_repo_id: int = 0
    language_guess: str = "-"
