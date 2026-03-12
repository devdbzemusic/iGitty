"""Orchestrierung fuer sichere Clone-Ablaufe von Remote-Repositories."""

from __future__ import annotations

from pathlib import Path

from models.job_models import CloneRecord
from models.repo_models import RemoteRepo
from services.git_service import GitService


class CloneService:
    """Fuehrt Batch-Clones mit defensiver Zielpfadpruefung aus."""

    def __init__(self, git_service: GitService) -> None:
        """
        Initialisiert den Service mit einer Git-Abhaengigkeit.

        Eingabeparameter:
        - git_service: Service fuer die direkten Git-CLI-Operationen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Die eigentliche Prozessausfuehrung bleibt in `GitService`, waehrend hier Ablaufregeln gelten.
        """

        self._git_service = git_service

    def clone_repositories(
        self,
        repositories: list[RemoteRepo],
        target_root: Path,
        job_id: str,
    ) -> list[CloneRecord]:
        """
        Klont mehrere Remote-Repositories in den angegebenen Zielordner.

        Eingabeparameter:
        - repositories: Auswahl der zu klonenden Remote-Repositories.
        - target_root: Oberordner fuer die lokalen Zielverzeichnisse.
        - job_id: Uebergeordnete Job-ID fuer die Protokollierung.

        Rueckgabewerte:
        - Liste der einzelnen Clone-Ergebnisse je Repository.

        Moegliche Fehlerfaelle:
        - Fehlende Git-CLI.
        - Nicht vorhandener oder nicht beschreibbarer Zielordner.

        Wichtige interne Logik:
        - Existierende Zielordner werden sicher uebersprungen statt ueberschrieben.
        - Jeder Clone erzeugt ein eigenes Ergebnisobjekt fuer SQLite und UI.
        """

        self._git_service.ensure_git_available()
        target_root.mkdir(parents=True, exist_ok=True)

        results: list[CloneRecord] = []
        for repository in repositories:
            local_path = target_root / repository.name
            if local_path.exists():
                results.append(
                    CloneRecord(
                        job_id=job_id,
                        repo_id=repository.repo_id,
                        repo_name=repository.name,
                        remote_url=repository.clone_url,
                        local_path=str(local_path),
                        status="skipped",
                        message="Zielordner existiert bereits und wurde sicher uebersprungen.",
                    )
                )
                continue

            try:
                self._git_service.clone_repository(repository.clone_url, local_path)
                results.append(
                    CloneRecord(
                        job_id=job_id,
                        repo_id=repository.repo_id,
                        repo_name=repository.name,
                        remote_url=repository.clone_url,
                        local_path=str(local_path),
                        status="success",
                        message="Repository erfolgreich geklont.",
                    )
                )
            except Exception as error:  # noqa: BLE001
                results.append(
                    CloneRecord(
                        job_id=job_id,
                        repo_id=repository.repo_id,
                        repo_name=repository.name,
                        remote_url=repository.clone_url,
                        local_path=str(local_path),
                        status="error",
                        message=str(error),
                    )
                )

        return results
