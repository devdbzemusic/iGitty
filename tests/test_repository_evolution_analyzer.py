"""Tests fuer RepositoryEvolutionAnalyzer."""

from __future__ import annotations

from models.evolution_models import RepositorySnapshot, RepositorySnapshotFile
from services.repository_evolution_analyzer import RepositoryEvolutionAnalyzer
from services.repository_snapshot_service import RepositorySnapshotService


def test_repository_evolution_analyzer_computes_growth_and_activity() -> None:
    """
    Prueft Wachstum, Dateitypen und Aktivitaetsphasen aus einer Snapshot-Reihe.
    """

    snapshot_service = RepositorySnapshotService.__new__(RepositorySnapshotService)
    analyzer = RepositoryEvolutionAnalyzer(snapshot_service)
    snapshots = [
        RepositorySnapshot(
            id=1,
            repo_key="local::demo",
            snapshot_timestamp="2026-03-15T10:00:00+00:00",
            head_commit="a1",
            file_count=1,
            files=[RepositorySnapshotFile(relative_path="src/app.py", path_type="file", extension=".py")],
        ),
        RepositorySnapshot(
            id=2,
            repo_key="local::demo",
            snapshot_timestamp="2026-03-15T10:20:00+00:00",
            head_commit="b2",
            file_count=3,
            files=[
                RepositorySnapshotFile(relative_path="src/app.py", path_type="file", extension=".py"),
                RepositorySnapshotFile(relative_path="src/util.py", path_type="file", extension=".py"),
                RepositorySnapshotFile(relative_path="README.md", path_type="file", extension=".md"),
            ],
        ),
    ]

    summary, diffs = analyzer.analyze(snapshots)

    assert summary.snapshot_count == 2
    assert summary.current_file_count == 3
    assert summary.peak_file_count == 3
    assert summary.growth_rate_per_snapshot == 2.0
    assert any(".py" in item for item in summary.most_common_file_types)
    assert diffs[0].commit_changed is True
    assert any("aktive Phase" in item for item in summary.activity_phases)
