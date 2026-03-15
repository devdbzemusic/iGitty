"""Timeline-Panel fuer Repository Time-Travel und Ereignisverlauf."""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from models.evolution_models import RepositoryTimelineEntry


class RepositoryTimelinePanel(QWidget):
    """Zeigt Snapshots, Aktionen, Diagnosen und Scan-Laeufe als chronologische Timeline an."""

    def __init__(self, parent=None) -> None:
        """
        Baut das Timeline-Panel mit tabellarischer Chronologieansicht auf.

        Eingabeparameter:
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Widget-Erstellung.

        Wichtige interne Logik:
        - Die Tabelle bleibt bewusst schlicht, damit die Zeitreiseansicht auch bei vielen
          Eintraegen gut lesbar und performant bleibt.
        """

        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Zeit", "Typ", "Titel", "Details"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def set_entries(self, entries: list[RepositoryTimelineEntry]) -> None:
        """
        Uebernimmt die normalisierte Timeline-Reihe in die Tabellenansicht.

        Eingabeparameter:
        - entries: Bereits sortierte Timeline-Eintraege.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; eine leere Timeline erzeugt eine Platzhalterzeile.

        Wichtige interne Logik:
        - Das Widget fuehrt selbst keine Sortier- oder Analyse-Logik aus und bleibt rein darstellend.
        """

        rows = entries or [
            RepositoryTimelineEntry(
                timestamp="-",
                entry_type="-",
                title="Keine Timeline-Eintraege vorhanden.",
                details="",
            )
        ]
        self._table.setRowCount(len(rows))
        for row_index, entry in enumerate(rows):
            self._table.setItem(row_index, 0, QTableWidgetItem(entry.timestamp or "-"))
            self._table.setItem(row_index, 1, QTableWidgetItem(entry.entry_type or "-"))
            self._table.setItem(row_index, 2, QTableWidgetItem(entry.title or "-"))
            self._table.setItem(row_index, 3, QTableWidgetItem(entry.details or "-"))
