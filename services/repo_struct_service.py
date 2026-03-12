"""Service fuer Datei- und Ordnerstruktur-Scans lokaler Repositories."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from db.repo_struct_repository import RepoStructRepository
from models.job_models import ActionRecord
from models.repo_models import LocalRepo
from models.struct_models import RepoTreeItem


class RepoStructService:
    """Erfasst die baumartige Struktur lokaler Repositories fuer den spaeteren RepoViewer."""

    def __init__(self, repository: RepoStructRepository) -> None:
        """
        Initialisiert den Service mit einem persistierenden Repository.

        Eingabeparameter:
        - repository: Datenbank-Repository fuer den Struktur-Vault.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Die Dateisystem-Ermittlung und Datenbankpersistenz bleiben sauber getrennt.
        """

        self._repository = repository

    def scan_repositories(self, repositories: list[LocalRepo], job_id: str) -> list[ActionRecord]:
        """
        Scannt mehrere lokale Repositories und speichert deren Struktur in SQLite.

        Eingabeparameter:
        - repositories: Ausgewaehlte lokale Repositories.
        - job_id: Uebergeordnete Job-ID fuer den Batch.

        Rueckgabewerte:
        - Ergebnisliste je Repository.

        Moegliche Fehlerfaelle:
        - Dateisystemzugriff oder Datenbankpersistenz koennen pro Repository fehlschlagen.

        Wichtige interne Logik:
        - Jeder Scan ersetzt die vorherigen Knoten dieses Repositories vollstaendig.
        """

        results: list[ActionRecord] = []
        for repository in repositories:
            repo_path = Path(repository.full_path)
            try:
                items: list[RepoTreeItem] = []
                for current in repo_path.rglob("*"):
                    if ".git" in current.parts:
                        continue
                    relative_path = str(current.relative_to(repo_path))
                    stat = current.stat()
                    items.append(
                        RepoTreeItem(
                            repo_identifier=repository.name,
                            relative_path=relative_path,
                            item_type="dir" if current.is_dir() else "file",
                            size=0 if current.is_dir() else stat.st_size,
                            extension="" if current.is_dir() else current.suffix.lower(),
                            last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        )
                    )
                self._repository.replace_repo_items(repository.name, "local", repository.full_path, items)
                results.append(
                    ActionRecord(
                        job_id=job_id,
                        action_type="struct_scan",
                        repo_name=repository.name,
                        source_type="local",
                        local_path=repository.full_path,
                        remote_url=repository.remote_url,
                        status="success",
                        message=f"{len(items)} Strukturknoten gespeichert.",
                        reversible_flag=False,
                    )
                )
            except Exception as error:  # noqa: BLE001
                results.append(
                    ActionRecord(
                        job_id=job_id,
                        action_type="struct_scan",
                        repo_name=repository.name,
                        source_type="local",
                        local_path=repository.full_path,
                        remote_url=repository.remote_url,
                        status="error",
                        message=str(error),
                        reversible_flag=False,
                    )
                )
        return results

    def fetch_repo_summary(self, repo_identifier: str, source_type: str) -> tuple[bool, int, str | None]:
        """
        Liefert eine kompakte Struktur-Zusammenfassung fuer den Repo-Kontext.

        Eingabeparameter:
        - repo_identifier: Eindeutige Kennung des Repositories.
        - source_type: Herkunft des Repositories.

        Rueckgabewerte:
        - Tupel aus Vorhandensein, Anzahl und letztem Scan-Zeitpunkt.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Reicht die Repository-Zusammenfassung unveraendert an die Kontext-Schicht durch.
        """

        return self._repository.fetch_repo_summary(repo_identifier, source_type)
