"""Zentraler Logger fuer Datei- und UI-Ausgaben."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path
from types import TracebackType
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
        - Verwendet einen dedizierten Logger pro Dateipfad, damit Testlaeufe und
          parallele Instanzen keine Handler gegenseitig ueberschreiben.
        - Schreibt bewusst auf DEBUG-Niveau in die Datei, damit auch sehr feingranulare
          UI- und Scan-Ereignisse in `log.txt` landen koennen.
        """

        self._listeners: list[tuple[Callable[[str], None], int]] = []
        logger_name = f"igitty.{log_file.resolve().as_posix()}"
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
            handler.close()

        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        self._logger.addHandler(handler)

    def subscribe(self, listener: Callable[[str], None], min_level: int = logging.INFO) -> None:
        """
        Registriert einen UI-Listener fuer neue Logzeilen.

        Eingabeparameter:
        - listener: Rueckruffunktion, die eine formatierte Logzeile entgegennimmt.
        - min_level: Minimales Logging-Level, ab dem der Listener benachrichtigt wird.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; doppelte Listener werden bewusst nicht verhindert.

        Wichtige interne Logik:
        - UI-Listener koennen auf ein hoeheres Minimum gesetzt werden als das Dateilog,
          damit `log.txt` deutlich detailreicher sein kann als das sichtbare Laufzeitpanel.
        """

        self._listeners.append((listener, min_level))

    def debug(self, message: str) -> None:
        """
        Schreibt eine Debug-Nachricht in die Logdatei und optional an Listener.

        Eingabeparameter:
        - message: Bereits aufbereitete Lognachricht.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Listener koennen intern scheitern; der Dateilog bleibt trotzdem erhalten.

        Wichtige interne Logik:
        - Debug wird fuer detaillierte App- und Scan-Ereignisse verwendet.
        """

        self._log(logging.DEBUG, message)

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
        - Info ist das Standardniveau fuer benutzerrelevante Aktionen.
        """

        self._log(logging.INFO, message)

    def warning(self, message: str) -> None:
        """
        Schreibt eine Warnung in Datei und UI.

        Eingabeparameter:
        - message: Aufbereitete Warnmeldung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Listenerfehler werden isoliert behandelt.

        Wichtige interne Logik:
        - Warnungen heben unvollstaendige oder verdaechtige, aber nicht fatale Situationen hervor.
        """

        self._log(logging.WARNING, message)

    def error(self, message: str) -> None:
        """
        Schreibt eine Fehlermeldung in Datei und UI.

        Eingabeparameter:
        - message: Aufbereitete Fehlermeldung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Listenerfehler werden abgefangen.

        Wichtige interne Logik:
        - Fehler werden ohne Ausnahmeobjekt protokolliert, wenn bereits ein sauberer Text vorliegt.
        """

        self._log(logging.ERROR, message)

    def exception(self, message: str) -> None:
        """
        Schreibt eine Fehlermeldung inklusive aktuellem Stacktrace in die Logdatei.

        Eingabeparameter:
        - message: Fachlicher Kontext zur gerade behandelten Ausnahme.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Listener koennen scheitern; die eigentliche Ausnahme wird trotzdem ins Dateilog geschrieben.

        Wichtige interne Logik:
        - Der Stacktrace bleibt im Dateilog erhalten, waehrend UI-Listener nur den
          kompakten Meldungstext erhalten.
        """

        self._logger.exception(message)
        self._notify_listeners(logging.ERROR, message)

    def log_exception_details(
        self,
        message: str,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        """
        Schreibt eine explizit uebergebene Ausnahme inklusive Traceback in die Logdatei.

        Eingabeparameter:
        - message: Fachlicher Kontext fuer die Ausnahme.
        - exc_type: Konkreter Ausnahmetyp.
        - exc_value: Ausgeloeste Ausnahmeinstanz.
        - exc_traceback: Zugehoeriger Traceback oder `None`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Listener koennen scheitern; der Dateieintrag bleibt trotzdem erhalten.

        Wichtige interne Logik:
        - Diese Methode wird fuer globale Hooks wie `sys.excepthook` benoetigt, weil dort
          keine aktive Exception mehr im klassischen `except`-Kontext vorhanden ist.
        """

        self._logger.error(message, exc_info=(exc_type, exc_value, exc_traceback))
        self._notify_listeners(logging.ERROR, f"{message}: {exc_value}")

    def critical(self, message: str) -> None:
        """
        Schreibt eine kritische Meldung in Datei und UI.

        Eingabeparameter:
        - message: Aufbereitete kritische Meldung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Listenerfehler werden abgefangen.

        Wichtige interne Logik:
        - Kritische Eintraege markieren Situationen, die typischerweise mit einem
          App-Absturz oder unmittelbar bevorstehendem Abbruch zusammenhaengen.
        """

        self._log(logging.CRITICAL, message)

    def event(self, category: str, action: str, details: str = "", level: int = logging.DEBUG) -> None:
        """
        Schreibt ein strukturiertes Ereignis mit Kategorie und Aktion in das Log.

        Eingabeparameter:
        - category: Oberbegriff des Ereignisses, zum Beispiel `ui`, `scan` oder `app`.
        - action: Konkrete Aktion oder Statusbeschreibung.
        - details: Optionale Detaildaten zum Ereignis.
        - level: Logging-Level fuer dieses Ereignis.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine ueber die allgemeinen Logging-Risiken hinaus.

        Wichtige interne Logik:
        - Das kompakte Format erleichtert spaetere Textsuche in `log.txt`.
        """

        suffix = f" | {details}" if details else ""
        self._log(level, f"[{category}] {action}{suffix}")

    def _log(self, level: int, message: str) -> None:
        """
        Fuehrt die gemeinsame Ausgabelogik fuer alle Logging-Methoden aus.

        Eingabeparameter:
        - level: Numerisches Logging-Level aus dem `logging`-Modul.
        - message: Bereits formatierte Nachricht.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Listener koennen intern fehlschlagen.

        Wichtige interne Logik:
        - Datei- und Listener-Ausgabe bleiben konsistent an einer zentralen Stelle.
        """

        self._logger.log(level, message)
        self._notify_listeners(level, message)

    def _notify_listeners(self, level: int, message: str) -> None:
        """
        Benachrichtigt alle registrierten Listener gemaess ihres Mindestlevels.

        Eingabeparameter:
        - level: Level der aktuellen Nachricht.
        - message: Bereits formatierter Meldungstext.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Defekte Listener werden ignoriert, damit das Logging insgesamt stabil bleibt.

        Wichtige interne Logik:
        - Die UI erhaelt ein kompaktes `LEVEL | Nachricht`-Format, damit sichtbare
          Eintraege auch ohne Dateitimestamp eindeutig bleiben.
        """

        rendered_message = f"{logging.getLevelName(level)} | {message}"
        for listener, min_level in list(self._listeners):
            if level < min_level:
                continue
            try:
                listener(rendered_message)
            except Exception:
                continue
