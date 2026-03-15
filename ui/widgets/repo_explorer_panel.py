"""RepoExplorer-Panel fuer den baumartigen Repository-Blick."""

from __future__ import annotations

from pathlib import PurePosixPath

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSplitter,
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
        self._items_by_path: dict[str, RepoTreeItem] = {}

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
        self._tree.setObjectName("repo_explorer_tree")

        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.addWidget(QLabel("Ausgewaehlter Knoten"))
        details_form = QFormLayout()
        self._detail_path_label = QLabel("-")
        self._detail_type_label = QLabel("-")
        self._detail_extension_label = QLabel("-")
        self._detail_git_status_label = QLabel("-")
        self._detail_size_label = QLabel("-")
        self._detail_last_modified_label = QLabel("-")
        self._detail_last_commit_label = QLabel("-")
        self._detail_last_scan_label = QLabel("-")
        self._detail_deleted_label = QLabel("-")
        self._detail_hint_label = QLabel("Kein Strukturknoten ausgewaehlt.")
        self._detail_path_label.setWordWrap(True)
        self._detail_last_commit_label.setWordWrap(True)
        self._detail_hint_label.setWordWrap(True)
        details_form.addRow("Pfad", self._detail_path_label)
        details_form.addRow("Typ", self._detail_type_label)
        details_form.addRow("Extension", self._detail_extension_label)
        details_form.addRow("Git Status", self._detail_git_status_label)
        details_form.addRow("Groesse", self._detail_size_label)
        details_form.addRow("Letzte Aenderung", self._detail_last_modified_label)
        details_form.addRow("Letzter Commit", self._detail_last_commit_label)
        details_form.addRow("Letzter Scan", self._detail_last_scan_label)
        details_form.addRow("Geloescht", self._detail_deleted_label)
        details_layout.addLayout(details_form)
        details_layout.addWidget(QLabel("Hinweis"))
        details_layout.addWidget(self._detail_hint_label)
        details_layout.addStretch(1)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._tree)
        self._splitter.addWidget(details_widget)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        layout.addWidget(self._splitter, stretch=1)

        self._summary_label = QLabel("Keine Strukturinformationen vorhanden.")
        layout.addWidget(self._summary_label)

        self._text_filter.textChanged.connect(self._rebuild_tree)
        self._extension_filter.currentIndexChanged.connect(self._rebuild_tree)
        self._tree.itemSelectionChanged.connect(self._update_details_for_selection)

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
        self._items_by_path = {item.relative_path: item for item in items}
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
        self._detail_hint_label.setText("Kein Strukturknoten ausgewaehlt.")
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
                    widget_item.setData(0, Qt.ItemDataRole.UserRole, current_path)
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
        if self._tree.topLevelItemCount() > 0:
            self._tree.setCurrentItem(self._tree.topLevelItem(0))
        else:
            self._clear_details()

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

    def _update_details_for_selection(self) -> None:
        """
        Aktualisiert den rechten Details-Bereich fuer den aktuell ausgewaehlten Baumknoten.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehlende oder synthetische Zwischenknoten werden defensiv mit Platzhalterdaten angezeigt.

        Wichtige interne Logik:
        - Der Explorer zeigt fuer echte Vault-Knoten deren bekannte Metadaten.
        - Fuer reine Zwischenordner aus einem gefilterten Teilbaum bleibt trotzdem ein
          lesbarer Kontext sichtbar, statt einfach leere Werte stehen zu lassen.
        """

        current_item = self._tree.currentItem()
        if current_item is None:
            self._clear_details()
            return
        relative_path = str(current_item.data(0, Qt.ItemDataRole.UserRole) or "")
        repo_item = self._items_by_path.get(relative_path)
        if repo_item is None:
            self._detail_path_label.setText(relative_path or current_item.text(0) or "-")
            self._detail_type_label.setText("Zwischenknoten")
            self._detail_extension_label.setText("-")
            self._detail_git_status_label.setText("-")
            self._detail_size_label.setText("-")
            self._detail_last_modified_label.setText("-")
            self._detail_last_commit_label.setText("-")
            self._detail_last_scan_label.setText("-")
            self._detail_deleted_label.setText("-")
            self._detail_hint_label.setText(
                "Dieser Ordnerknoten wurde fuer die Baumdarstellung aus gefilterten Unterpfaden aufgebaut."
            )
            return

        self._detail_path_label.setText(repo_item.relative_path or "-")
        self._detail_type_label.setText(repo_item.item_type or "-")
        self._detail_extension_label.setText(repo_item.extension or "-")
        self._detail_git_status_label.setText(repo_item.git_status or "clean")
        self._detail_size_label.setText(self._format_size(repo_item.size))
        self._detail_last_modified_label.setText(repo_item.last_modified or "-")
        self._detail_last_commit_label.setText(repo_item.last_commit_hash or "-")
        self._detail_last_scan_label.setText(repo_item.version_scan_timestamp or "-")
        self._detail_deleted_label.setText("Ja" if repo_item.is_deleted else "Nein")
        self._detail_hint_label.setText(self._build_item_hint(repo_item))

    def _clear_details(self) -> None:
        """
        Setzt den Details-Bereich auf einen neutralen Leerzustand zurueck.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Ruecksetzung verhindert, dass alte Dateidetails sichtbar bleiben, wenn der
          Explorer durch Filter oder leere Datenquellen keinen Knoten mehr zeigt.
        """

        self._detail_path_label.setText("-")
        self._detail_type_label.setText("-")
        self._detail_extension_label.setText("-")
        self._detail_git_status_label.setText("-")
        self._detail_size_label.setText("-")
        self._detail_last_modified_label.setText("-")
        self._detail_last_commit_label.setText("-")
        self._detail_last_scan_label.setText("-")
        self._detail_deleted_label.setText("-")
        self._detail_hint_label.setText("Kein Strukturknoten ausgewaehlt.")

    def _format_size(self, size: int) -> str:
        """
        Formatiert Dateigroessen fuer die kompakte Anzeige im Explorer.

        Eingabeparameter:
        - size: Rohgroesse in Bytes.

        Rueckgabewerte:
        - Lesbarer Groessentext fuer die UI.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Kleine Dateien bleiben in Bytes sichtbar, groessere werden bewusst knapp in KB
          oder MB ausgegeben, damit der Details-Bereich schnell lesbar bleibt.
        """

        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def _build_item_hint(self, item: RepoTreeItem) -> str:
        """
        Baut einen kurzen Interpretationstext fuer den ausgewaehlten Strukturknoten.

        Eingabeparameter:
        - item: Aus dem Struktur-Vault geladener Knoten.

        Rueckgabewerte:
        - Kurzer, menschlich lesbarer Hinweistext.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Hinweis verdichtet technische Metadaten zu einer schnell lesbaren Aussage,
          ohne dass der Benutzer mehrere Spalten gleichzeitig interpretieren muss.
        """

        if item.item_type == "dir":
            return "Ordnerknoten aus dem Struktur-Vault."
        if item.git_status and item.git_status not in {"clean", "-"}:
            return f"Datei mit Git-Status '{item.git_status}' im letzten bekannten Struktur-Scan."
        return "Datei ohne besonderen Git-Hinweis im letzten bekannten Struktur-Scan."
