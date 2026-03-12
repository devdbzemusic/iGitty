"""Datamodelle fuer Job- und Protokolleintraege."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class JobLogEntry:
    """Beschreibt einen protokollierten Arbeitsschritt in der Job-Datenbank."""

    job_id: str
    action_type: str
    source_type: str
    repo_name: str
    status: str
    message: str
    repo_owner: str = ""
    local_path: str = ""
    remote_url: str = ""
    reversible_flag: bool = False


@dataclass(slots=True)
class CloneRecord:
    """Beschreibt das Ergebnis eines einzelnen Clone-Vorgangs."""

    job_id: str
    repo_id: int
    repo_name: str
    remote_url: str
    local_path: str
    status: str
    message: str
    repo_owner: str = ""
    reversible_flag: bool = True


@dataclass(slots=True)
class ActionRecord:
    """Allgemeines Ergebnisobjekt fuer Commit-, Push-, Delete- und Struktur-Scans."""

    job_id: str
    action_type: str
    repo_name: str
    source_type: str
    local_path: str
    remote_url: str
    status: str
    message: str
    repo_owner: str = ""
    reversible_flag: bool = False


@dataclass(slots=True)
class ActionSummary:
    """Kompakte Zusammenfassung einer letzten bekannten Aktion fuer ein Repository."""

    action_type: str
    status: str
    timestamp: str | None
    message: str = ""


@dataclass(slots=True)
class JobStepRecord:
    """Beschreibt einen feingranularen Schritt innerhalb eines groesseren Jobs."""

    job_id: str
    step_name: str
    status: str
    message: str
    step_index: int = 0


@dataclass(slots=True)
class RepoSnapshotRecord:
    """Beschreibt einen Snapshot des betroffenen Repository-Kontexts fuer einen Job."""

    job_id: str
    action_type: str
    source_type: str
    repo_name: str
    repo_owner: str
    local_path: str
    remote_url: str
    status: str
    reversible_flag: bool
