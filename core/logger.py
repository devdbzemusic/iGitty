"""Zentraler Logger fuer Datei- und UI-Ausgaben."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable


class AppLogger:
    """Verteilt Lognachrichten gleichzeitig an Datei- und UI-Empfaenger."""

    def __init__(self, log_file: Path) -> None:
        """
        Initialisiert den Anwendungslogger.

        Eingabeparameter:
        - log_file: Zielpfad fuer das persistente Dateilog.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehlende Schreibrechte auf die Logdatei.

        Wichtige interne Logik:
        - Verwendet einen dedizierten Logger-Namen, damit iGitty-Logs kontrolliert bleiben.
        """

        self._listeners: list[Callable[[str], None]] = []
        self._logger = logging.getLogger("igitty")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            handler = logging.FileHandler(log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            self._logger.addHandler(handler)

    def subscribe(self, listener: Callable[[str], None]) -> None:
        """
        Registriert einen UI-Listener fuer neue Logzeilen.

        Eingabeparameter:
        - listener: Rueckruffunktion, die eine formatierte Logzeile entgegennimmt.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; doppelte Listener werden bewusst nicht verhindert.

        Wichtige interne Logik:
        - Die Kopplung bleibt locker, damit der Logger auch ohne UI nutzbar bleibt.
        """

        self._listeners.append(listener)

    def info(self, message: str) -> None:
        """
        Schreibt eine Info-Nachricht in Datei und UI.

        Eingabeparameter:
        - message: Bereits aufbereitete Lognachricht.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Listener koennen intern scheitern; der Dateilog bleibt trotzdem erhalten.

        Wichtige interne Logik:
        - Die Nachricht wird zuerst persistent geschrieben und danach an UI-Listener verteilt.
        """

        self._logger.info(message)
        for listener in list(self._listeners):
            listener(message)
