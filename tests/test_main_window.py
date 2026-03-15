"""Tests fuer gezielte Local-Row-Updates im MainWindow."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

from models.repo_models import LocalRepo
from ui.main_window import MainWindow


def _get_or_create_application() -> QApplication:
    """
    Liefert eine vorhandene Qt-Anwendung oder erzeugt eine neue Testinstanz.
    """

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _build_local_repo(**overrides) -> LocalRepo:
    """
    Erzeugt ein lokales Repository-Testmodell mit ueberschreibbaren Defaults.
    """

    payload = {
        "name": "demo",
        "full_path": "C:/demo",
        "current_branch": "main",
        "has_remote": True,
        "remote_url": "https://github.com/dbzs/demo.git",
        "has_changes": False,
        "untracked_count": 0,
        "modified_count": 0,
        "last_commit_hash": "abc123",
        "last_commit_date": "2026-03-15T10:00:00+00:00",
        "last_commit_message": "Demo",
        "remote_status": "REMOTE_OK",
        "recommended_action": "Normal pushen",
        "available_actions": ["remove_remote"],
        "state_status_hash": "hash-1",
    }
    payload.update(overrides)
    return LocalRepo(**payload)


def test_main_window_upserts_and_removes_local_repository_without_full_rebuild() -> None:
    """
    Prueft, dass das MainWindow lokale Eintraege gezielt ersetzen und entfernen kann.
    """

    _get_or_create_application()
    window = MainWindow()
    first_repository = _build_local_repo()
    changed_repository = _build_local_repo(
        recommended_action="Remote reparieren",
        remote_status="REMOTE_MISSING",
        available_actions=["repair_remote", "remove_remote"],
    )

    window.populate_local_repositories([first_repository])
    window.upsert_local_repository(changed_repository)

    repositories_after_upsert = window.get_local_repositories()
    assert len(repositories_after_upsert) == 1
    assert repositories_after_upsert[0].recommended_action == "Remote reparieren"

    window.remove_local_repository("C:/demo")

    assert window.get_local_repositories() == []
