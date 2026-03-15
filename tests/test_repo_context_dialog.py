"""Tests fuer den RepoViewer-Kontextdialog."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication, QTabWidget

from models.job_models import ActionSummary
from models.evolution_models import RepositoryEvolutionSummary, RepositoryTimelineEntry, SnapshotDiffResult
from models.state_models import RepoStatusEvent, ScanRunRecord
from models.struct_models import RepoTreeItem
from models.view_models import RepoContext
from ui.dialogs.repo_context_dialog import RepoContextDialog


def _get_or_create_application() -> QApplication:
    """
    Liefert eine vorhandene Qt-Anwendung oder erzeugt eine neue Testinstanz.
    """

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_repo_context_dialog_builds_phase_two_tabs() -> None:
    """
    Prueft, dass der RepoViewer-Dialog die neuen Phase-II-Tabs aufbaut.
    """

    _get_or_create_application()
    context = RepoContext(
        source_type="local",
        repo_name="demo",
        repository_status="REMOTE_OK",
        health_state="healthy",
        sync_state="SYNCED",
        recommended_action="Push",
        available_actions=["push", "commit"],
        tree_items=[
            RepoTreeItem(
                repo_identifier="local::c:/demo",
                relative_path="src/app.py",
                item_type="file",
                extension=".py",
                git_status="M",
                last_commit_hash="abc123",
            )
        ],
        history_entries=[
            ActionSummary(action_type="push", status="success", timestamp="2026-03-15T10:00:00+00:00", message="Ok")
        ],
        status_events=[
            RepoStatusEvent(
                repo_id=1,
                event_type="LOCAL_SCAN_COMPLETED",
                severity="info",
                message="Lokaler Scan fertig",
                created_at="2026-03-15T10:00:00+00:00",
            )
        ],
        recent_scan_runs=[
            ScanRunRecord(
                id=1,
                scan_type="local_normal_refresh",
                started_at="2026-03-15T10:00:00+00:00",
                finished_at="2026-03-15T10:00:01+00:00",
                duration_ms=1000,
                changed_count=1,
                unchanged_count=0,
                error_count=0,
            )
        ],
        timeline_entries=[
            RepositoryTimelineEntry(
                timestamp="2026-03-15T10:00:00+00:00",
                entry_type="snapshot",
                title="Snapshot | local_scan",
                details="Demo",
            )
        ],
        evolution_summary=RepositoryEvolutionSummary(snapshot_count=1, current_file_count=1, peak_file_count=1),
        snapshot_diffs=[SnapshotDiffResult(previous_snapshot_id=1, current_snapshot_id=2, commit_changed=True)],
    )

    dialog = RepoContextDialog(context=context)
    tabs = dialog.findChild(QTabWidget)

    assert tabs is not None
    assert tabs.count() == 7
    assert tabs.tabText(1) == "Dashboard"
    assert tabs.tabText(2) == "Repo Explorer"
    assert tabs.tabText(4) == "Timeline"
    assert tabs.tabText(6) == "Evolution"
