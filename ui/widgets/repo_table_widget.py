"""Wiederverwendbares Tabellenwidget mit Filter und Checkboxen."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class RepoTableWidget(QGroupBox):
    """Kapselt Tabellenanzeige, Filter und Sammelauswahl fuer Repository-Listen."""

    filter_text_changed = Signal(str)
    row_activated = Signal(int)

    def __init__(self, title: str, columns: list[str]) -> None:
        """
        Erstellt das Widget fuer eine einzelne Repository-Liste.

        Eingabeparameter:
        - title: Sichtbarer Titel des Bereichs.
        - columns: Spaltennamen fuer die Tabelle.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Widget ist generisch genug fuer Remote- und Local-Pane.
        """

        super().__init__(title)
        self._columns = columns
        self._table = QTableWidget()
        self._filter_input = QLineEdit()
        self._select_all_checkbox = QCheckBox("Alle auswaehlen")
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        """
        Baut das interne Layout des Tabellenwidgets auf.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Tabelle wird auf zeilenweises Verhalten und flexible Spaltenbreiten getrimmt.
        """

        layout = QVBoxLayout(self)
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_input.setPlaceholderText("Filter nach sichtbaren Tabellenspalten")
        toolbar_layout.addWidget(self._select_all_checkbox)
        toolbar_layout.addWidget(self._filter_input, stretch=1)

        self._table.setColumnCount(len(self._columns))
        self._table.setHorizontalHeaderLabels(self._columns)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(toolbar)
        layout.addWidget(self._table, stretch=1)

    def _wire_signals(self) -> None:
        """
        Verbindet UI-Ereignisse innerhalb des Widgets.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Widget emittiert nur den Filtertext nach aussen; die Sammelauswahl wird intern verarbeitet.
        """

        self._filter_input.textChanged.connect(self.filter_text_changed.emit)
        self._select_all_checkbox.toggled.connect(self._toggle_all_rows)
        self._table.itemDoubleClicked.connect(self._emit_row_activation)

    def populate_rows(self, rows: list[list[str]]) -> None:
        """
        Ersetzt den kompletten Tabelleninhalt durch neue Zeilen.

        Eingabeparameter:
        - rows: Bereits aufbereitete Zellwerte pro Zeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Inkonsistente Spaltenanzahl fuehrt zu leeren Zellen, wird aber defensiv aufgefangen.

        Wichtige interne Logik:
        - Jede Zeile erhaelt in Spalte 0 eine aktive Checkbox.
        """

        self._table.setRowCount(len(rows))
        for row_index, row_values in enumerate(rows):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self._table.setItem(row_index, 0, checkbox_item)

            for column_index in range(1, len(self._columns)):
                value = row_values[column_index] if column_index < len(row_values) else ""
                self._table.setItem(row_index, column_index, QTableWidgetItem(value))

        self._table.resizeColumnsToContents()

    def apply_filter(self, filter_text: str) -> None:
        """
        Blendet Tabellenzeilen anhand eines einfachen Freitextfilters ein oder aus.

        Eingabeparameter:
        - filter_text: Suchbegriff fuer die aktuelle Repository-Liste.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Filter prueft alle sichtbaren Textspalten ausser der Checkbox-Spalte.
        """

        normalized = filter_text.strip().lower()
        for row_index in range(self._table.rowCount()):
            if not normalized:
                self._table.setRowHidden(row_index, False)
                continue

            row_matches = False
            for column_index in range(1, self._table.columnCount()):
                item = self._table.item(row_index, column_index)
                if item and normalized in item.text().lower():
                    row_matches = True
                    break
            self._table.setRowHidden(row_index, not row_matches)

    def _toggle_all_rows(self, checked: bool) -> None:
        """
        Setzt die Checkbox jeder aktuell sichtbaren Zeile auf denselben Zustand.

        Eingabeparameter:
        - checked: Zielzustand fuer alle Zeilencheckboxen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Versteckte Zeilen bleiben unberuehrt, damit Filter und Auswahl sauber zusammenspielen.
        """

        target_state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row_index in range(self._table.rowCount()):
            if self._table.isRowHidden(row_index):
                continue
            item = self._table.item(row_index, 0)
            if item is not None:
                item.setCheckState(target_state)

    def checked_row_indices(self) -> list[int]:
        """
        Liefert die Indizes aller aktuell angehakten Tabellenzeilen zurueck.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Liste aller Zeilenindizes mit gesetzter Checkbox.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Methode bildet die generische Bruecke zwischen UI-Auswahl und Fachobjekten.
        """

        checked_indices: list[int] = []
        for row_index in range(self._table.rowCount()):
            item = self._table.item(row_index, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                checked_indices.append(row_index)
        return checked_indices

    def _emit_row_activation(self, item: QTableWidgetItem) -> None:
        """
        Meldet einen Doppelklick auf eine Tabellenzeile als Zeilenindex nach aussen.

        Eingabeparameter:
        - item: Das von Qt gemeldete Tabellenitem des Doppelklicks.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Widget abstrahiert das konkrete Qt-Item auf einen stabilen Zeilenindex.
        """

        self.row_activated.emit(item.row())
