"""Startlogik fuer die iGitty-Desktop-Anwendung."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from controllers.main_controller import MainController
from core.config import build_app_config
from core.env import load_environment
from core.logger import AppLogger
from core.paths import ensure_runtime_paths
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

    env_settings = load_environment()
    paths = ensure_runtime_paths()
    logger = AppLogger(paths.log_file)
    initialize_databases(paths)
    config = build_app_config(env_settings, paths)

    application = QApplication(sys.argv)
    application.setApplicationName(config.application_name)
    application.setOrganizationName(config.organization_name)

    if config.stylesheet_path.exists():
        application.setStyleSheet(config.stylesheet_path.read_text(encoding="utf-8"))

    window = MainWindow()
    MainController(
        window=window,
        config=config,
        env_settings=env_settings,
        paths=paths,
        logger=logger,
    )
    window.show()
    return application.exec()
