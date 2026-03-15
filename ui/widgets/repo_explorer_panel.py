"""RepoExplorer-Panel fuer den baumartigen Repository-Blick."""

from __future__ import annotations

from pathlib import PurePosixPath

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.struct_models import RepoTreeItem


class RepoExplorerPanel(QWidget):
    """Zeigt den persistierten Strukturbaum eines Repositories mit einfachen Filtern an."""

    def __init__(self, parent=None) -> None:
        """
        Baut das Explorer-Panel mit Baumansicht und Filtersteuerung auf.

        Eingabeparameter:
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der UI-Erstellung.

        Wichtige interne Logik:
        - Die Baumansicht liest spaeter nur noch vorbereitete Strukturdaten aus dem RepoContext.
        """

        super().__init__(parent)
        self._items: list[RepoTreeItem] = []

        layout = QVBoxLayout(self)
        filter_layout = QHBoxLayout()
        self._text_filter = QLineEdit()
        self._text_filter.setPlaceholderText("Pfad oder Dateiname filtern")
        self._extension_filter = QComboBox()
        self._extension_filter.addItem("Alle Endungen", "")
        filter_layout.addWidget(QLabel("Filter"))
        filter_layout.addWidget(self._text_filter, stretch=1)
        filter_layout.addWidget(QLabel("Extension"))
        filter_layout.addWidget(self._extension_filter)
        layout.addLayout(filter_layout)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["Pfad", "Typ", "Git Status", "Letzter Commit"])
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._tree, stretch=1)

        self._summary_label = QLabel("Keine Strukturinformationen vorhanden.")
        layout.addWidget(self._summary_label)

        self._text_filter.textChanged.connect(self._rebuild_tree)
        self._extension_filter.currentIndexChanged.connect(self._rebuild_tree)

    def set_items(self, items: list[RepoTreeItem]) -> None:
        """
        Uebernimmt die aktuellen Strukturknoten und baut den Explorer neu auf.

        Eingabeparameter:
        - items: Aus dem Struktur-Vault geladene Knoten.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; eine leere Liste fuehrt zu einer leeren Baumansicht.

        Wichtige interne Logik:
        - Die verfuegbaren Dateiendungen werden direkt aus den Daten abgeleitet, damit
          der Explorer ohne weitere Serviceaufrufe filtern kann.
        """

        self._items = items
        self._extension_filter.blockSignals(True)
        self._extension_filter.clear()
        self._extension_filter.addItem("Alle Endungen", "")
        extensions = sorted({item.extension for item in items if item.extension})
        for extension in extensions:
            self._extension_filter.addItem(extension, extension)
        self._extension_filter.blockSignals(False)
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        """
        Baut die sichtbare Baumansicht auf Basis der aktuellen Filter neu auf.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; unpassende Filter erzeugen einfach einen leeren Baum.

        Wichtige interne Logik:
        - Die Methode erstellt fehlende Elternknoten on-the-fly, damit auch bei
          teilgefilterten Treffern ein sauberer Baum sichtbar bleibt.
        """

        self._tree.clear()
        filter_text = self._text_filter.text().strip().lower()
        selected_extension = str(self._extension_filter.currentData() or "")
        visible_items = [
            item
            for item in self._items
            if self._matches_filters(item, filter_text, selected_extension)
        ]
        item_by_path: dict[str, QTreeWidgetItem] = {}
        for item in visible_items:
            path_parts = PurePosixPath(item.relative_path).parts
            parent_widget_item: QTreeWidgetItem | None = None
            accumulated_parts: list[str] = []
            for index, part in enumerate(path_parts):
                accumulated_parts.append(part)
                current_path = "/".join(accumulated_parts)
                widget_item = item_by_path.get(current_path)
                if widget_item is None:
                    widget_item = QTreeWidgetItem()
                    widget_item.setText(0, part)
                    if parent_widget_item is None:
                        self._tree.addTopLevelItem(widget_item)
                    else:
                        parent_widget_item.addChild(widget_item)
                    item_by_path[current_path] = widget_item
                parent_widget_item = widget_item
                if index == len(path_parts) - 1:
                    widget_item.setText(1, item.item_type)
                    widget_item.setText(2, item.git_status or "clean")
                    widget_item.setText(3, item.last_commit_hash[:12] if item.last_commit_hash else "-")
                    if item.git_status and item.git_status not in {"clean", "-"}:
                        widget_item.setForeground(2, self.palette().link())
                    widget_item.setData(0, Qt.ItemDataRole.UserRole, item.relative_path)
        self._tree.expandToDepth(1)
        self._summary_label.setText(
            f"{len(visible_items)} sichtbare Strukturknoten | Filter: {filter_text or '-'} | Extension: {selected_extension or 'alle'}"
        )

    def _matches_filters(self, item: RepoTreeItem, filter_text: str, selected_extension: str) -> bool:
        """
        Prueft, ob ein Strukturknoten den aktuell gesetzten Explorer-Filtern entspricht.

        Eingabeparameter:
        - item: Zu pruefender Strukturknoten.
        - filter_text: Kleingeschriebener Freitextfilter.
        - selected_extension: Aktuell ausgewaehlte Dateiendung oder Leerstring.

        Rueckgabewerte:
        - `True`, wenn der Knoten sichtbar sein soll.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Verzeichnisse werden bei aktivem Extension-Filter weiterhin gezeigt, wenn ihr
          Pfad zum Textfilter passt und dadurch den Baum lesbar haelt.
        """

        if filter_text and filter_text not in item.relative_path.lower():
            return False
        if selected_extension and item.item_type == "file" and item.extension != selected_extension:
            return False
        return True
