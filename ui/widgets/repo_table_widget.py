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
    row_context_requested = Signal(int)
    row_selected = Signal(int)

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
        normalized_title = title.lower().replace(" ", "_").replace("-", "_")
        self.setObjectName(f"{normalized_title}_group")
        self._table.setObjectName(f"{normalized_title}_table")
        self._filter_input.setObjectName(f"{normalized_title}_filter")
        self._select_all_checkbox.setObjectName(f"{normalized_title}_select_all")
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
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
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
        self._table.customContextMenuRequested.connect(self._emit_context_request)
        self._table.itemSelectionChanged.connect(self._emit_selected_row)

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
        self.apply_filter(self._filter_input.text())

    def insert_row(self, row_index: int, row_values: list[str]) -> None:
        """
        Fuegt genau eine neue Tabellenzeile an einer bestimmten Position ein.

        Eingabeparameter:
        - row_index: Zielposition fuer die neue Zeile.
        - row_values: Bereits vorbereitete Zellwerte der neuen Zeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Positionen werden von Qt defensiv behandelt.

        Wichtige interne Logik:
        - Die Methode erlaubt gezielte Delta-Updates, ohne die komplette Tabelle neu aufzubauen.
        """

        self._table.insertRow(row_index)
        self._write_row(row_index, row_values)
        self._table.resizeColumnsToContents()
        self.apply_filter(self._filter_input.text())

    def update_row(self, row_index: int, row_values: list[str]) -> None:
        """
        Aktualisiert die Textzellen einer bestehenden Tabellenzeile gezielt.

        Eingabeparameter:
        - row_index: Zielzeile der Aktualisierung.
        - row_values: Neue Zellwerte fuer die Zeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Zeilen werden von Qt defensiv ignoriert.

        Wichtige interne Logik:
        - Checkbox-Spalte und restliche Zellen bleiben in derselben Tabellenzeile erhalten,
          was partielle UI-Aktualisierungen deutlich guenstiger macht.
        """

        self._write_row(row_index, row_values)
        self._table.resizeColumnsToContents()
        self.apply_filter(self._filter_input.text())

    def remove_row(self, row_index: int) -> None:
        """
        Entfernt genau eine Tabellenzeile aus der internen Qt-Tabelle.

        Eingabeparameter:
        - row_index: Zu entfernende Zeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Zeilen werden von Qt defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode ist Teil der Delta-Update-Unterstuetzung fuer STUFE 2.
        """

        self._table.removeRow(row_index)
        self.apply_filter(self._filter_input.text())

    def row_count(self) -> int:
        """
        Liefert die aktuelle Anzahl sichtbarer Datenzeilen der Tabelle.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Anzahl der aktuell vorhandenen Tabellenzeilen.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der schmale Getter erleichtert gezielte UI-Operationen ausserhalb des Widgets.
        """

        return self._table.rowCount()

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

    def set_item(self, row_index: int, column_index: int, item: QTableWidgetItem) -> None:
        """
        Setzt ein einzelnes Tabellenitem gezielt in der internen Qt-Tabelle.

        Eingabeparameter:
        - row_index: Zielzeile.
        - column_index: Zielspalte.
        - item: Vollstaendig vorbereitetes Tabellenitem.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Zeilen- oder Spaltenindizes werden von Qt ignoriert.

        Wichtige interne Logik:
        - Ermoeglicht spezialisierte Zelltypen, ohne das gesamte Widget fachlich zu spezialisieren.
        """

        self._table.setItem(row_index, column_index, item)

    def set_cell_widget(self, row_index: int, column_index: int, widget: QWidget) -> None:
        """
        Setzt ein QWidget als Zellinhalt in der internen Tabelle.

        Eingabeparameter:
        - row_index: Zielzeile.
        - column_index: Zielspalte.
        - widget: Darzustellendes Zell-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Indizes werden von Qt ignoriert.

        Wichtige interne Logik:
        - Wird fuer Anzeige-Checkboxen ohne Aenderung der generischen Tabellenlogik genutzt.
        """

        self._table.setCellWidget(row_index, column_index, widget)

    def set_row_background(self, row_index: int, color_hex: str) -> None:
        """
        Faerbt alle darstellbaren Zellen einer Tabellenzeile ein.

        Eingabeparameter:
        - row_index: Zielzeile fuer die farbliche Markierung.
        - color_hex: Hex-Farbwert wie `#552222`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Farbwerte werden von Qt defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode ermoeglicht Statusmarkierungen, ohne das Widget fachlich auf eine Liste festzulegen.
        """

        from PySide6.QtGui import QColor

        color = QColor(color_hex)
        for column_index in range(self._table.columnCount()):
            item = self._table.item(row_index, column_index)
            if item is not None:
                item.setBackground(color)

    def clear_row_background(self, row_index: int) -> None:
        """
        Entfernt gesetzte Hintergrundfarben einer Tabellenzeile wieder.

        Eingabeparameter:
        - row_index: Zielzeile der Ruecksetzung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Zeilen werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode wird fuer gezielte Delta-Updates benoetigt, wenn ein Eintrag
          seinen Problemstatus wieder verliert.
        """

        from PySide6.QtGui import QBrush

        for column_index in range(self._table.columnCount()):
            item = self._table.item(row_index, column_index)
            if item is not None:
                item.setBackground(QBrush())

    def _emit_context_request(self, position) -> None:
        """
        Meldet die Tabellenzeile eines Kontextmenue-Aufrufs nach aussen.

        Eingabeparameter:
        - position: Von Qt gelieferte lokale Mausposition innerhalb der Tabelle.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Klicks ausserhalb gueltiger Zeilen werden ignoriert.

        Wichtige interne Logik:
        - Die Signalisierung bleibt bewusst generisch, damit das Hauptfenster das eigentliche Menue erstellt.
        """

        item = self._table.itemAt(position)
        if item is not None:
            self.row_context_requested.emit(item.row())

    def _emit_selected_row(self) -> None:
        """
        Meldet die aktuell selektierte Zeile nach aussen.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Leere Tabellen oder keine Auswahl fuehren zu keinem Signal.

        Wichtige interne Logik:
        - Die Selektion bleibt rein technisch und ueberlaesst jede fachliche Reaktion dem Controller.
        """

        selected_items = self._table.selectedItems()
        if selected_items:
            self.row_selected.emit(selected_items[0].row())

    def _write_row(self, row_index: int, row_values: list[str]) -> None:
        """
        Schreibt die Standardzellen einer Tabellenzeile inklusive Checkbox-Spalte.

        Eingabeparameter:
        - row_index: Zielzeile innerhalb der Tabelle.
        - row_values: Bereits vorbereitete Zellwerte pro Spalte.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Inkonsistente Spaltenanzahl fuehrt defensiv zu leeren Zellen.

        Wichtige interne Logik:
        - Die gemeinsame interne Schreiblogik haelt Vollaufbau und Delta-Updates konsistent.
        """

        checkbox_item = self._table.item(row_index, 0)
        check_state = Qt.CheckState.Unchecked
        if checkbox_item is not None:
            check_state = checkbox_item.checkState()
        checkbox_item = QTableWidgetItem()
        checkbox_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsSelectable
        )
        checkbox_item.setCheckState(check_state)
        self._table.setItem(row_index, 0, checkbox_item)

        for column_index in range(1, len(self._columns)):
            value = row_values[column_index] if column_index < len(row_values) else ""
            existing_item = self._table.item(row_index, column_index)
            if existing_item is None:
                self._table.setItem(row_index, column_index, QTableWidgetItem(value))
            else:
                existing_item.setText(value)
