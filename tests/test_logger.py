"""Tests fuer das erweiterte Datei-Logging."""

from __future__ import annotations

import logging
from pathlib import Path

from core.logger import AppLogger


def test_app_logger_writes_debug_and_info_messages_to_log_file(tmp_path: Path) -> None:
    """
    Prueft, dass der Logger sowohl Debug- als auch Info-Ereignisse nach `log.txt` schreibt.

    Eingabeparameter:
    - tmp_path: Isoliertes Temp-Verzeichnis fuer die Test-Logdatei.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - AssertionError, wenn erwartete Logtexte nicht in der Datei landen.

    Wichtige interne Logik:
    - Der Test deckt die fuer das neue Detail-Logging wichtige DEBUG-Stufe explizit mit ab.
    """

    log_file = tmp_path / "logs" / "log.txt"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = AppLogger(log_file)

    logger.event("app", "startup_begin", "Testlauf", level=logging.DEBUG)
    logger.info("Info-Nachricht fuer die UI und Datei.")

    log_text = log_file.read_text(encoding="utf-8")
    assert "[app] startup_begin | Testlauf" in log_text
    assert "INFO | Info-Nachricht fuer die UI und Datei." in log_text
