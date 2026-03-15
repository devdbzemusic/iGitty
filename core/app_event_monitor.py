"""Ueberwacht App-Events, Qt-Meldungen und ungefangene Absturzpfade."""

from __future__ import annotations

import faulthandler
import logging
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Callable, TextIO

from PySide6.QtCore import QEvent, QMessageLogContext, QObject, QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from core.logger import AppLogger


@dataclass(slots=True)
class AppEventMonitorResources:
    """Haelt installierte Hooks und offene Ressourcen fuer die Laufzeitueberwachung."""

    fault_log_stream: TextIO
    previous_sys_excepthook: Callable[[type[BaseException], BaseException, TracebackType | None], object]
    previous_threading_excepthook: Callable[[threading.ExceptHookArgs], object] | None
    previous_qt_message_handler: Callable[[QtMsgType, QMessageLogContext, str], None] | None

    def close(self) -> None:
        """
        Stellt globale Hooks wieder her und schliesst den Faulthandler-Stream.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Bereits deaktivierte Hooks oder Streams werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Wiederherstellung ist vor allem fuer Tests und wiederholte App-Starts
          im selben Python-Prozess wichtig.
        """

        try:
            faulthandler.disable()
        except Exception:
            pass
        sys.excepthook = self.previous_sys_excepthook
        if self.previous_threading_excepthook is not None:
            threading.excepthook = self.previous_threading_excepthook
        qInstallMessageHandler(self.previous_qt_message_handler)
        try:
            self.fault_log_stream.flush()
            self.fault_log_stream.close()
        except Exception:
            pass


class LoggedApplication(QApplication):
    """QApplication-Variante mit Absicherung gegen ungefangene Event-Exceptions."""

    def __init__(self, argv: list[str], logger: AppLogger) -> None:
        """
        Initialisiert die Qt-Anwendung und merkt sich den zentralen Logger.

        Eingabeparameter:
        - argv: Prozessargumente fuer Qt.
        - logger: Zentraler App-Logger.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Das Logger-Objekt steht in `notify()` zur Verfuegung, damit auch Fehler
          waehrend der Event-Auslieferung nicht still verloren gehen.
        """

        super().__init__(argv)
        self._logger = logger

    def notify(self, receiver: QObject, event: QEvent) -> bool:
        """
        Liefert Qt-Events aus und protokolliert ungefangene Python-Ausnahmen.

        Eingabeparameter:
        - receiver: Empfaengerobjekt des Qt-Events.
        - event: Das konkrete Qt-Ereignis.

        Rueckgabewerte:
        - Rueckgabewert der normalen Qt-Ereignisverarbeitung oder `False` bei Ausnahme.

        Moegliche Fehlerfaelle:
        - Unerwartete Exceptions aus Widgets, Slots oder Event-Handlern.

        Wichtige interne Logik:
        - Die Methode loggt den Fehler mit Receiver- und Event-Kontext, damit App-Abbrueche
          im GUI-Bereich spaeter reproduzierbar werden.
        """

        try:
            return super().notify(receiver, event)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as error:  # noqa: BLE001
            event_name = self._event_name(event)
            receiver_name = self._describe_receiver(receiver)
            self._logger.log_exception_details(
                (
                    "Unbehandelte Ausnahme waehrend der Qt-Event-Verarbeitung "
                    f"(receiver={receiver_name}, event={event_name})"
                ),
                type(error),
                error,
                error.__traceback__,
            )
            return False

    def _describe_receiver(self, receiver: QObject) -> str:
        """
        Erzeugt eine kompakte Bezeichnung fuer den Event-Empfaenger.

        Eingabeparameter:
        - receiver: Qt-Objekt, das das Event empfaengt.

        Rueckgabewerte:
        - Lesbarer Name fuer das Log.

        Moegliche Fehlerfaelle:
        - Fehlende Metadaten werden ueber Fallbacks abgefangen.

        Wichtige interne Logik:
        - Objektname und Klassenname werden kombiniert, um UI-Fehler gezielt zuordnen zu koennen.
        """

        parts = [receiver.__class__.__name__]
        object_name = receiver.objectName().strip() if receiver.objectName() else ""
        if object_name:
            parts.append(f"object={object_name}")
        return " | ".join(parts)

    def _event_name(self, event: QEvent) -> str:
        """
        Liefert eine kompakte Bezeichnung des Qt-Ereignistyps.

        Eingabeparameter:
        - event: Zu benennendes Qt-Ereignis.

        Rueckgabewerte:
        - Name oder numerischer Fallback des Ereignistyps.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Qt-Enums koennen je nach Binding leicht variieren; deshalb existiert ein sicherer Fallback.
        """

        event_type = event.type()
        return getattr(event_type, "name", str(int(event_type)))


def install_app_event_monitoring(logger: AppLogger, log_file: Path) -> AppEventMonitorResources:
    """
    Installiert globale Hooks fuer ungefangene Exceptions, Qt-Meldungen und Crash-Dumps.

    Eingabeparameter:
    - logger: Zentraler App-Logger.
    - log_file: Gemeinsame Logdatei fuer Laufzeit- und Crash-Informationen.

    Rueckgabewerte:
    - Ressourcenobjekt zum spaeteren Wiederherstellen und Schliessen.

    Moegliche Fehlerfaelle:
    - Faulthandler kann bei fehlenden Dateirechten nicht aktiviert werden.

    Wichtige interne Logik:
    - `faulthandler` deckt auch haertere Absturzpfade ab, bei denen reguläre Python-Logger
      nicht mehr zum Zug kommen.
    """

    fault_log_stream = log_file.open("a", encoding="utf-8")
    fault_log_stream.write("\n")
    fault_log_stream.flush()
    faulthandler.enable(file=fault_log_stream, all_threads=True)

    previous_sys_excepthook = sys.excepthook
    previous_threading_excepthook = getattr(threading, "excepthook", None)

    def _sys_excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        """
        Protokolliert ungefangene Hauptthread-Ausnahmen in `log.txt`.
        """

        logger.log_exception_details(
            "Unbehandelte Ausnahme im Hauptthread entdeckt",
            exc_type,
            exc_value,
            exc_traceback,
        )
        if callable(previous_sys_excepthook):
            previous_sys_excepthook(exc_type, exc_value, exc_traceback)

    def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
        """
        Protokolliert ungefangene Thread-Ausnahmen mitsamt Thread-Namen.
        """

        logger.log_exception_details(
            f"Unbehandelte Ausnahme im Thread entdeckt (thread={args.thread.name if args.thread else 'unbekannt'})",
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
        )
        if callable(previous_threading_excepthook):
            previous_threading_excepthook(args)

    previous_qt_message_handler = qInstallMessageHandler(_build_qt_message_handler(logger))
    sys.excepthook = _sys_excepthook
    if previous_threading_excepthook is not None:
        threading.excepthook = _threading_excepthook

    logger.event("app", "global_exception_hooks_installed", f"log_file={log_file}", level=logging.INFO)
    return AppEventMonitorResources(
        fault_log_stream=fault_log_stream,
        previous_sys_excepthook=previous_sys_excepthook,
        previous_threading_excepthook=previous_threading_excepthook,
        previous_qt_message_handler=previous_qt_message_handler,
    )


def _build_qt_message_handler(
    logger: AppLogger,
) -> Callable[[QtMsgType, QMessageLogContext, str], None]:
    """
    Baut einen Qt-Message-Handler, der Framework-Meldungen nach `log.txt` umlenkt.

    Eingabeparameter:
    - logger: Zentraler App-Logger.

    Rueckgabewerte:
    - Passende Callback-Funktion fuer `qInstallMessageHandler`.

    Moegliche Fehlerfaelle:
    - Keine; unbekannte Qt-Meldetypen werden defensiv als Fehler behandelt.

    Wichtige interne Logik:
    - Qt-Warnungen und -Fehler landen damit nicht nur in stderr, sondern nachvollziehbar
      im selben Laufzeitlog wie die restlichen App-Ereignisse.
    """

    def _qt_message_handler(message_type: QtMsgType, context: QMessageLogContext, message: str) -> None:
        """
        Protokolliert eine einzelne Qt-Framework-Meldung.
        """

        level_map = {
            QtMsgType.QtDebugMsg: logging.DEBUG,
            QtMsgType.QtInfoMsg: logging.INFO,
            QtMsgType.QtWarningMsg: logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.ERROR,
            QtMsgType.QtFatalMsg: logging.CRITICAL,
        }
        level = level_map.get(message_type, logging.ERROR)
        source_details = []
        if context.file:
            source_details.append(f"file={context.file}")
        if context.line:
            source_details.append(f"line={context.line}")
        if context.function:
            source_details.append(f"function={context.function}")
        details = " | ".join([message.strip(), *source_details]).strip(" |")
        logger.event("qt", "framework_message", details, level=level)

    return _qt_message_handler
