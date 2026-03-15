"""Tests fuer das erweiterte Datei-Logging."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from core.app_event_monitor import install_app_event_monitoring
from core.logger import AppLogger
from services.git_service import GitService


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


def test_git_service_logs_expected_allow_failure_as_debug_instead_of_warning(tmp_path: Path, monkeypatch) -> None:
    """
    Prueft, dass erwartete Git-Fallbacks nicht als Warnung im Log landen.

    Eingabeparameter:
    - tmp_path: Isoliertes Temp-Verzeichnis fuer die Test-Logdatei.
    - monkeypatch: pytest-Helfer zum Austauschen von `subprocess.run`.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - AssertionError, wenn `allow_failure` weiterhin Warnungen schreibt.

    Wichtige interne Logik:
    - Typische Faelle wie fehlendes `origin` oder fehlender Commit sollen das Log nicht mehr
      mit Warnungen fluten, weil sie im Scanner bewusst als erwartete Fallbacks behandelt werden.
    """

    log_file = tmp_path / "logs" / "log.txt"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = AppLogger(log_file)
    git_service = GitService(logger=logger)

    def _raise_called_process_error(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=2, cmd=["git", "remote", "get-url", "origin"])

    monkeypatch.setattr(subprocess, "run", _raise_called_process_error)

    result = git_service.get_remote_url(tmp_path, "origin")

    assert result == ""
    log_text = log_file.read_text(encoding="utf-8")
    assert "WARNING" not in log_text
    assert "command_expected_failure" in log_text


def test_app_event_monitor_logs_unhandled_main_thread_exceptions(tmp_path: Path) -> None:
    """
    Prueft, dass globale Hauptthread-Ausnahmen ueber den installierten Hook in `log.txt` landen.

    Eingabeparameter:
    - tmp_path: Isoliertes Temp-Verzeichnis fuer die Test-Logdatei.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - AssertionError, wenn der Hook keine Fehlerdetails in die Logdatei schreibt.

    Wichtige interne Logik:
    - Der Test simuliert direkt den von Python verwendeten `sys.excepthook`, ohne die
      Testsession selbst durch eine echte ungefangene Ausnahme abbrechen zu lassen.
    """

    log_file = tmp_path / "logs" / "log.txt"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = AppLogger(log_file)
    resources = install_app_event_monitoring(logger, log_file)

    try:
        try:
            raise RuntimeError("Boom im Hauptthread")
        except RuntimeError as error:
            sys.excepthook(type(error), error, error.__traceback__)
    finally:
        resources.close()

    log_text = log_file.read_text(encoding="utf-8")
    assert "Unbehandelte Ausnahme im Hauptthread entdeckt" in log_text
    assert "Boom im Hauptthread" in log_text
