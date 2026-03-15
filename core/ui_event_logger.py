"""Globales Qt-Ereignislogging fuer die Desktop-Anwendung."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QWidget,
)

from core.logger import AppLogger


class UiEventLogger(QObject):
    """Protokolliert wichtige Qt-UI-Ereignisse zentral ueber einen Event-Filter."""

    def __init__(self, application: QApplication, logger: AppLogger) -> None:
        """
        Installiert den Event-Filter auf der gesamten Qt-Anwendung.

        Eingabeparameter:
        - application: Laufende QApplication-Instanz.
        - logger: Zentraler App-Logger fuer `log.txt`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine direkten Fehler; unbekannte Ereignisse werden einfach ignoriert.

        Wichtige interne Logik:
        - Es werden nur semantisch sinnvolle UI-Ereignisse mit geringer Frequenz geloggt,
          damit die Datei detailreich bleibt, ohne von Paint- oder MouseMove-Fluten unlesbar zu werden.
        """

        super().__init__(application)
        self._application = application
        self._logger = logger
        self._application.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        Protokolliert ausgewaehlte Anwendungsereignisse und laesst sie danach normal weiterlaufen.

        Eingabeparameter:
        - watched: Qt-Objekt, auf dem das Ereignis auftritt.
        - event: Das konkrete Qt-Ereignis.

        Rueckgabewerte:
        - `False`, damit Qt die Ereignisse normal weiterverarbeitet.

        Moegliche Fehlerfaelle:
        - Unerwartete Widget-Typen werden ignoriert.

        Wichtige interne Logik:
        - Das Logging arbeitet rein beobachtend und veraendert das UI-Verhalten nicht.
        """

        if isinstance(watched, QWidget):
            if event.type() == QEvent.Type.Show:
                self._logger.event("ui", "widget_shown", self._describe_widget(watched))
            elif event.type() == QEvent.Type.Close:
                self._logger.event("ui", "widget_closed", self._describe_widget(watched))
            elif event.type() == QEvent.Type.FocusIn:
                self._logger.event("ui", "focus_in", self._describe_widget(watched))
            elif event.type() == QEvent.Type.MouseButtonPress:
                self._log_mouse_press(watched, event)
        return False

    def _log_mouse_press(self, watched: QWidget, event: QEvent) -> None:
        """
        Protokolliert Maus-Klicks auf interaktive Widgets mit etwas Kontext.

        Eingabeparameter:
        - watched: Betroffenes Widget.
        - event: Urspruengliches Qt-Mausereignis.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Nicht passende Event-Typen werden defensiv ignoriert.

        Wichtige interne Logik:
        - Das Logging unterscheidet Buttons, Textfelder, Tabellen und allgemeine Widgets,
          damit spaetere Fehleranalysen nachvollziehen koennen, wo Benutzer interagiert haben.
        """

        if not isinstance(event, QMouseEvent):
            return
        mouse_button = getattr(event.button(), "name", str(event.button()))
        details = f"{self._describe_widget(watched)} | button={mouse_button}"
        if isinstance(watched, QAbstractButton):
            details = f"{details} | text={watched.text()!r}"
        elif isinstance(watched, QLineEdit):
            details = f"{details} | placeholder={watched.placeholderText()!r}"
        elif isinstance(watched, QPlainTextEdit):
            details = f"{details} | read_only={watched.isReadOnly()}"
        elif isinstance(watched, QTableWidget):
            details = f"{details} | rows={watched.rowCount()} | columns={watched.columnCount()}"
        self._logger.event("ui", "mouse_press", details)

    def _describe_widget(self, widget: QWidget) -> str:
        """
        Erzeugt eine kompakte Textbeschreibung eines Widgets fuer das Ereignislog.

        Eingabeparameter:
        - widget: Das zu beschreibende Qt-Widget.

        Rueckgabewerte:
        - Kompakter, menschenlesbarer Beschreibungstext.

        Moegliche Fehlerfaelle:
        - Fehlende Objekt- oder Fenstertitel werden ueber Fallbacks abgefangen.

        Wichtige interne Logik:
        - Kombiniert Widget-Klasse, Objektname und sichtbare Titel, damit Logs auch ohne
          Debugger oder Screenshots brauchbar bleiben.
        """

        object_name = widget.objectName().strip() if widget.objectName() else ""
        window_title = widget.windowTitle().strip() if hasattr(widget, "windowTitle") else ""
        visible_text = ""
        if hasattr(widget, "text"):
            try:
                visible_text = str(widget.text()).strip()
            except Exception:
                visible_text = ""

        parts = [widget.__class__.__name__]
        if object_name:
            parts.append(f"object={object_name}")
        if window_title:
            parts.append(f"title={window_title}")
        if visible_text and visible_text != window_title:
            parts.append(f"text={visible_text}")
        return " | ".join(parts)
