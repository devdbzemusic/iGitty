"""Nicht-modales Fenster fuer Repository-Diagnose und Job-Historie."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QCheckBox, QDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

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
        self._live_log_panel = LogPanelWidget()
        self._auto_refresh_checkbox = QCheckBox("Auto Refresh")
        self._refresh_button = QPushButton("Log aktualisieren")
        self._refresh_status_label = QLabel("Live-Log noch nicht geladen.")
        self._live_log_timer = QTimer(self)
        self._live_log_file: Path | None = None
        self._last_loaded_signature: tuple[int, int] | None = None
        self._diagnostics_panel.setMaximumBlockCount(500)
        self._history_panel.setMaximumBlockCount(500)
        self._live_log_panel.setMaximumBlockCount(10000)
        self._diagnostics_panel.set_messages([], "Kein lokales Repository ausgewaehlt.")
        self._history_panel.set_messages([], "Keine Job-Historie fuer dieses Repository vorhanden.")
        self._live_log_panel.setPlainText("Noch keine Logdatei verbunden.")
        self._auto_refresh_checkbox.setChecked(True)
        self._live_log_timer.setInterval(1500)

        root_layout = QVBoxLayout(self)

        diagnostics_box = QGroupBox("Repository-Diagnose")
        diagnostics_layout = QVBoxLayout(diagnostics_box)
        diagnostics_layout.addWidget(self._diagnostics_panel)

        history_box = QGroupBox("Job-Historie")
        history_layout = QVBoxLayout(history_box)
        history_layout.addWidget(self._history_panel)

        live_log_box = QGroupBox("Live Log.txt")
        live_log_layout = QVBoxLayout(live_log_box)
        live_log_toolbar = QHBoxLayout()
        live_log_toolbar.addWidget(self._auto_refresh_checkbox)
        live_log_toolbar.addWidget(self._refresh_button)
        live_log_toolbar.addStretch(1)
        live_log_toolbar.addWidget(self._refresh_status_label)
        live_log_layout.addLayout(live_log_toolbar)
        live_log_layout.addWidget(self._live_log_panel)

        root_layout.addWidget(diagnostics_box, stretch=1)
        root_layout.addWidget(history_box, stretch=1)
        root_layout.addWidget(live_log_box, stretch=2)

        self._refresh_button.clicked.connect(lambda: self.refresh_live_log(force=True))
        self._auto_refresh_checkbox.toggled.connect(self._sync_live_log_timer)
        self._live_log_timer.timeout.connect(self.refresh_live_log)

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

    def set_live_log_file(self, log_file: Path) -> None:
        """
        Hinterlegt die zu spiegelnde Logdatei fuer das Live-Log im Diagnosefenster.

        Eingabeparameter:
        - log_file: Vollstaendiger Dateipfad zur `log.txt`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Nicht vorhandene Dateien werden ueber Platzhaltertext statt Exceptions behandelt.

        Wichtige interne Logik:
        - Der Pfad wird separat gesetzt, weil das Diagnosefenster schon vor der kompletten
          Laufzeitinitialisierung des Controllers erzeugt wird.
        """

        self._live_log_file = log_file
        self._last_loaded_signature = None
        self.refresh_live_log(force=True)
        self._sync_live_log_timer()

    def live_log_file(self) -> Path | None:
        """
        Liefert die aktuell verbundene Live-Logdatei fuer Hilfsaktionen im Hauptfenster.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Hinterlegter Logpfad oder `None`.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Hauptfenster kann damit Datei- und Ordneraktionen anbieten, ohne eigene
          Dateipfade parallel zum Diagnosefenster zu speichern.
        """

        return self._live_log_file

    def refresh_live_log(self, force: bool = False) -> None:
        """
        Laedt den aktuellen Inhalt der Logdatei in das sichtbare Live-Log-Feld.

        Eingabeparameter:
        - force: Erzwingt das Neuladen auch ohne erkannte Dateiaenderung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehlende oder gerade gesperrte Dateien werden als lesbare Statusmeldung angezeigt.

        Wichtige interne Logik:
        - Es wird nur bei geaenderter Dateisignatur neu gelesen, damit das Auto-Refresh die UI
          nicht unnötig belastet.
        """

        if self._live_log_file is None:
            self._live_log_panel.setPlainText("Noch keine Logdatei verbunden.")
            self._refresh_status_label.setText("Kein Logpfad gesetzt.")
            return
        if not self._live_log_file.exists():
            self._live_log_panel.setPlainText("Die konfigurierte log.txt wurde noch nicht gefunden.")
            self._refresh_status_label.setText("Logdatei fehlt.")
            return

        try:
            stat_result = self._live_log_file.stat()
            signature = (int(stat_result.st_mtime_ns), int(stat_result.st_size))
            if not force and signature == self._last_loaded_signature:
                return

            scrollbar = self._live_log_panel.verticalScrollBar()
            was_near_bottom = scrollbar.value() >= max(scrollbar.maximum() - 8, 0)
            previous_value = scrollbar.value()

            log_text = self._live_log_file.read_text(encoding="utf-8", errors="replace")
            self._live_log_panel.setPlainText(log_text if log_text else "Die log.txt ist aktuell leer.")
            self._last_loaded_signature = signature
            self._refresh_status_label.setText(
                f"Stand: {datetime.now().strftime('%H:%M:%S')} | {self._live_log_file.name}"
            )

            if was_near_bottom:
                self._live_log_panel.moveCursor(QTextCursor.MoveOperation.End)
            else:
                scrollbar.setValue(min(previous_value, scrollbar.maximum()))
        except Exception as error:  # noqa: BLE001
            self._refresh_status_label.setText(f"Fehler beim Laden: {type(error).__name__}")
            self._live_log_panel.setPlainText(f"Live-Log konnte nicht gelesen werden:\n{error}")

    def showEvent(self, event) -> None:
        """
        Startet beim Anzeigen des Fensters den Live-Refresh und laedt den aktuellen Logstand.

        Eingabeparameter:
        - event: Qt-Show-Event des Fensters.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Live-Log soll beim Oeffnen sofort den aktuellen Dateistand zeigen.
        """

        super().showEvent(event)
        self.refresh_live_log(force=True)
        self._sync_live_log_timer()

    def hideEvent(self, event) -> None:
        """
        Stoppt das Polling, sobald das Diagnosefenster nicht mehr sichtbar ist.

        Eingabeparameter:
        - event: Qt-Hide-Event des Fensters.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Fenster pollt die Logdatei nur dann, wenn der Benutzer es wirklich offen hat.
        """

        super().hideEvent(event)
        self._sync_live_log_timer()

    def _sync_live_log_timer(self) -> None:
        """
        Synchronisiert den Timerzustand mit Sichtbarkeit und Auto-Refresh-Option.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Polling bleibt aktiv nur bei sichtbarem Fenster und gesetzter Auto-Refresh-Option.
        """

        should_run = self.isVisible() and self._auto_refresh_checkbox.isChecked() and self._live_log_file is not None
        if should_run and not self._live_log_timer.isActive():
            self._live_log_timer.start()
        elif not should_run and self._live_log_timer.isActive():
            self._live_log_timer.stop()
