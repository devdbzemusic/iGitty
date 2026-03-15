"""Service fuer Datei- und Ordnerstruktur-Scans lokaler Repositories."""

from __future__ import annotations

from pathlib import Path

from db.repo_struct_repository import RepoStructRepository
from models.job_models import ActionRecord
from models.repo_models import LocalRepo
from models.struct_models import RepoTreeItem
from services.repository_structure_scanner import RepositoryStructureScanner


class RepoStructService:
    """Erfasst die baumartige Struktur lokaler Repositories fuer den spaeteren RepoViewer."""

    def __init__(
        self,
        repository: RepoStructRepository,
        structure_scanner: RepositoryStructureScanner | None = None,
    ) -> None:
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
        self._structure_scanner = structure_scanner

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
        - Die Methode nutzt jetzt einen deltafaehigen Scanner, damit spaetere RepoViewer-
          Oeffnungen und Strukturdiagnosen nicht bei jedem Lauf einen Komplettaustausch benoetigen.
        """

        results: list[ActionRecord] = []
        for repository in repositories:
            repo_path = Path(repository.full_path)
            try:
                repo_identifier = self.build_repo_identifier(local_path=repository.full_path)
                if self._structure_scanner is None:
                    items: list[RepoTreeItem] = []
                    for current in repo_path.rglob("*"):
                        if ".git" in current.parts:
                            continue
                        relative_path = str(current.relative_to(repo_path)).replace("\\", "/")
                        stat = current.stat()
                        items.append(
                            RepoTreeItem(
                                repo_identifier=repo_identifier,
                                relative_path=relative_path,
                                item_type="dir" if current.is_dir() else "file",
                                size=0 if current.is_dir() else int(stat.st_size),
                                extension="" if current.is_dir() else current.suffix.lower(),
                                last_modified="",
                                git_status="clean",
                                version_scan_timestamp="",
                            )
                        )
                    self._repository.replace_repo_items(repo_identifier, "local", repository.full_path, items)
                    item_count = len(items)
                    delta_message = "Legacy-Fallback ohne Delta-Scanner verwendet."
                else:
                    stats = self._structure_scanner.scan_repository(
                        repo_identifier=repo_identifier,
                        source_type="local",
                        repo_path=repo_path,
                        include_commit_details=False,
                    )
                    item_count = stats.total_count
                    delta_message = (
                        f"Struktur aktualisiert: +{stats.inserted_count} / ~{stats.updated_count} / "
                        f"-{stats.deleted_count} / ={stats.unchanged_count}"
                    )
                results.append(
                    ActionRecord(
                        job_id=job_id,
                        action_type="struct_scan",
                        repo_name=repository.name,
                        source_type="local",
                        local_path=repository.full_path,
                        remote_url=repository.remote_url,
                        status="success",
                        message=f"{item_count} Strukturknoten gespeichert. {delta_message}",
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

    def fetch_repo_items(self, repo_identifier: str, source_type: str) -> list[RepoTreeItem]:
        """
        Laedt die aktuelle Struktur eines Repositories fuer den RepoExplorer aus dem Vault.

        Eingabeparameter:
        - repo_identifier: Stabiler technischer Repository-Schluessel.
        - source_type: Herkunft des Repositories.

        Rueckgabewerte:
        - Liste der aktuell sichtbaren Strukturknoten.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Geloeschte Knoten bleiben im Vault erhalten, werden hier fuer den RepoExplorer
          aber standardmaessig ausgeblendet.
        """

        return self._repository.fetch_repo_items(repo_identifier, source_type, include_deleted=False)

    def build_repo_identifier(
        self,
        local_path: str = "",
        remote_repo_id: int = 0,
        remote_url: str = "",
        repo_name: str = "",
    ) -> str:
        """
        Erzeugt einen stabilen Struktur-Vault-Schluessel fuer lokale oder Remote-Repositories.

        Eingabeparameter:
        - local_path: Optionaler lokaler Repository-Pfad.
        - remote_repo_id: Optionale GitHub-Repository-ID.
        - remote_url: Optionale Remote-URL.
        - repo_name: Defensiver Namensfallback.

        Rueckgabewerte:
        - Stabiler Identifier fuer `repo_struct_vault.db`.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Pfad wird fuer lokale Repositories bevorzugt, damit gleichnamige Repositories
          in verschiedenen Roots sauber getrennt bleiben.
        """

        if local_path:
            return f"local::{local_path.lower()}"
        if remote_repo_id:
            return f"remote::{remote_repo_id}"
        if remote_url:
            return f"remote_url::{remote_url.lower()}"
        return repo_name
