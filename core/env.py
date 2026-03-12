"""Einlesen und Aufbereiten der relevanten Umgebungsvariablen."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class EnvSettings:
    """Haelt die aus der Umgebung geladenen Rohwerte der Anwendung."""

    github_access_token: str
    github_app_client_id: str
    repo_dir: Path | None


def load_environment() -> EnvSettings:
    """
    Liest die benoetigten Umgebungsvariablen der Anwendung ein.

    Eingabeparameter:
    - Keine.

    Rueckgabewerte:
    - Eine EnvSettings-Instanz mit allen bekannten Konfigurationswerten.

    Moegliche Fehlerfaelle:
    - Nicht aufloesbarer Pfad in `IGITTY_REPO_DIR`.

    Wichtige interne Logik:
    - Laesst fehlende Werte bewusst zu, damit die UI spaeter kontrolliert reagieren kann.
    - Wandelt den Repo-Zielordner sofort in ein Path-Objekt um.
    """

    raw_repo_dir = os.getenv("IGITTY_REPO_DIR", "").strip()
    repo_dir = Path(raw_repo_dir).expanduser() if raw_repo_dir else None

    return EnvSettings(
        github_access_token=os.getenv("GITHUB_ACCESS_TOKEN", "").strip(),
        github_app_client_id=os.getenv("GITHUBAPP_CLIENT_ID", "").strip(),
        repo_dir=repo_dir,
    )
