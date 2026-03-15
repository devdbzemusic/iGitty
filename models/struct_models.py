"""Datamodelle fuer persistente Repo-Struktur-Scans."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RepoTreeItem:
    """
    Beschreibt einen einzelnen persistierten Datei- oder Ordnerknoten im Struktur-Vault.

    Eingabeparameter:
    - repo_identifier: Stabiler technischer Repository-Schluessel fuer den Vault.
    - relative_path: Relativer Pfad innerhalb des Repositories.
    - item_type: `file` oder `dir`.
    - size: Dateigroesse in Bytes oder `0` fuer Verzeichnisse.
    - extension: Dateiendung in Kleinbuchstaben fuer spaetere Filter.
    - last_modified: ISO-Zeitstempel der letzten Dateisystemaenderung.
    - git_status: Kompakter Git-Status wie `M`, `A`, `??` oder `clean`.
    - last_commit_hash: Letzter bekannter Commit-Hash fuer diesen Knoten.
    - version_scan_timestamp: Zeitstempel des letzten Struktur-Scans.
    - is_deleted: Kennzeichnet verschwundene Knoten per Soft-Delete.

    Rueckgabewerte:
    - Keine; die Dataklasse dient als Transportobjekt.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Das Modell enthaelt bewusst bereits UI-relevante Felder wie Git-Status und
      Commit-Hash, damit der RepoExplorer spaeter DB-first arbeiten kann.
    """

    repo_identifier: str
    relative_path: str
    item_type: str
    size: int = 0
    extension: str = ""
    last_modified: str = ""
    git_status: str = ""
    last_commit_hash: str = ""
    version_scan_timestamp: str = ""
    is_deleted: bool = False


@dataclass(slots=True)
class RepoStructureScanStats:
    """
    Fasst das Delta-Ergebnis eines Struktur-Scans fuer Diagnose und Logging zusammen.

    Eingabeparameter:
    - inserted_count: Anzahl neu angelegter Knoten.
    - updated_count: Anzahl veraenderter Knoten.
    - deleted_count: Anzahl weich als geloescht markierter Knoten.
    - unchanged_count: Anzahl unveraenderter Knoten.
    - total_count: Gesamtanzahl der aktuell sichtbaren Knoten.
    - scan_timestamp: Zeitstempel des zugehoerigen Scan-Laufs.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Die Statistik trennt Struktur-Persistenz bewusst von der UI-Darstellung, damit
      Logging, Tests und spaetere Performance-Auswertungen denselben Datensatz nutzen.
    """

    inserted_count: int = 0
    updated_count: int = 0
    deleted_count: int = 0
    unchanged_count: int = 0
    total_count: int = 0
    scan_timestamp: str = ""
