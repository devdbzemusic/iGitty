"""Snapshot-Erzeugung und Diff-Logik fuer das Repository Time-Travel System."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

from core.logger import AppLogger
from db.job_log_repository import JobLogRepository
from db.repo_struct_repository import RepoStructRepository
from db.state_repository import StateRepository
from models.evolution_models import RepositorySnapshot, RepositorySnapshotFile, SnapshotDiffResult
from models.state_models import RepositoryState
from services.repo_struct_service import RepoStructService


class RepositorySnapshotService:
    """Erzeugt persistente Repository-Snapshots fuer Timeline, Time-Travel und Evolution."""

    def __init__(
        self,
        state_repository: StateRepository,
        job_log_repository: JobLogRepository,
        repo_struct_repository: RepoStructRepository,
        repo_struct_service: RepoStructService,
        logger: AppLogger | None = None,
    ) -> None:
        """
        Initialisiert den Snapshot-Service mit Zugriff auf State-, Job- und Strukturdaten.

        Eingabeparameter:
        - state_repository: State-Zugriff auf Repository- und Dateiindexdaten.
        - job_log_repository: Persistenz fuer Snapshot-Kopf- und Dateidaten.
        - repo_struct_repository: Direktzugriff auf den Struktur-Vault.
        - repo_struct_service: Hilfsservice fuer stabile Struktur-Identifier.
        - logger: Optionaler zentraler Logger.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Service liest alle Quellinformationen DB-first und vermeidet damit
          zusaetzliche Live-Scans nur fuer Snapshot-Erzeugung.
        """

        self._state_repository = state_repository
        self._job_log_repository = job_log_repository
        self._repo_struct_repository = repo_struct_repository
        self._repo_struct_service = repo_struct_service
        self._logger = logger

    def capture_snapshot_for_repository(
        self,
        repository: RepositoryState,
        trigger_type: str,
        force: bool = False,
        job_id: str = "",
    ) -> RepositorySnapshot | None:
        """
        Erzeugt bei Bedarf einen neuen Snapshot fuer einen bereits geladenen RepositoryState.

        Eingabeparameter:
        - repository: Persistierter oder frisch aktualisierter RepositoryState.
        - trigger_type: Ausloeser wie `local_scan`, `push` oder `set_private`.
        - force: Erzwingt auch bei gleichen Fingerprints einen neuen Snapshot.
        - job_id: Optional uebergeordnete Job-ID fuer die Rueckverfolgbarkeit.

        Rueckgabewerte:
        - Persistierter Snapshot oder `None`, wenn keine Aenderung einen neuen Snapshot rechtfertigt.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen oder Schreiben der Snapshot-Daten.

        Wichtige interne Logik:
        - Normale Scan-Snapshots werden bei unveraendertem Fingerprint uebersprungen.
        - Aktions-Snapshots koennen bewusst erzwungen werden, damit Commit- oder Push-
          Ereignisse auch ohne sofortige neue Fingerprints nachvollziehbar bleiben.
        """

        if repository.id is None:
            return None
        snapshot = self._build_snapshot(repository, trigger_type=trigger_type, job_id=job_id)
        latest_snapshot = self._job_log_repository.fetch_recent_repository_snapshot(repository.repo_key)
        if not force and latest_snapshot is not None and self._is_redundant_snapshot(latest_snapshot, snapshot):
            if self._logger is not None:
                self._logger.event(
                    "snapshot",
                    "repository_snapshot_skipped",
                    (
                        f"repo_key={repository.repo_key} | trigger_type={trigger_type} | "
                        f"reason=redundant_snapshot"
                    ),
                )
            return None

        stored_snapshot = self._job_log_repository.add_repository_snapshot(snapshot)
        if self._logger is not None:
            self._logger.event(
                "snapshot",
                "repository_snapshot_created",
                (
                    f"repo_key={stored_snapshot.repo_key} | trigger_type={trigger_type} | "
                    f"snapshot_id={stored_snapshot.id} | file_count={stored_snapshot.file_count} | "
                    f"change_count={stored_snapshot.change_count}"
                ),
                level=20,
            )
        return stored_snapshot

    def capture_snapshot_for_local_path(
        self,
        local_path: str,
        trigger_type: str,
        force: bool = False,
        job_id: str = "",
    ) -> RepositorySnapshot | None:
        """
        Loest die Snapshot-Erzeugung ueber einen lokalen Repository-Pfad aus.

        Eingabeparameter:
        - local_path: Vollstaendiger lokaler Repository-Pfad.
        - trigger_type: Ausloesender Ereignistyp.
        - force: Erzwingt einen Snapshot unabhaengig vom letzten Fingerprint.
        - job_id: Optionale Job-ID.

        Rueckgabewerte:
        - Persistierter Snapshot oder `None`.

        Moegliche Fehlerfaelle:
        - Fehlende Repository-Zustaende fuehren defensiv zu `None`.

        Wichtige interne Logik:
        - Die Methode wird von Controllern genutzt, die bereits nur den Pfad des
          betroffenen Repositories kennen.
        """

        repository = self._state_repository.fetch_repository_by_local_path(local_path)
        if repository is None:
            return None
        return self.capture_snapshot_for_repository(repository, trigger_type=trigger_type, force=force, job_id=job_id)

    def capture_snapshot_for_github_repo_id(
        self,
        github_repo_id: int,
        trigger_type: str,
        force: bool = False,
        job_id: str = "",
    ) -> RepositorySnapshot | None:
        """
        Loest die Snapshot-Erzeugung ueber eine GitHub-Repository-ID aus.

        Eingabeparameter:
        - github_repo_id: Numerische GitHub-Repository-ID.
        - trigger_type: Ausloesender Ereignistyp.
        - force: Erzwingt einen Snapshot unabhaengig vom letzten Fingerprint.
        - job_id: Optionale Job-ID.

        Rueckgabewerte:
        - Persistierter Snapshot oder `None`.

        Moegliche Fehlerfaelle:
        - Fehlende Repository-Zustaende fuehren defensiv zu `None`.

        Wichtige interne Logik:
        - Die Methode deckt Remote-Only-Repositories und Remote-Kontextaktionen ab.
        """

        repository = self._state_repository.fetch_repository_by_github_repo_id(github_repo_id)
        if repository is None:
            return None
        return self.capture_snapshot_for_repository(repository, trigger_type=trigger_type, force=force, job_id=job_id)

    def fetch_snapshots(self, repo_key: str, limit: int = 32) -> list[RepositorySnapshot]:
        """
        Laedt die Snapshot-Reihe eines Repositories inklusive Dateimenge.

        Eingabeparameter:
        - repo_key: Interner Repository-Schluessel.
        - limit: Maximale Anzahl geladener Snapshots.

        Rueckgabewerte:
        - Chronologisch sortierte Snapshot-Liste.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen.

        Wichtige interne Logik:
        - Die Methode reicht nur sauber gekapselt an die Job-Repository-Schicht durch.
        """

        return self._job_log_repository.fetch_repository_snapshots(repo_key=repo_key, limit=limit, include_files=True)

    def compare_snapshots(self, snapshot_a: RepositorySnapshot, snapshot_b: RepositorySnapshot) -> SnapshotDiffResult:
        """
        Vergleicht zwei Snapshots und leitet Datei-, Struktur- und Commit-Unterschiede ab.

        Eingabeparameter:
        - snapshot_a: Aelterer Snapshot.
        - snapshot_b: Neuerer Snapshot.

        Rueckgabewerte:
        - Zusammenfassung der relevanten Aenderungen.

        Moegliche Fehlerfaelle:
        - Snapshots ohne geladene Dateilisten liefern nur eingeschraenkte Diffs.

        Wichtige interne Logik:
        - Datei- und Strukturveraenderungen werden ueber relative Pfade paarweise verglichen.
        """

        files_a = {entry.relative_path: entry for entry in snapshot_a.files}
        files_b = {entry.relative_path: entry for entry in snapshot_b.files}
        new_files = sorted(path_text for path_text in files_b if path_text not in files_a and not files_b[path_text].is_deleted)
        deleted_files = sorted(path_text for path_text in files_a if path_text not in files_b or files_b.get(path_text, files_a[path_text]).is_deleted)
        structure_changes: list[str] = []
        file_type_changes: list[str] = []
        for relative_path in sorted(set(files_a) & set(files_b)):
            file_a = files_a[relative_path]
            file_b = files_b[relative_path]
            if file_a.path_type != file_b.path_type:
                structure_changes.append(f"{relative_path}: {file_a.path_type} -> {file_b.path_type}")
            if file_a.extension != file_b.extension:
                file_type_changes.append(f"{relative_path}: {file_a.extension or '-'} -> {file_b.extension or '-'}")
        return SnapshotDiffResult(
            previous_snapshot_id=snapshot_a.id,
            current_snapshot_id=snapshot_b.id,
            new_files=new_files,
            deleted_files=deleted_files,
            structure_changes=structure_changes,
            file_type_changes=file_type_changes,
            commit_changed=snapshot_a.head_commit != snapshot_b.head_commit,
            previous_head_commit=snapshot_a.head_commit,
            current_head_commit=snapshot_b.head_commit,
        )

    def _build_snapshot(self, repository: RepositoryState, trigger_type: str, job_id: str) -> RepositorySnapshot:
        """
        Baut aus State-, Datei- und Strukturdaten einen persistierbaren Snapshot auf.

        Eingabeparameter:
        - repository: Ausgangszustand des Repositories.
        - trigger_type: Fachlicher Snapshot-Ausloeser.
        - job_id: Optionale uebergeordnete Job-ID.

        Rueckgabewerte:
        - Vollstaendig vorbereiteter RepositorySnapshot.

        Moegliche Fehlerfaelle:
        - Datenbankfehler beim Lesen der zugehoerigen Dateidaten.

        Wichtige interne Logik:
        - Der Snapshot verwendet den vorhandenen Dateiindex aus `repo_files` und den
          Struktur-Vault, damit keine zusaetzlichen Dateisystemscans noetig sind.
        """

        repo_files = self._state_repository.fetch_repo_files(int(repository.id or 0), include_deleted=False)
        struct_source_type = "local" if repository.local_path else "remote_clone"
        struct_identifier = self._repo_struct_service.build_repo_identifier(
            local_path=repository.local_path,
            remote_repo_id=repository.github_repo_id,
            remote_url=repository.remote_url,
            repo_name=repository.name,
        )
        structure_items = self._repo_struct_repository.fetch_repo_items(
            repo_identifier=struct_identifier,
            source_type=struct_source_type,
            include_deleted=False,
        )
        snapshot_files = self._build_snapshot_files(repo_files, structure_items)
        structure_hash = self._build_structure_hash(snapshot_files)
        change_count = sum(1 for item in snapshot_files if item.git_status not in {"", "-", "clean"})
        return RepositorySnapshot(
            job_id=job_id or self._build_snapshot_job_id(repository.repo_key, trigger_type),
            repo_key=repository.repo_key,
            snapshot_timestamp=self._utc_now(),
            branch=repository.current_branch or repository.default_branch or "",
            head_commit=repository.head_commit or "",
            file_count=sum(1 for item in snapshot_files if item.path_type == "file" and not item.is_deleted),
            change_count=change_count,
            scan_fingerprint=repository.scan_fingerprint,
            structure_hash=structure_hash,
            action_type=trigger_type,
            source_type=repository.source_type,
            repo_name=repository.name,
            repo_owner=repository.remote_owner,
            local_path=repository.local_path,
            remote_url=repository.remote_url,
            status=repository.status or "success",
            structure_item_count=len(structure_items),
            files=snapshot_files,
        )

    def _build_snapshot_files(self, repo_files, structure_items) -> list[RepositorySnapshotFile]:
        """
        Kombiniert State-Dateiindex und Struktur-Vault zu einer diffbaren Snapshot-Dateiliste.

        Eingabeparameter:
        - repo_files: Persistierte RepoFileState-Liste aus `igitty_state.db`.
        - structure_items: Persistierte RepoTreeItem-Liste aus dem Struktur-Vault.

        Rueckgabewerte:
        - Normalisierte Snapshot-Dateiliste.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Teilquellen liefern nur weniger Details.

        Wichtige interne Logik:
        - Strukturdaten liefern Git-Status und Verzeichnisknoten, waehrend der Dateiindex
          stabile Content-Hashes fuer Diffs beisteuert.
        """

        structure_by_path = {item.relative_path: item for item in structure_items}
        snapshot_files: list[RepositorySnapshotFile] = []
        seen_paths: set[str] = set()
        for file_state in repo_files:
            structure_item = structure_by_path.get(file_state.relative_path)
            snapshot_files.append(
                RepositorySnapshotFile(
                    relative_path=file_state.relative_path,
                    path_type=file_state.path_type,
                    extension=(structure_item.extension if structure_item is not None else Path(file_state.relative_path).suffix.lower()),
                    content_hash=file_state.content_hash,
                    git_status=(structure_item.git_status if structure_item is not None else "clean"),
                    is_deleted=file_state.is_deleted,
                )
            )
            seen_paths.add(file_state.relative_path)
        for structure_item in structure_items:
            if structure_item.relative_path in seen_paths:
                continue
            snapshot_files.append(
                RepositorySnapshotFile(
                    relative_path=structure_item.relative_path,
                    path_type=structure_item.item_type,
                    extension=structure_item.extension,
                    content_hash="",
                    git_status=structure_item.git_status or "clean",
                    is_deleted=structure_item.is_deleted,
                )
            )
        snapshot_files.sort(key=lambda item: item.relative_path.lower())
        return snapshot_files

    def _build_structure_hash(self, snapshot_files: list[RepositorySnapshotFile]) -> str:
        """
        Erzeugt einen stabilen Hash ueber die bekannte Repository-Struktur.

        Eingabeparameter:
        - snapshot_files: Normalisierte Snapshot-Dateiliste.

        Rueckgabewerte:
        - Hexadezimale SHA256-Darstellung der aktuellen Struktur.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Hash beruecksichtigt Pfad, Knotentyp, Dateiendung und Git-Status, damit
          auch reine Struktur- oder Tracking-Aenderungen erkannt werden.
        """

        rendered = "\n".join(
            f"{item.relative_path}|{item.path_type}|{item.extension}|{item.git_status}|{int(item.is_deleted)}"
            for item in snapshot_files
        )
        return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    def _is_redundant_snapshot(self, latest_snapshot: RepositorySnapshot, current_snapshot: RepositorySnapshot) -> bool:
        """
        Prueft, ob ein neu vorbereiteter Snapshot inhaltlich redundant waere.

        Eingabeparameter:
        - latest_snapshot: Juengster bereits persistierter Snapshot.
        - current_snapshot: Neu vorbereiteter Snapshot.

        Rueckgabewerte:
        - `True`, wenn kein neuer Snapshot geschrieben werden sollte.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Fuer die Performance reicht ein Vergleich der wichtigsten Delta-Felder, statt
          jede Snapshot-Dateiliste komplett erneut zu vergleichen.
        """

        return (
            latest_snapshot.scan_fingerprint == current_snapshot.scan_fingerprint
            and latest_snapshot.structure_hash == current_snapshot.structure_hash
            and latest_snapshot.head_commit == current_snapshot.head_commit
            and latest_snapshot.file_count == current_snapshot.file_count
            and latest_snapshot.change_count == current_snapshot.change_count
        )

    def _build_snapshot_job_id(self, repo_key: str, trigger_type: str) -> str:
        """
        Erzeugt eine lesbare interne Job-ID fuer automatisch erzeugte Snapshots.

        Eingabeparameter:
        - repo_key: Stabiler Repository-Schluessel.
        - trigger_type: Snapshot-Ausloeser.

        Rueckgabewerte:
        - Interne Snapshot-Job-ID.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die ID erleichtert spaetere Rueckverfolgung, ohne einen separaten UUID-Zwang einzufuehren.
        """

        safe_key = repo_key.replace("::", "_").replace("\\", "_").replace("/", "_")
        return f"snapshot_{trigger_type}_{safe_key}_{int(datetime.now(timezone.utc).timestamp())}"

    def _utc_now(self) -> str:
        """
        Liefert einen einheitlichen UTC-Zeitstempel fuer Snapshot-Erzeugung.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - ISO-8601-Zeitstempel in UTC.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Einheitliche Zeitstempel vereinfachen Sortierung, Timeline und Tests.
        """

        return datetime.now(timezone.utc).isoformat()
