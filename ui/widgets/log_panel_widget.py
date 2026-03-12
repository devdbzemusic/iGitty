"""Einfaches Logpanel fuer sichtbare Laufzeitmeldungen."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QPlainTextEdit


class LogPanelWidget(QPlainTextEdit):
    """Zeigt menschenlesbare Laufzeitmeldungen in der UI an."""

    def __init__(self) -> None:
        """
        Initialisiert das schreibgeschuetzte Logpanel.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Widget ist read-only, damit die UI-Logs manipulationsarm bleiben.
        """

        super().__init__()
        self.setReadOnly(True)
        self.setMaximumBlockCount(500)

    def append_message(self, message: str) -> None:
        """
        Fuegt eine neue Zeitstempel-Zeile an das sichtbare Log an.

        Eingabeparameter:
        - message: Darzustellende Lognachricht.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Ergaenzt lokal einen UI-Zeitstempel, damit die Anzeige ohne Dateilog lesbar bleibt.
        """

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.appendPlainText(f"[{timestamp}] {message}")
