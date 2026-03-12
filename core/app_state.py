"""Zentraler Laufzeitstatus fuer UI und Controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from models.repo_models import RateLimitInfo


@dataclass(slots=True)
class AppState:
    """Speichert UI-relevante Zustandswerte an einer zentralen Stelle."""

    current_target_dir: Path
    remote_repo_count: int = 0
    local_repo_count: int = 0
    github_status_text: str = "Nicht verbunden"
    rate_limit: RateLimitInfo = field(default_factory=RateLimitInfo)
