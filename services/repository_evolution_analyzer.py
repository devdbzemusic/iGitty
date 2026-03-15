"""Analyse der Repository-Entwicklung auf Basis persistierter Snapshots."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from models.evolution_models import RepositoryEvolutionSummary, RepositorySnapshot, SnapshotDiffResult
from services.repository_snapshot_service import RepositorySnapshotService


class RepositoryEvolutionAnalyzer:
    """Analysiert Snapshot-Reihen und leitet daraus Evolutionsmetriken ab."""

    def __init__(self, snapshot_service: RepositorySnapshotService) -> None:
        """
        Initialisiert den Analyzer mit Zugriff auf Snapshot-Diffs.

        Eingabeparameter:
        - snapshot_service: Service fuer Snapshot-Lesen und Snapshot-Vergleiche.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Analyzer bleibt rein lesend und arbeitet ausschliesslich auf bereits
          persistierten Snapshot-Daten.
        """

        self._snapshot_service = snapshot_service

    def analyze(self, snapshots: list[RepositorySnapshot]) -> tuple[RepositoryEvolutionSummary, list[SnapshotDiffResult]]:
        """
        Analysiert eine chronologische Snapshot-Reihe und berechnet Evolutionsmetriken.

        Eingabeparameter:
        - snapshots: Chronologisch sortierte Snapshot-Liste eines Repositories.

        Rueckgabewerte:
        - Tupel aus zusammenfassender Evolution und den aufeinanderfolgenden Snapshot-Diffs.

        Moegliche Fehlerfaelle:
        - Keine; leere Listen liefern eine stabile leere Zusammenfassung.

        Wichtige interne Logik:
        - Die Analyse ist bewusst heuristisch und leichtgewichtig, damit sie im RepoViewer
          ohne zusaetzliche Hintergrundjobs lauffaehig bleibt.
        """

        if not snapshots:
            return RepositoryEvolutionSummary(), []

        diffs: list[SnapshotDiffResult] = []
        interval_lines: list[str] = []
        for previous_snapshot, current_snapshot in zip(snapshots, snapshots[1:]):
            diff = self._snapshot_service.compare_snapshots(previous_snapshot, current_snapshot)
            diffs.append(diff)
            interval_lines.append(
                (
                    f"{previous_snapshot.snapshot_timestamp} -> {current_snapshot.snapshot_timestamp} | "
                    f"+{len(diff.new_files)} / -{len(diff.deleted_files)} / "
                    f"Struktur={len(diff.structure_changes)} / Typwechsel={len(diff.file_type_changes)}"
                )
            )

        file_type_counter: Counter[str] = Counter()
        for snapshot in snapshots:
            for file_entry in snapshot.files:
                if file_entry.path_type != "file" or file_entry.is_deleted:
                    continue
                file_type_counter[file_entry.extension or "(ohne Endung)"] += 1

        growth_rate = 0.0
        if len(snapshots) > 1:
            growth_rate = (snapshots[-1].file_count - snapshots[0].file_count) / max(1, len(snapshots) - 1)

        summary = RepositoryEvolutionSummary(
            snapshot_count=len(snapshots),
            growth_rate_per_snapshot=growth_rate,
            current_file_count=snapshots[-1].file_count,
            peak_file_count=max(snapshot.file_count for snapshot in snapshots),
            most_common_file_types=[
                f"{extension}: {count}"
                for extension, count in file_type_counter.most_common(5)
            ],
            structure_changes_per_interval=interval_lines,
            activity_phases=self._build_activity_phases(snapshots),
        )
        return summary, diffs

    def _build_activity_phases(self, snapshots: list[RepositorySnapshot]) -> list[str]:
        """
        Leitet grobe Aktivitaetsphasen ueber Zeitabstaende zwischen Snapshots ab.

        Eingabeparameter:
        - snapshots: Chronologisch sortierte Snapshot-Liste.

        Rueckgabewerte:
        - Liste lesbarer Aktivitaetsphasen.

        Moegliche Fehlerfaelle:
        - Ungueltige Zeitstempel werden defensiv uebersprungen.

        Wichtige interne Logik:
        - Kurze Abstaende werden als aktive Phase interpretiert, grosse Luecken als Ruhephase.
        """

        if len(snapshots) < 2:
            return ["Nur ein Snapshot vorhanden, noch keine Aktivitaetsphase ableitbar."]

        phases: list[str] = []
        for previous_snapshot, current_snapshot in zip(snapshots, snapshots[1:]):
            try:
                previous_timestamp = datetime.fromisoformat(previous_snapshot.snapshot_timestamp)
                current_timestamp = datetime.fromisoformat(current_snapshot.snapshot_timestamp)
            except ValueError:
                continue
            gap_minutes = (current_timestamp - previous_timestamp).total_seconds() / 60
            if gap_minutes <= 30:
                phase = "aktive Phase"
            elif gap_minutes <= 240:
                phase = "moderate Phase"
            else:
                phase = "Ruhephase"
            phases.append(
                f"{previous_snapshot.snapshot_timestamp} -> {current_snapshot.snapshot_timestamp}: {phase} ({gap_minutes:.1f} min Abstand)"
            )
        return phases or ["Keine belastbaren Aktivitaetsphasen ermittelbar."]
