"""Einfacher RepoViewer auf Basis des Struktur-Vaults."""

from __future__ import annotations

from pathlib import PurePosixPath

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from models.struct_models import RepoTreeItem


class RepoViewerDialog(QDialog):
    """Zeigt die gespeicherte Repository-Struktur in einer baumartigen Ansicht an."""

    def __init__(self, repo_name: str, source_type: str, items: list[RepoTreeItem], parent=None) -> None:
        """
        Baut den RepoViewer fuer ein bestimmtes Repository auf.

        Eingabeparameter:
        - repo_name: Anzeigename des Repositories.
        - source_type: Herkunft des Repositories.
        - items: Bereits geladene Strukturknoten aus dem Vault.
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der UI-Erstellung.

        Wichtige interne Logik:
        - Nutzt ausschliesslich die gespeicherten SQLite-Daten und greift nicht direkt aufs Dateisystem zu.
        """

        super().__init__(parent)
        self.setWindowTitle(f"RepoViewer | {repo_name}")
        self.resize(1100, 760)
        layout = QVBoxLayout(self)
        header = QLabel(f"Repository: {repo_name} | Quelle: {source_type} | Strukturknoten: {len(items)}")
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Pfad", "Typ", "Groesse", "Extension", "Geaendert", "Git-Status", "Letzter Commit"])
        layout.addWidget(header)
        layout.addWidget(self._tree, stretch=1)
        self._populate_tree(items)

    def _populate_tree(self, items: list[RepoTreeItem]) -> None:
        """
        Fuellt den Baum aus den im Vault gespeicherten Strukturknoten.

        Eingabeparameter:
        - items: Bereits geladene Strukturknoten des Repositories.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Baut fehlende Zwischenknoten defensiv auf, damit auch unvollstaendige Pfadlisten darstellbar bleiben.
        """

        tree_index: dict[str, QTreeWidgetItem] = {}
        for item in items:
            normalized_path = item.relative_path.replace("\\", "/")
            path_obj = PurePosixPath(normalized_path)
            parent_node = self._tree.invisibleRootItem()
            current_prefix = ""
            for part in path_obj.parts:
                current_prefix = part if not current_prefix else f"{current_prefix}/{part}"
                tree_item = tree_index.get(current_prefix)
                if tree_item is None:
                    tree_item = QTreeWidgetItem(
                        [
                            part,
                            item.item_type if current_prefix == normalized_path else "dir",
                            str(item.size) if current_prefix == normalized_path and item.item_type == "file" else "",
                            item.extension if current_prefix == normalized_path else "",
                            item.last_modified if current_prefix == normalized_path else "",
                            item.git_status if current_prefix == normalized_path else "",
                            item.last_commit_hash if current_prefix == normalized_path else "",
                        ]
                    )
                    parent_node.addChild(tree_item)
                    tree_index[current_prefix] = tree_item
                parent_node = tree_item
        self._tree.expandToDepth(1)
