"""Statusleiste fuer globale Laufzeitinformationen."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar

from models.view_models import StatusSnapshot


class StatusBarWidget(QStatusBar):
    """Stellt zentrale Statuswerte dauerhaft am Fensterrand dar."""

    def __init__(self) -> None:
        """
        Baut die festen Statusfelder der Anwendung auf.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Jeder Wert bekommt ein eigenes Label, damit spaetere Updates gezielt moeglich bleiben.
        """

        super().__init__()
        self._github_label = QLabel("GitHub: Nicht verbunden")
        self._remote_label = QLabel("Remote: 0")
        self._local_label = QLabel("Lokal: 0")
        self._rate_limit_label = QLabel("Rate Limit: 0/0 (-)")
        self._target_dir_label = QLabel("Zielordner: -")

        self.addPermanentWidget(self._github_label)
        self.addPermanentWidget(self._remote_label)
        self.addPermanentWidget(self._local_label)
        self.addPermanentWidget(self._rate_limit_label, stretch=1)
        self.addPermanentWidget(self._target_dir_label, stretch=2)

    def update_snapshot(self, snapshot: StatusSnapshot) -> None:
        """
        Uebernimmt einen kompletten Status-Snapshot in die sichtbaren Felder.

        Eingabeparameter:
        - snapshot: Bereits formatierte Statuswerte.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Widgetschicht bleibt rein darstellend und wertet nichts fachlich aus.
        """

        self._github_label.setText(f"GitHub: {snapshot.github_text}")
        self._remote_label.setText(f"Remote: {snapshot.remote_count}")
        self._local_label.setText(f"Lokal: {snapshot.local_count}")
        self._rate_limit_label.setText(f"Rate Limit: {snapshot.rate_limit_text}")
        self._target_dir_label.setText(f"Zielordner: {snapshot.target_dir_text}")
