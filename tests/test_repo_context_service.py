"""Tests fuer die Repo-Kontext-Zusammenfuehrung."""

from db.job_log_repository import JobLogRepository
from db.init_db import initialize_databases
from db.repo_struct_repository import RepoStructRepository
from db.state_repository import StateRepository
from core.paths import RuntimePaths
from models.evolution_models import RepositorySnapshotFile
from models.job_models import ActionRecord, CloneRecord
from models.repo_models import LocalRepo, RemoteRepo
from models.state_models import RepoFileState, RepoStatusEvent, RepositoryState
from services.repo_context_service import RepoContextService
from services.repository_evolution_analyzer import RepositoryEvolutionAnalyzer
from services.repository_snapshot_service import RepositorySnapshotService
from services.repo_struct_service import RepoStructService


def _build_runtime_paths(tmp_path):
    """
    Erstellt isolierte Laufzeitpfade fuer Kontext-Tests.

    Eingabeparameter:
    - tmp_path: Temporäres Testverzeichnis von pytest.

    Rueckgabewerte:
    - Vollstaendige RuntimePaths-Instanz.

    Moegliche Fehlerfaelle:
    - Keine.

    Wichtige interne Logik:
    - Verwendet frische SQLite-Dateien pro Testfall.
    """

    paths = RuntimePaths(
        project_root=tmp_path,
        assets_dir=tmp_path / "assets",
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        jobs_db_file=tmp_path / "data" / "igitty_jobs.db",
        repo_struct_db_file=tmp_path / "data" / "repo_struct_vault.db",
        state_db_file=tmp_path / "data" / "igitty_state.db",
        log_file=tmp_path / "logs" / "log.txt",
        stylesheet_file=tmp_path / "assets" / "styles" / "neon_dark.qss",
    )
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    initialize_databases(paths)
    return paths


def test_repo_context_from_local_repo(tmp_path) -> None:
    """
    Prueft die Kontextbildung fuer ein rein lokales Repository.
    """

    paths = _build_runtime_paths(tmp_path)
    job_repository = JobLogRepository(paths.jobs_db_file)
    struct_repository = RepoStructRepository(paths.repo_struct_db_file)
    state_repository = StateRepository(paths.state_db_file)
    service = RepoContextService(job_repository, RepoStructService(struct_repository), state_repository)
    local_repo = LocalRepo(
        name="demo",
        full_path="C:/demo",
        current_branch="main",
        has_remote=False,
        remote_url="",
        has_changes=False,
        untracked_count=0,
        modified_count=0,
        last_commit_hash="-",
        last_commit_date="-",
        last_commit_message="-",
        remote_visibility="not_published",
    )

    context = service.build_context(
        repo_ref={"repo_name": "demo", "local_path": "C:/demo"},
        source_type="local",
        remote_repositories=[],
        local_repositories=[local_repo],
    )

    assert context.repo_name == "demo"
    assert context.has_local_clone is True
    assert context.has_remote is False


def test_repo_context_from_remote_repo(tmp_path) -> None:
    """
    Prueft die Kontextbildung fuer ein rein entferntes Repository.
    """

    paths = _build_runtime_paths(tmp_path)
    job_repository = JobLogRepository(paths.jobs_db_file)
    struct_repository = RepoStructRepository(paths.repo_struct_db_file)
    state_repository = StateRepository(paths.state_db_file)
    service = RepoContextService(job_repository, RepoStructService(struct_repository), state_repository)
    remote_repo = RemoteRepo(
        repo_id=11,
        name="demo",
        full_name="owner/demo",
        owner="owner",
        visibility="public",
        default_branch="main",
        language="Python",
        archived=False,
        fork=False,
        clone_url="https://github.com/owner/demo.git",
        ssh_url="git@github.com:owner/demo.git",
        html_url="https://github.com/owner/demo",
        description="Demo",
        contributors_summary="alice, bob",
    )

    context = service.build_context(
        repo_ref={"remote_repo_id": 11, "repo_full_name": "owner/demo"},
        source_type="remote",
        remote_repositories=[remote_repo],
        local_repositories=[],
    )

    assert context.repo_full_name == "owner/demo"
    assert context.remote_visibility == "public"
    assert context.has_local_clone is False
    assert context.contributors_summary == "alice, bob"


def test_repo_context_merges_remote_and_local_by_remote_repo_id(tmp_path) -> None:
    """
    Prueft die Zusammenfuehrung eines Repositories mit lokaler und Remote-Entsprechung.
    """

    paths = _build_runtime_paths(tmp_path)
    job_repository = JobLogRepository(paths.jobs_db_file)
    struct_repository = RepoStructRepository(paths.repo_struct_db_file)
    state_repository = StateRepository(paths.state_db_file)
    service = RepoContextService(job_repository, RepoStructService(struct_repository), state_repository)
    remote_repo = RemoteRepo(
        repo_id=22,
        name="demo",
        full_name="owner/demo",
        owner="owner",
        visibility="private",
        default_branch="main",
        language="Python",
        archived=False,
        fork=False,
        clone_url="https://github.com/owner/demo.git",
        ssh_url="git@github.com:owner/demo.git",
        html_url="https://github.com/owner/demo",
        description="Demo",
    )
    local_repo = LocalRepo(
        name="demo",
        full_path="C:/demo",
        current_branch="main",
        has_remote=True,
        remote_url="https://github.com/owner/demo.git",
        has_changes=False,
        untracked_count=0,
        modified_count=0,
        last_commit_hash="-",
        last_commit_date="-",
        last_commit_message="-",
        remote_visibility="private",
        remote_repo_id=22,
    )

    context = service.build_context(
        repo_ref={"remote_repo_id": 22},
        source_type="local",
        remote_repositories=[remote_repo],
        local_repositories=[local_repo],
    )

    assert context.remote_repo_id == 22
    assert context.local_path == "C:/demo"
    assert context.repo_full_name == "owner/demo"


def test_repo_context_falls_back_to_remote_url_when_remote_repo_id_is_missing(tmp_path) -> None:
    """
    Prueft die Fallback-Zuordnung ueber die Remote-URL ohne vorhandene Remote-ID.
    """

    paths = _build_runtime_paths(tmp_path)
    job_repository = JobLogRepository(paths.jobs_db_file)
    struct_repository = RepoStructRepository(paths.repo_struct_db_file)
    state_repository = StateRepository(paths.state_db_file)
    service = RepoContextService(job_repository, RepoStructService(struct_repository), state_repository)
    remote_repo = RemoteRepo(
        repo_id=33,
        name="demo",
        full_name="owner/demo",
        owner="owner",
        visibility="public",
        default_branch="main",
        language="Python",
        archived=False,
        fork=False,
        clone_url="https://github.com/owner/demo.git",
        ssh_url="git@github.com:owner/demo.git",
        html_url="https://github.com/owner/demo",
        description="Demo",
    )
    local_repo = LocalRepo(
        name="demo",
        full_path="C:/demo",
        current_branch="main",
        has_remote=True,
        remote_url="https://github.com/owner/demo.git",
        has_changes=False,
        untracked_count=0,
        modified_count=0,
        last_commit_hash="-",
        last_commit_date="-",
        last_commit_message="-",
        remote_visibility="public",
        remote_repo_id=0,
    )

    context = service.build_context(
        repo_ref={"remote_url": "https://github.com/owner/demo.git"},
        source_type="local",
        remote_repositories=[remote_repo],
        local_repositories=[local_repo],
    )

    assert context.remote_repo_id == 33
    assert context.repo_name == "demo"


def test_repo_context_reads_history_and_struct_summary(tmp_path) -> None:
    """
    Prueft Historien- und Struktur-Zusammenfassung im Repo-Kontext.
    """

    paths = _build_runtime_paths(tmp_path)
    job_repository = JobLogRepository(paths.jobs_db_file)
    struct_repository = RepoStructRepository(paths.repo_struct_db_file)
    state_repository = StateRepository(paths.state_db_file)
    struct_service = RepoStructService(struct_repository)
    service = RepoContextService(job_repository, struct_service, state_repository)
    local_repo = LocalRepo(
        name="demo",
        full_path="C:/demo",
        current_branch="main",
        has_remote=True,
        remote_url="https://github.com/owner/demo.git",
        has_changes=False,
        untracked_count=0,
        modified_count=0,
        last_commit_hash="-",
        last_commit_date="-",
        last_commit_message="-",
        remote_visibility="public",
        remote_repo_id=44,
    )
    job_repository.add_clone_record(
        CloneRecord(
            job_id="clone-1",
            repo_id=44,
            repo_name="demo",
            remote_url="https://github.com/owner/demo.git",
            local_path="C:/demo",
            status="success",
            message="Clone ok",
        )
    )
    job_repository.add_action_record(
        ActionRecord(
            job_id="action-1",
            action_type="push",
            repo_name="demo",
            source_type="local",
            local_path="C:/demo",
            remote_url="https://github.com/owner/demo.git",
            status="success",
            message="Push ok",
        )
    )
    struct_repository.replace_repo_items(
        repo_identifier=struct_service.build_repo_identifier(local_path="C:/demo"),
        source_type="local",
        root_path="C:/demo",
        items=[],
    )
    state = state_repository.upsert_repository(
        RepositoryState(
            name="demo",
            local_path="C:/demo",
            is_git_repo=True,
            current_branch="main",
            head_commit="abc123",
            head_commit_date="2026-03-12T10:00:00+00:00",
            has_remote=True,
            remote_name="origin",
            remote_url="https://github.com/owner/demo.git",
            remote_host="github.com",
            remote_owner="owner",
            remote_repo_name="demo",
            remote_exists_online=1,
            remote_visibility="public",
            status="REMOTE_OK",
            last_local_scan_at="2026-03-12T10:00:00+00:00",
            last_remote_check_at="2026-03-12T10:01:00+00:00",
        )
    )
    state_repository.add_status_event(
        RepoStatusEvent(
            repo_id=int(state.id or 0),
            event_type="REMOTE_VALIDATION_COMPLETED",
            message="Remote-Status: REMOTE_OK",
            created_at="2026-03-12T10:01:00+00:00",
        )
    )

    context = service.build_context(
        repo_ref={"local_path": "C:/demo", "repo_name": "demo"},
        source_type="local",
        remote_repositories=[],
        local_repositories=[local_repo],
    )

    assert context.last_action_type in {"clone", "push"}
    assert context.last_action_status == "success"
    assert context.struct_item_count == 0
    assert context.diagnostic_events
    assert "REMOTE_VALIDATION_COMPLETED" in context.diagnostic_events[0]
    assert context.history_entries
    assert context.repository_status == "REMOTE_OK"


def test_repo_context_handles_missing_data_without_crashing(tmp_path) -> None:
    """
    Prueft, dass fehlende Datenquellen keinen Absturz verursachen.
    """

    paths = _build_runtime_paths(tmp_path)
    job_repository = JobLogRepository(paths.jobs_db_file)
    struct_repository = RepoStructRepository(paths.repo_struct_db_file)
    state_repository = StateRepository(paths.state_db_file)
    service = RepoContextService(job_repository, RepoStructService(struct_repository), state_repository)

    context = service.build_context(
        repo_ref={"repo_name": "unbekannt"},
        source_type="remote",
        remote_repositories=[],
        local_repositories=[],
    )

    assert context.repo_name == "unbekannt"
    assert context.last_action_type is None


def test_repo_context_builds_timeline_and_snapshots_when_services_are_available(tmp_path) -> None:
    """
    Prueft, dass der RepoContext bei vorhandenem Snapshot-Service Timeline- und Evolutionsdaten fuellt.
    """

    paths = _build_runtime_paths(tmp_path)
    job_repository = JobLogRepository(paths.jobs_db_file)
    struct_repository = RepoStructRepository(paths.repo_struct_db_file)
    state_repository = StateRepository(paths.state_db_file)
    struct_service = RepoStructService(struct_repository)
    snapshot_service = RepositorySnapshotService(
        state_repository=state_repository,
        job_log_repository=job_repository,
        repo_struct_repository=struct_repository,
        repo_struct_service=struct_service,
    )
    analyzer = RepositoryEvolutionAnalyzer(snapshot_service)
    service = RepoContextService(
        job_repository,
        struct_service,
        state_repository,
        repository_snapshot_service=snapshot_service,
        repository_evolution_analyzer=analyzer,
    )
    local_repo = LocalRepo(
        name="demo",
        full_path="C:/demo",
        current_branch="main",
        has_remote=True,
        remote_url="https://github.com/owner/demo.git",
        has_changes=False,
        untracked_count=0,
        modified_count=0,
        last_commit_hash="-",
        last_commit_date="-",
        last_commit_message="-",
        remote_visibility="public",
        remote_repo_id=44,
    )
    state = state_repository.upsert_repository(
        RepositoryState(
            repo_key="local::c:/demo",
            name="demo",
            local_path="C:/demo",
            is_git_repo=True,
            current_branch="main",
            head_commit="abc123",
            has_remote=True,
            remote_url="https://github.com/owner/demo.git",
            remote_owner="owner",
            remote_repo_name="demo",
            status="REMOTE_OK",
            scan_fingerprint="fp-1",
            status_hash="status-1",
        )
    )
    state_repository.update_repo_files_delta(
        int(state.id or 0),
        [
            RepoFileState(
                repo_id=int(state.id or 0),
                relative_path="src/app.py",
                path_type="file",
                content_hash="hash-1",
                last_seen_at="2026-03-15T10:00:00+00:00",
                last_seen_scan_at="2026-03-15T10:00:00+00:00",
            )
        ],
    )
    struct_repository.replace_repo_items(
        repo_identifier=struct_service.build_repo_identifier(local_path="C:/demo"),
        source_type="local",
        root_path="C:/demo",
        items=[],
    )
    snapshot_service.capture_snapshot_for_repository(state, trigger_type="local_scan", force=True)

    context = service.build_context(
        repo_ref={"local_path": "C:/demo", "repo_name": "demo"},
        source_type="local",
        remote_repositories=[],
        local_repositories=[local_repo],
    )

    assert context.snapshots
    assert context.timeline_entries
    assert context.evolution_summary is not None
