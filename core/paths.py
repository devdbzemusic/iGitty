"""Verwaltet alle projektbezogenen Laufzeitpfade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RuntimePaths:
    """Kapselt alle fuer die Laufzeit benoetigten Dateisystempfade."""

    project_root: Path
    assets_dir: Path
    data_dir: Path
    logs_dir: Path
    jobs_db_file: Path
    repo_struct_db_file: Path
    state_db_file: Path
    log_file: Path
    stylesheet_file: Path


def ensure_runtime_paths() -> RuntimePaths:
    """
    Ermittelt und erstellt alle benoetigten Laufzeitverzeichnisse.

    Eingabeparameter:
    - Keine.

    Rueckgabewerte:
    - Eine RuntimePaths-Instanz mit allen relevanten Projektpfaden.

    Moegliche Fehlerfaelle:
    - Fehlende Schreibrechte im Projektverzeichnis.

    Wichtige interne Logik:
    - Das Projektwurzelverzeichnis wird ueber den Speicherort dieser Datei bestimmt.
    - Daten- und Logverzeichnisse werden sofort angelegt, damit spaetere Initialisierungsschritte stabil laufen.
    """

    project_root = Path(__file__).resolve().parent.parent
    assets_dir = project_root / "assets"
    data_dir = project_root / "data"
    logs_dir = project_root / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    return RuntimePaths(
        project_root=project_root,
        assets_dir=assets_dir,
        data_dir=data_dir,
        logs_dir=logs_dir,
        jobs_db_file=data_dir / "igitty_jobs.db",
        repo_struct_db_file=data_dir / "repo_struct_vault.db",
        state_db_file=data_dir / "igitty_state.db",
        log_file=logs_dir / "log.txt",
        stylesheet_file=assets_dir / "styles" / "neon_dark.qss",
    )
