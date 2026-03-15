"""Nicht-modales Fenster fuer Repository-Diagnose und Job-Historie."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QGroupBox, QVBoxLayout

from ui.widgets.log_panel_widget import LogPanelWidget


class DiagnosticsWindow(QDialog):
    """Zeigt Diagnose- und Historienbereiche in einem separaten, nicht-modalen Fenster."""

    def __init__(self, parent=None) -> None:
        """
        Baut das Diagnosefenster mit zwei klar getrennten Textbereichen auf.

        Eingabeparameter:
        - parent: Optionales Parent-Widget fuer Fensterbezug und Fokusverhalten.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine direkten Fehler; das Fenster baut nur UI-Struktur auf.

        Wichtige interne Logik:
        - Das Fenster ist explizit nicht modal, damit das MainWindow waehrend geoeffneter
          Diagnose weiter bedienbar bleibt.
        """

        super().__init__(parent)
        self.setWindowTitle("iGitty Diagnose")
        self.setModal(False)
        self.resize(900, 700)

        self._diagnostics_panel = LogPanelWidget()
        self._history_panel = LogPanelWidget()
        self._diagnostics_panel.setMaximumBlockCount(500)
        self._history_panel.setMaximumBlockCount(500)
        self._diagnostics_panel.set_messages([], "Kein lokales Repository ausgewaehlt.")
        self._history_panel.set_messages([], "Keine Job-Historie fuer dieses Repository vorhanden.")

        root_layout = QVBoxLayout(self)

        diagnostics_box = QGroupBox("Repository-Diagnose")
        diagnostics_layout = QVBoxLayout(diagnostics_box)
        diagnostics_layout.addWidget(self._diagnostics_panel)

        history_box = QGroupBox("Job-Historie")
        history_layout = QVBoxLayout(history_box)
        history_layout.addWidget(self._history_panel)

        root_layout.addWidget(diagnostics_box, stretch=1)
        root_layout.addWidget(history_box, stretch=1)

    def set_local_repo_diagnostics(self, lines: list[str]) -> None:
        """
        Aktualisiert die Diagnosezeilen fuer das aktuell selektierte Repository.

        Eingabeparameter:
        - lines: Bereits aufbereitete Diagnosezeilen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die eigentliche Diagnoseaufbereitung bleibt ausserhalb des Fensters.
        """

        self._diagnostics_panel.set_messages(lines, "Kein lokales Repository ausgewaehlt.")

    def set_local_repo_history(self, lines: list[str]) -> None:
        """
        Aktualisiert die Job-Historie fuer das aktuell selektierte Repository.

        Eingabeparameter:
        - lines: Bereits aufbereitete Historienzeilen.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Fenster zeigt nur Daten an und enthaelt keine eigene Datenlogik.
        """

        self._history_panel.set_messages(lines, "Keine Job-Historie fuer dieses Repository vorhanden.")
