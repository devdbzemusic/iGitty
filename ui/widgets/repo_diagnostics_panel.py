"""Diagnose-Panel fuer Statusevents und Scan-Historie im RepoViewer."""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from models.state_models import RepoStatusEvent, ScanRunRecord


class RepoDiagnosticsPanel(QWidget):
    """Zeigt Event-Timeline und juengste Scan-Laeufe fuer ein Repository an."""

    def __init__(self, parent=None) -> None:
        """
        Baut das Diagnose-Panel mit Event- und Scan-Tabelle auf.

        Eingabeparameter:
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Widget-Erstellung.

        Wichtige interne Logik:
        - Das Panel trennt Statusevents und Scan-Laeufe sichtbar, weil beide fuer die
          Fehlersuche unterschiedliche Fragen beantworten.
        """

        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._event_table = QTableWidget(0, 4)
        self._event_table.setHorizontalHeaderLabels(["Zeit", "Severity", "Event", "Nachricht"])
        self._event_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._event_table, stretch=2)

        self._scan_table = QTableWidget(0, 5)
        self._scan_table.setHorizontalHeaderLabels(["Start", "Typ", "Dauer ms", "Changed", "Errors"])
        self._scan_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._scan_table, stretch=1)

    def set_status_events(self, events: list[RepoStatusEvent]) -> None:
        """
        Uebernimmt Statusereignisse in die Event-Timeline.

        Eingabeparameter:
        - events: Juengste append-only RepoStatusEvents.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; eine leere Eventliste fuehrt zu einer Platzhalterzeile.

        Wichtige interne Logik:
        - Die Timeline zeigt die neuesten Ereignisse zuerst, genau wie der State-Layer sie liefert.
        """

        rows = events or [
            RepoStatusEvent(repo_id=0, event_type="-", severity="info", message="Keine Diagnoseevents vorhanden.", created_at="-")
        ]
        self._event_table.setRowCount(len(rows))
        for row_index, event in enumerate(rows):
            self._event_table.setItem(row_index, 0, QTableWidgetItem(event.created_at or "-"))
            self._event_table.setItem(row_index, 1, QTableWidgetItem(event.severity or "info"))
            self._event_table.setItem(row_index, 2, QTableWidgetItem(event.event_type or "-"))
            self._event_table.setItem(row_index, 3, QTableWidgetItem(event.message or "-"))

    def set_scan_runs(self, runs: list[ScanRunRecord]) -> None:
        """
        Uebernimmt juengste Scan-Laeufe in die untere Diagnoseansicht.

        Eingabeparameter:
        - runs: Juengste ScanRunRecord-Eintraege aus dem State-Layer.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; eine leere Liste fuehrt zu einer Platzhalterzeile.

        Wichtige interne Logik:
        - Die Tabelle bleibt generisch genug, damit sowohl lokale als auch Remote-Laeufe
          in derselben Diagnoseansicht lesbar bleiben.
        """

        rows = runs or [
            ScanRunRecord(
                id=0,
                scan_type="-",
                started_at="-",
                finished_at="-",
                duration_ms=0,
                changed_count=0,
                unchanged_count=0,
                error_count=0,
            )
        ]
        self._scan_table.setRowCount(len(rows))
        for row_index, run in enumerate(rows):
            self._scan_table.setItem(row_index, 0, QTableWidgetItem(run.started_at or "-"))
            self._scan_table.setItem(row_index, 1, QTableWidgetItem(run.scan_type or "-"))
            self._scan_table.setItem(row_index, 2, QTableWidgetItem(str(run.duration_ms)))
            self._scan_table.setItem(row_index, 3, QTableWidgetItem(str(run.changed_count)))
            self._scan_table.setItem(row_index, 4, QTableWidgetItem(str(run.error_count)))
