"""Tests fuer gezielte Local-Row-Updates im MainWindow."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

from models.repo_models import LocalRepo, RemoteRepo
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


def _build_remote_repo(**overrides) -> RemoteRepo:
    """
    Erzeugt ein Remote-Repository-Testmodell mit ueberschreibbaren Standardwerten.
    """

    payload = {
        "repo_id": 7,
        "name": "demo",
        "full_name": "dbzs/demo",
        "owner": "dbzs",
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "archived": False,
        "fork": False,
        "clone_url": "https://github.com/dbzs/demo.git",
        "ssh_url": "git@github.com:dbzs/demo.git",
        "html_url": "https://github.com/dbzs/demo",
        "description": "Demo",
        "topics": ["python"],
        "contributors_count": 1,
        "contributors_summary": "alice",
        "created_at": "2026-03-01T10:00:00Z",
        "updated_at": "2026-03-10T10:00:00Z",
        "pushed_at": "2026-03-11T10:00:00Z",
        "size": 123,
        "available_actions": ["set_private"],
        "state_status_hash": "remote-hash-1",
    }
    payload.update(overrides)
    return RemoteRepo(**payload)


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


def test_main_window_upserts_and_removes_remote_repository_without_full_rebuild() -> None:
    """
    Prueft, dass das MainWindow Remote-Eintraege gezielt ersetzen und entfernen kann.
    """

    _get_or_create_application()
    window = MainWindow()
    first_repository = _build_remote_repo()
    changed_repository = _build_remote_repo(
        visibility="private",
        available_actions=["set_public"],
        state_status_hash="remote-hash-2",
    )

    window.populate_remote_repositories([first_repository])
    window.upsert_remote_repository(changed_repository)

    repositories_after_upsert = window.get_remote_repositories()
    assert len(repositories_after_upsert) == 1
    assert repositories_after_upsert[0].visibility == "private"

    window.remove_remote_repository(7)

    assert window.get_remote_repositories() == []
