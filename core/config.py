"""Konfigurationsobjekte fuer die Anwendung."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.env import EnvSettings
from core.paths import RuntimePaths


@dataclass(slots=True)
class AppConfig:
    """Buendelt die statische und dynamische Anwendungskonfiguration."""

    application_name: str
    organization_name: str
    stylesheet_path: Path
    default_repo_dir: Path


def build_app_config(env_settings: EnvSettings, paths: RuntimePaths) -> AppConfig:
    """
    Erstellt das zentrale Konfigurationsobjekt fuer die Anwendung.

    Eingabeparameter:
    - env_settings: Bereits geladene Umgebungswerte der Anwendung.
    - paths: Vorbereitete Laufzeitpfade fuer Daten, Logs und Assets.

    Rueckgabewerte:
    - Vollstaendig befuellte AppConfig-Instanz.

    Moegliche Fehlerfaelle:
    - Ungueltige oder nicht aufloesbare Pfade aus der Umgebung.

    Wichtige interne Logik:
    - Verwendet den konfigurierten Repo-Ordner aus den EnvVars, falls vorhanden.
    - Faellt andernfalls robust auf den lokalen Datenordner zurueck.
    """

    default_repo_dir = env_settings.repo_dir or (paths.project_root / "repos")
    return AppConfig(
        application_name="iGitty",
        organization_name="DBZS",
        stylesheet_path=paths.stylesheet_file,
        default_repo_dir=default_repo_dir,
    )
