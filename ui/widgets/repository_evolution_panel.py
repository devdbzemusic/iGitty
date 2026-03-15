"""Evolution-Panel fuer Wachstums- und Strukturentwicklung eines Repositories."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QListWidget, QFormLayout, QVBoxLayout, QWidget

from models.evolution_models import RepositoryEvolutionSummary, SnapshotDiffResult


class RepositoryEvolutionPanel(QWidget):
    """Zeigt die zusammengefasste Entwicklung und Snapshot-Diffs eines Repositories an."""

    def __init__(self, parent=None) -> None:
        """
        Baut das Evolution-Panel mit Kennzahlen- und Listenansicht auf.

        Eingabeparameter:
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Widget-Erstellung.

        Wichtige interne Logik:
        - Die Darstellung trennt kompakte Kennzahlen von den diffbasierten Verlaufsdetails,
          damit auch groessere Snapshot-Reihen schnell erfassbar bleiben.
        """

        super().__init__(parent)
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self._snapshot_count_label = QLabel("0")
        self._growth_rate_label = QLabel("0.00")
        self._current_file_count_label = QLabel("0")
        self._peak_file_count_label = QLabel("0")
        form_layout.addRow("Snapshots", self._snapshot_count_label)
        form_layout.addRow("Wachstum / Snapshot", self._growth_rate_label)
        form_layout.addRow("Aktuelle Dateien", self._current_file_count_label)
        form_layout.addRow("Peak Dateien", self._peak_file_count_label)
        layout.addLayout(form_layout)

        self._file_types_list = QListWidget()
        self._interval_changes_list = QListWidget()
        self._activity_phases_list = QListWidget()
        self._diffs_list = QListWidget()
        layout.addWidget(QLabel("Haeufigste Dateitypen"))
        layout.addWidget(self._file_types_list)
        layout.addWidget(QLabel("Strukturaenderungen pro Intervall"))
        layout.addWidget(self._interval_changes_list)
        layout.addWidget(QLabel("Aktivitaetsphasen"))
        layout.addWidget(self._activity_phases_list)
        layout.addWidget(QLabel("Snapshot-Diffs"))
        layout.addWidget(self._diffs_list, stretch=1)

    def set_analysis(self, summary: RepositoryEvolutionSummary | None, diffs: list[SnapshotDiffResult]) -> None:
        """
        Uebernimmt Evolutionszusammenfassung und Snapshot-Diffs in die UI.

        Eingabeparameter:
        - summary: Kompakte Evolutionszusammenfassung oder `None`.
        - diffs: Liste aufeinanderfolgender Snapshot-Diffs.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Daten werden durch stabile Platzhalter ersetzt.

        Wichtige interne Logik:
        - Die Methode bleibt rein darstellend und formatiert die Daten bewusst knapp.
        """

        effective_summary = summary or RepositoryEvolutionSummary()
        self._snapshot_count_label.setText(str(effective_summary.snapshot_count))
        self._growth_rate_label.setText(f"{effective_summary.growth_rate_per_snapshot:.2f}")
        self._current_file_count_label.setText(str(effective_summary.current_file_count))
        self._peak_file_count_label.setText(str(effective_summary.peak_file_count))
        self._replace_list(self._file_types_list, effective_summary.most_common_file_types, "Noch keine Dateityp-Analyse vorhanden.")
        self._replace_list(
            self._interval_changes_list,
            effective_summary.structure_changes_per_interval,
            "Noch keine Intervallveraenderungen vorhanden.",
        )
        self._replace_list(self._activity_phases_list, effective_summary.activity_phases, "Noch keine Aktivitaetsphasen vorhanden.")
        self._replace_list(
            self._diffs_list,
            [
                (
                    f"#{diff.previous_snapshot_id}->{diff.current_snapshot_id} | "
                    f"+{len(diff.new_files)} / -{len(diff.deleted_files)} / "
                    f"Struktur={len(diff.structure_changes)} / Typwechsel={len(diff.file_type_changes)} / "
                    f"Commit={'Ja' if diff.commit_changed else 'Nein'}"
                )
                for diff in diffs
            ],
            "Noch keine Snapshot-Diffs vorhanden.",
        )

    def _replace_list(self, widget: QListWidget, entries: list[str], fallback: str) -> None:
        """
        Ersetzt den Inhalt einer Listenansicht durch neue oder fallback-basierte Eintraege.

        Eingabeparameter:
        - widget: Ziel-Listenwidget.
        - entries: Neue zu uebernehmende Zeilen.
        - fallback: Platzhaltertext fuer leere Listen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Kleine Hilfsmethode gegen duplizierte Listenlogik in der UI.
        """

        widget.clear()
        widget.addItems(entries or [fallback])
