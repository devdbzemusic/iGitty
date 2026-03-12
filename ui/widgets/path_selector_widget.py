"""Schmales Anzeige-Widget fuer den aktuellen Zielordner."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class PathSelectorWidget(QWidget):
    """Zeigt den aktuellen Zielpfad der Anwendung an."""

    browse_requested = Signal()

    def __init__(self) -> None:
        """
        Baut ein minimales Pfad-Anzeigewidget auf.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die eigentliche Ordnerauswahl folgt spaeter; fuer den MVP reicht eine klare Anzeige.
        """

        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._browse_button = QPushButton("Ordner waehlen")
        layout.addWidget(self._path_edit)
        layout.addWidget(self._browse_button)
        self._browse_button.clicked.connect(self.browse_requested.emit)

    def set_path(self, path_text: str) -> None:
        """
        Aktualisiert den dargestellten Zielpfad.

        Eingabeparameter:
        - path_text: Vollstaendiger anzuzeigender Pfad.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Widget speichert keine Fachlogik, sondern nur den sichtbaren Text.
        """

        self._path_edit.setText(path_text)

    def current_path(self) -> str:
        """
        Liefert den aktuell angezeigten Pfadtext fuer vorbelegte Dialoge zurueck.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Aktuell sichtbarer Pfad als String.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Stellt dem Hauptfenster lesenden Zugriff bereit, ohne das interne Widget preiszugeben.
        """

        return self._path_edit.text()
