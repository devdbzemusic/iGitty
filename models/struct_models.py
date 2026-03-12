"""Datamodelle fuer spaetere Repo-Struktur-Scans."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RepoTreeItem:
    """Minimalmodell fuer einen gescannten Datei- oder Ordnerknoten."""

    repo_identifier: str
    relative_path: str
    item_type: str
    size: int = 0
    extension: str = ""
    last_modified: str = ""
    git_status: str = ""
    last_commit_hash: str = ""
