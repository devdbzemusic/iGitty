"""UI-nahe Hilfsmodelle."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StatusSnapshot:
    """Fasst die in der Statuszeile angezeigten Werte in einem Objekt zusammen."""

    github_text: str
    remote_count: int
    local_count: int
    rate_limit_text: str
    target_dir_text: str
