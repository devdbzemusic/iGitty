"""Historien-Panel fuer Repository-Aktionen im RepoViewer."""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from models.job_models import ActionSummary


class RepoHistoryPanel(QWidget):
    """Zeigt die juengste Job- und Aktionshistorie eines Repositories tabellarisch an."""

    def __init__(self, parent=None) -> None:
        """
        Baut das Historien-Panel mit kompakter Tabellenansicht auf.

        Eingabeparameter:
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Widget-Erstellung.

        Wichtige interne Logik:
        - Die Tabelle bleibt bewusst einfach, damit Diagnose und Nachvollziehbarkeit im Vordergrund stehen.
        """

        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Zeit", "Aktion", "Status", "Nachricht"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def set_entries(self, entries: list[ActionSummary]) -> None:
        """
        Uebernimmt die strukturierte Repository-Historie in die Tabellenansicht.

        Eingabeparameter:
        - entries: Juengste Historieneintraege aus der Jobs-DB.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; eine leere Historie wird als einzelne Platzhalterzeile dargestellt.

        Wichtige interne Logik:
        - Die Tabelle arbeitet rein auf dem vorbereiteten View-Model und kennt keine DB-Details.
        """

        rows = entries or [ActionSummary(action_type="-", status="-", timestamp="-", message="Keine Historie vorhanden.")]
        self._table.setRowCount(len(rows))
        for row_index, entry in enumerate(rows):
            self._table.setItem(row_index, 0, QTableWidgetItem(entry.timestamp or "-"))
            self._table.setItem(row_index, 1, QTableWidgetItem(entry.action_type or "-"))
            self._table.setItem(row_index, 2, QTableWidgetItem(entry.status or "-"))
            self._table.setItem(row_index, 3, QTableWidgetItem(entry.message or "-"))
