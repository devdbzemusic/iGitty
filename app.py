"""Startlogik fuer die iGitty-Desktop-Anwendung."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from controllers.main_controller import MainController
from core.config import build_app_config
from core.env import load_environment
from core.logger import AppLogger
from core.paths import ensure_runtime_paths
from core.ui_event_logger import UiEventLogger
from db.init_db import initialize_databases
from ui.main_window import MainWindow


def main() -> int:
    """
    Startet die Qt-Anwendung und initialisiert die Basiskomponenten.

    Eingabeparameter:
    - Keine.

    Rueckgabewerte:
    - Prozessrueckgabecode der Qt-Ereignisschleife.

    Moegliche Fehlerfaelle:
    - Fehlende oder defekte Runtime-Verzeichnisse.
    - Nicht initialisierbare Datenbanken.
    - Nicht ladbare Stylesheet-Datei.

    Wichtige interne Logik:
    - Laedt zuerst die Umgebungsvariablen und Pfade.
    - Initialisiert danach Logging und SQLite.
    - Erzeugt das Hauptfenster erst, wenn der technische Unterbau bereit ist.
    """

    paths = ensure_runtime_paths()
    logger = AppLogger(paths.log_file)
    logger.event("app", "startup_begin", f"log_file={paths.log_file}", level=logging.INFO)
    env_settings = load_environment()
    logger.event("app", "environment_loaded")
    initialize_databases(paths)
    logger.event("app", "databases_initialized")
    config = build_app_config(env_settings, paths)
    logger.event("app", "config_built", f"default_repo_dir={config.default_repo_dir}")

    application = QApplication(sys.argv)
    application.setApplicationName(config.application_name)
    application.setOrganizationName(config.organization_name)
    logger.event("app", "qapplication_initialized", f"name={config.application_name}")
    UiEventLogger(application, logger)
    logger.event("app", "ui_event_logger_installed")

    if config.stylesheet_path.exists():
        application.setStyleSheet(config.stylesheet_path.read_text(encoding="utf-8"))
        logger.event("app", "stylesheet_loaded", f"path={config.stylesheet_path}")
    else:
        logger.warning(f"Stylesheet wurde nicht gefunden: {config.stylesheet_path}")

    window = MainWindow()
    logger.event("app", "main_window_created")
    MainController(
        window=window,
        config=config,
        env_settings=env_settings,
        paths=paths,
        logger=logger,
    )
    window.show()
    logger.event("app", "main_window_shown")
    return application.exec()
