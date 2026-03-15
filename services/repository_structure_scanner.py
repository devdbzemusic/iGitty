"""Delta-faehiger Struktur-Scanner fuer den persistierten RepoExplorer-Vault."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.logger import AppLogger
from db.repo_struct_repository import RepoStructRepository
from models.struct_models import RepoStructureScanStats, RepoTreeItem
from services.git_service import GitService


class RepositoryStructureScanner:
    """Scant lokale Repository-Strukturen und schreibt Deltas in den Struktur-Vault."""

    def __init__(
        self,
        repository: RepoStructRepository,
        git_service: GitService,
        logger: AppLogger | None = None,
    ) -> None:
        """
        Initialisiert Scanner, Git-Zugriff und Vault-Repository.

        Eingabeparameter:
        - repository: Persistenzschicht fuer `repo_struct_vault.db`.
        - git_service: Git-CLI-Helfer fuer Dateistatus und Commit-Details.
        - logger: Optionaler zentraler Logger fuer Strukturdiagnosen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Scanner bleibt bewusst lokal und lesend; die eigentliche Delta-Persistenz
          liegt weiterhin sauber getrennt im Repository.
        """

        self._repository = repository
        self._git_service = git_service
        self._logger = logger

    def scan_repository(
        self,
        repo_identifier: str,
        source_type: str,
        repo_path: Path,
        include_commit_details: bool = False,
    ) -> RepoStructureScanStats:
        """
        Scannt ein einzelnes lokales Repository und persistiert die Struktur per Delta.

        Eingabeparameter:
        - repo_identifier: Stabiler technischer Schluessel des Repositories.
        - source_type: Herkunft des Repositories, typischerweise `local`.
        - repo_path: Dateisystempfad des zu scannenden Repository-Roots.
        - include_commit_details: Aktiviert optional teurere per-Datei-Commitabfragen.

        Rueckgabewerte:
        - Delta-Statistik des Struktur-Scans.

        Moegliche Fehlerfaelle:
        - Nicht vorhandene oder unlesbare Repositories werfen Dateisystem- oder Git-Fehler.

        Wichtige interne Logik:
        - Die Methode erfasst sowohl Datei- als auch Verzeichnisknoten.
        - `.git`-Inhalte werden komplett ausgelassen.
        - Git-Status wird moeglichst leichtgewichtig gesammelt, damit der RepoExplorer
          bereits beim Oeffnen einen sinnvollen Arbeitszustand zeigen kann.
        """

        scan_timestamp = self._utc_now()
        if self._logger is not None:
            self._logger.event(
                "scan",
                "repository_structure_scan_begin",
                (
                    f"repo_identifier={repo_identifier} | source_type={source_type} | "
                    f"repo_path={repo_path} | include_commit_details={include_commit_details}"
                ),
            )

        status_by_path = self._git_service.get_status_porcelain_map(repo_path)
        items = self._build_tree_items(
            repo_identifier=repo_identifier,
            repo_path=repo_path,
            scan_timestamp=scan_timestamp,
            status_by_path=status_by_path,
            include_commit_details=include_commit_details,
        )
        stats = self._repository.update_repo_items_delta(
            repo_identifier=repo_identifier,
            source_type=source_type,
            root_path=str(repo_path),
            items=items,
            scan_timestamp=scan_timestamp,
        )
        if self._logger is not None:
            self._logger.event(
                "scan",
                "repository_structure_scan_complete",
                (
                    f"repo_identifier={repo_identifier} | source_type={source_type} | total={stats.total_count} | "
                    f"inserted={stats.inserted_count} | updated={stats.updated_count} | "
                    f"deleted={stats.deleted_count} | unchanged={stats.unchanged_count}"
                ),
            )
        return stats

    def _build_tree_items(
        self,
        repo_identifier: str,
        repo_path: Path,
        scan_timestamp: str,
        status_by_path: dict[str, str],
        include_commit_details: bool,
    ) -> list[RepoTreeItem]:
        """
        Baut aus dem Dateisystem und Git-Metadaten die persistierbaren Strukturknoten auf.

        Eingabeparameter:
        - repo_identifier: Stabiler technischer Repository-Schluessel.
        - repo_path: Root des gescannten Repositories.
        - scan_timestamp: Zeitstempel des aktuellen Struktur-Scans.
        - status_by_path: Vorberechnete Git-Statuszuordnung nach relativem Pfad.
        - include_commit_details: Aktiviert optionale per-Datei-Commitabfragen.

        Rueckgabewerte:
        - Vollstaendige Liste aktueller Strukturknoten.

        Moegliche Fehlerfaelle:
        - Dateisystemfehler beim Lesen einzelner Knoten.

        Wichtige interne Logik:
        - Die Methode sortiert den Baum stabil, damit Tests und Deltas deterministisch bleiben.
        """

        items: list[RepoTreeItem] = []
        for current in sorted(repo_path.rglob("*"), key=lambda item: str(item).lower()):
            if ".git" in current.parts:
                continue
            relative_path = str(current.relative_to(repo_path)).replace("\\", "/")
            stat = current.stat()
            git_status = self._resolve_git_status(relative_path, current.is_dir(), status_by_path)
            last_commit_hash = ""
            if include_commit_details and current.is_file():
                last_commit_hash = self._git_service.get_last_commit_hash_for_path(repo_path, relative_path)
            items.append(
                RepoTreeItem(
                    repo_identifier=repo_identifier,
                    relative_path=relative_path,
                    item_type="dir" if current.is_dir() else "file",
                    size=0 if current.is_dir() else int(stat.st_size),
                    extension="" if current.is_dir() else current.suffix.lower(),
                    last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    git_status=git_status,
                    last_commit_hash=last_commit_hash,
                    version_scan_timestamp=scan_timestamp,
                    is_deleted=False,
                )
            )
        return items

    def _resolve_git_status(self, relative_path: str, is_directory: bool, status_by_path: dict[str, str]) -> str:
        """
        Leitet fuer einen Knoten einen moeglichst passenden Git-Status ab.

        Eingabeparameter:
        - relative_path: Relativer Pfad des aktuellen Knotens.
        - is_directory: Kennzeichnet Verzeichnisse fuer Prefix-Matching.
        - status_by_path: Vorbereitete Git-Statuszuordnung aus `git status --porcelain`.

        Rueckgabewerte:
        - Lesbarer Statuswert wie `M`, `A`, `??` oder `clean`.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte Pfade werden defensiv als `clean` behandelt.

        Wichtige interne Logik:
        - Fuer Verzeichnisse wird auf untergeordnete Dateistati aggregiert, damit der
          RepoExplorer betroffene Ordner direkt hervorheben kann.
        """

        direct_status = status_by_path.get(relative_path)
        if direct_status:
            return direct_status
        if is_directory:
            prefix = f"{relative_path}/"
            for path_text, status in status_by_path.items():
                if path_text.startswith(prefix):
                    return status
        return "clean"

    def _utc_now(self) -> str:
        """
        Erzeugt einen einheitlichen UTC-Zeitstempel fuer Struktur-Scans.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - ISO-8601-Zeitstempel in UTC.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Eine zentrale Hilfsmethode haelt Logging, Delta-Persistenz und Tests konsistent.
        """

        return datetime.now(timezone.utc).isoformat()
