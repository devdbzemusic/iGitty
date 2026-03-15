"""Tests fuer den Dateibaum-Explorer im RepoViewer."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

from models.struct_models import RepoTreeItem
from ui.widgets.repo_explorer_panel import RepoExplorerPanel


def _get_or_create_application() -> QApplication:
    """
    Liefert eine vorhandene Qt-Anwendung oder erzeugt eine neue Testinstanz.
    """

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_repo_explorer_panel_updates_detail_view_for_selected_file() -> None:
    """
    Prueft, dass der Explorer fuer ausgewaehlte Dateien rechts die Knotenmetadaten anzeigt.
    """

    _get_or_create_application()
    panel = RepoExplorerPanel()
    panel.set_items(
        [
            RepoTreeItem(
                repo_identifier="local::demo",
                relative_path="src/app.py",
                item_type="file",
                size=2048,
                extension=".py",
                last_modified="2026-03-15T12:00:00+00:00",
                git_status="M",
                last_commit_hash="abcdef1234567890",
                version_scan_timestamp="2026-03-15T12:05:00+00:00",
            )
        ]
    )

    top_level_item = panel._tree.topLevelItem(0)  # noqa: SLF001
    assert top_level_item is not None
    file_item = top_level_item.child(0)
    assert file_item is not None

    panel._tree.setCurrentItem(file_item)  # noqa: SLF001
    panel._update_details_for_selection()  # noqa: SLF001

    assert panel._detail_path_label.text() == "src/app.py"  # noqa: SLF001
    assert panel._detail_extension_label.text() == ".py"  # noqa: SLF001
    assert panel._detail_git_status_label.text() == "M"  # noqa: SLF001
    assert panel._detail_size_label.text() == "2.0 KB"  # noqa: SLF001


def test_repo_explorer_panel_filters_by_extension_and_keeps_tree_readable() -> None:
    """
    Prueft, dass der Extension-Filter Dateiknoten reduziert, aber den Pfadbaum weiter sichtbar laesst.
    """

    _get_or_create_application()
    panel = RepoExplorerPanel()
    panel.set_items(
        [
            RepoTreeItem(repo_identifier="local::demo", relative_path="src/app.py", item_type="file", extension=".py"),
            RepoTreeItem(repo_identifier="local::demo", relative_path="src/readme.md", item_type="file", extension=".md"),
        ]
    )

    py_index = panel._extension_filter.findData(".py")  # noqa: SLF001
    assert py_index >= 0
    panel._extension_filter.setCurrentIndex(py_index)  # noqa: SLF001

    assert panel._tree.topLevelItemCount() == 1  # noqa: SLF001
    top_level_item = panel._tree.topLevelItem(0)  # noqa: SLF001
    assert top_level_item.text(0) == "src"
    assert top_level_item.childCount() == 1
    assert top_level_item.child(0).text(0) == "app.py"
