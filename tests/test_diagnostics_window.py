"""Tests fuer das Diagnosefenster mit Live-Log-Anzeige."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ui.dialogs.diagnostics_window import DiagnosticsWindow


def _get_or_create_application() -> QApplication:
    """
    Liefert eine vorhandene Qt-Anwendung oder erzeugt eine neue Testinstanz.

    Eingabeparameter:
    - Keine.

    Rueckgabewerte:
    - Laufende `QApplication` fuer Widget-Tests.

    Moegliche Fehlerfaelle:
    - Keine; die Testumgebung nutzt bei Bedarf eine Offscreen-Plattform.

    Wichtige interne Logik:
    - Die Hilfsfunktion verhindert mehrere konkurrierende QApplication-Instanzen.
    """

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_diagnostics_window_reads_live_log_file(tmp_path: Path) -> None:
    """
    Prueft, dass das Diagnosefenster den Inhalt der `log.txt` sichtbar laedt.

    Eingabeparameter:
    - tmp_path: Isoliertes Temp-Verzeichnis fuer eine kuenstliche Logdatei.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - AssertionError, wenn der geladene Text nicht im Live-Log-Feld erscheint.

    Wichtige interne Logik:
    - Der Test deckt den Kernpfad fuer manuelles und automatisches Nachladen der Logdatei ab.
    """

    _get_or_create_application()
    log_file = tmp_path / "logs" / "log.txt"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("erste zeile\nzweite zeile", encoding="utf-8")

    window = DiagnosticsWindow()
    window.set_live_log_file(log_file)
    window.refresh_live_log(force=True)

    assert "erste zeile" in window._live_log_panel.toPlainText()
    assert "zweite zeile" in window._live_log_panel.toPlainText()
