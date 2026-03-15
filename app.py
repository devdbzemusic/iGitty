"""Startlogik fuer die iGitty-Desktop-Anwendung."""

from __future__ import annotations

import logging
import sys

from controllers.main_controller import MainController
from core.app_event_monitor import LoggedApplication, install_app_event_monitoring
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
    event_monitor_resources = install_app_event_monitoring(logger, paths.log_file)
    logger.event("app", "startup_begin", f"log_file={paths.log_file}", level=logging.INFO)
    try:
        env_settings = load_environment()
        logger.event("app", "environment_loaded")
        initialize_databases(paths)
        logger.event("app", "databases_initialized")
        config = build_app_config(env_settings, paths)
        logger.event("app", "config_built", f"default_repo_dir={config.default_repo_dir}")

        application = LoggedApplication(sys.argv, logger)
        application.setApplicationName(config.application_name)
        application.setOrganizationName(config.organization_name)
        application.aboutToQuit.connect(
            lambda: logger.event("app", "about_to_quit", "Qt meldet kontrollierten Shutdown.", level=logging.INFO)
        )
        application.lastWindowClosed.connect(
            lambda: logger.event("app", "last_window_closed", level=logging.INFO)
        )
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
        main_controller = MainController(
            window=window,
            config=config,
            env_settings=env_settings,
            paths=paths,
            logger=logger,
        )
        application.aboutToQuit.connect(main_controller.shutdown)
        window.show()
        logger.event("app", "main_window_shown")
        exit_code = application.exec()
        logger.event("app", "event_loop_finished", f"exit_code={exit_code}", level=logging.INFO)
        return exit_code
    except Exception as error:  # noqa: BLE001
        logger.log_exception_details(
            "Unbehandelte Ausnahme waehrend der App-Initialisierung oder Event-Loop-Ausfuehrung",
            type(error),
            error,
            error.__traceback__,
        )
        return 1
    finally:
        logger.event("app", "shutdown_cleanup_begin")
        event_monitor_resources.close()
