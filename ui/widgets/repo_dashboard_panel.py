"""Dashboard-Panel fuer den RepoViewer in MVP Phase II."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QListWidget, QVBoxLayout, QWidget

from models.view_models import RepoContext


class RepoDashboardPanel(QWidget):
    """Zeigt die wichtigsten Health-, Sync- und Aktionsdaten eines Repositories an."""

    def __init__(self, parent=None) -> None:
        """
        Baut das Dashboard-Panel mit kompakter Kennzahlen- und Aktionsansicht auf.

        Eingabeparameter:
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der Widget-Erstellung.

        Wichtige interne Logik:
        - Das Panel bleibt rein lesend und dient als schnelle Startansicht fuer den RepoViewer.
        """

        super().__init__(parent)
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self._status_label = QLabel("-")
        self._health_label = QLabel("-")
        self._sync_label = QLabel("-")
        self._recommended_action_label = QLabel("-")
        self._last_scan_label = QLabel("-")
        self._last_remote_check_label = QLabel("-")
        self._needs_rescan_label = QLabel("-")
        self._dirty_hint_label = QLabel("-")
        self._fingerprint_label = QLabel("-")
        self._status_hash_label = QLabel("-")
        self._fingerprint_label.setWordWrap(True)
        self._status_hash_label.setWordWrap(True)

        form_layout.addRow("Repository Status", self._status_label)
        form_layout.addRow("Health State", self._health_label)
        form_layout.addRow("Sync State", self._sync_label)
        form_layout.addRow("Recommended Action", self._recommended_action_label)
        form_layout.addRow("Last Scan", self._last_scan_label)
        form_layout.addRow("Last Remote Check", self._last_remote_check_label)
        form_layout.addRow("Needs Rescan", self._needs_rescan_label)
        form_layout.addRow("Dirty Hint", self._dirty_hint_label)
        form_layout.addRow("Scan Fingerprint", self._fingerprint_label)
        form_layout.addRow("Status Hash", self._status_hash_label)
        layout.addLayout(form_layout)

        self._actions_list = QListWidget()
        layout.addWidget(QLabel("Available Actions"))
        layout.addWidget(self._actions_list, stretch=1)

    def set_context(self, context: RepoContext) -> None:
        """
        Uebernimmt den zusammengefuehrten Repo-Kontext in die Dashboard-Anzeige.

        Eingabeparameter:
        - context: Vollstaendig vorbereiteter RepoContext.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Werte werden defensiv als `-` angezeigt.

        Wichtige interne Logik:
        - Das Panel zeigt nur lesbare Kerndaten und fuehrt selbst keine Businesslogik aus.
        """

        self._status_label.setText(context.repository_status or "-")
        self._health_label.setText(context.health_state or "-")
        self._sync_label.setText(context.sync_state or "-")
        self._recommended_action_label.setText(context.recommended_action or "-")
        self._last_scan_label.setText(context.last_scan_at or "-")
        self._last_remote_check_label.setText(context.last_remote_check_at or "-")
        self._needs_rescan_label.setText("Ja" if context.needs_rescan else "Nein")
        self._dirty_hint_label.setText("Ja" if context.dirty_hint else "Nein")
        self._fingerprint_label.setText(context.scan_fingerprint or "-")
        self._status_hash_label.setText(context.status_hash or "-")
        self._actions_list.clear()
        if context.available_actions:
            self._actions_list.addItems(context.available_actions)
        else:
            self._actions_list.addItem("Keine abgeleiteten Aktionen vorhanden.")
