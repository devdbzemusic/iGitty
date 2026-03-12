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
