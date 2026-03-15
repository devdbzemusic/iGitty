# iGitty

iGitty ist eine Windows-first Desktop-Anwendung auf Basis von PySide6 zum Verwalten von Remote-GitHub-Repositories und lokalen Git-Repositories in einer gemeinsamen Oberflaeche.

## Aktueller Stand

MVP Teil 1 ist umgesetzt und um einen persistenten lokalen State-Layer erweitert:

- Remote-GitHub-Repositories laden und anzeigen
- Sichtbarkeit bestehender Remote-Repositories direkt in der Remote-Liste umschalten
- Lokale Git-Repositories scannen und anzeigen
- Ausgewaehlte Remote-Repositories lokal klonen
- Ausgewaehlte lokale Repositories committen
- Lokale Repositories auf GitHub pushen
- Neue GitHub-Repositories fuer lokale Repositories anlegen
- Remote-Loeschen mit Sicherheitslogik
- Repo-Kontext per Doppelklick als Vorbereitung fuer Teil 2
- Persistente Repository-Zustandsdaten in `data/igitty_state.db`

## State-Layer

Der neue State-Layer speichert den lokalen Scan-Zustand getrennt von Job-Log und Struktur-Vault:

- `data/igitty_jobs.db`: Job- und Aktionsprotokolle
- `data/repo_struct_vault.db`: strukturorientierte Vault-Daten fuer Teil 2
- `data/igitty_state.db`: persistente Repository-Metadaten, Online-Status und Dateiindex

`igitty_state.db` enthaelt aktuell:

- `repositories`: Repository-Stammdaten plus Fingerprints, Soft-Delete-/Missing-Marker und letzte Sichtung
- `repo_status`: volatile Zustandsdaten wie Sync-State, Dirty-Hint, Ahead/Behind und `needs_rescan`
- `repo_links`: persistierte Pairing-Verknuepfungen zwischen lokalen und GitHub-Repositories
- `repo_files`: deltafaehiger Dateiindex pro Repository mit `is_deleted`-Markern statt Vollersetzung
- `repo_status_events`: technische Zustandsereignisse wie lokale Scans oder Remote-Validierungen
- `scan_runs`: Statistik fuer Normal- und Hard-Refresh-Laeufe

## Delta-Refresh

STUFE 1 fuehrt jetzt eine robuste Delta-Basis fuer lokale State-Scans ein:

- bekannte Repositories behalten einen leichten Fingerprint aus `.git`-Markerdateien
- bei unveraendertem Fingerprint wird kein Tiefenscan ausgefuehrt
- nur geaenderte oder als `needs_rescan` markierte Repositories laufen durch Git-Inspektion und Dateiindexierung
- verschwundene Repositories werden per Missing-/Soft-Delete-Marker erhalten statt hart geloescht
- `scan_runs` unterscheiden Normal Refresh und Hard Refresh im Backend

## DB-First-Start

STUFE 2 nutzt die State-DB jetzt fuer beide Hauptlisten aktiv:

- beim App-Start werden bekannte lokale und Remote-Repositories sofort aus SQLite geladen
- danach starten Hintergrund-Refreshes ueber die bestehenden Worker-Pfade
- nach dem Refresh liest die UI den aktuellen Zustand erneut aus SQLite
- nur geaenderte oder entfernte Zeilen werden gezielt aktualisiert
- lokale und Remote-Kontextaktionen werden zentral aus Zustand und Regeln abgeleitet

## Pairing und Sync

Die Anwendung behandelt lokale und entfernte Repositories jetzt als technische Paare, sobald eine belastbare Verknuepfung vorliegt.

Die Pairing-Prioritaet ist:

- exakte Remote-URL
- bekannte GitHub-Repository-ID
- Owner/Repository-Name
- rein diagnostischer Name-Match als unsicherer Hinweis

Der zentrale Sync-Analyzer berechnet dabei unter anderem:

- `local_head_commit`
- `remote_head_commit`
- `merge_base_commit`
- `ahead_count`
- `behind_count`
- `has_uncommitted_changes`
- `sync_state`
- `health_state`
- `recommended_action`

Aktuell verwendete Sync-Zustaende:

- `LOCAL_ONLY`
- `REMOTE_ONLY`
- `IN_SYNC`
- `LOCAL_AHEAD`
- `REMOTE_AHEAD`
- `DIVERGED`
- `UNCOMMITTED_LOCAL_CHANGES`
- `REMOTE_MISSING`
- `LOCAL_MISSING`
- `BROKEN_REMOTE`
- `AUTH_REQUIRED`
- `NOT_INITIALIZED`

## Lokale Tabelle

Die lokale Repository-Tabelle zeigt jetzt zusaetzlich:

- `Owner`
- `Local Path`
- `Sync State`
- `Ahead`
- `Behind`
- `Health`
- `Recommended Action`
- `Last Checked`

Problematische Sync-Zustaende wie `REMOTE_MISSING`, `DIVERGED` oder `LOCAL_AHEAD` werden farblich markiert. Ueber das Kontextmenue einer lokalen Zeile stehen je nach Zustand zentrale Folgeaktionen bereit:

- `Commit`
- `Push`
- `Repair remote`
- `Remove remote`
- `GitHub-Repository anlegen`
- `Repository neu initialisieren`
- `Repo Explorer oeffnen`
- `Verlauf anzeigen`
- `Diagnose anzeigen`

Das Hauptfenster ist jetzt klarer gegliedert in:

- eine Toolbar mit Primaeraktionen wie `Alles aktualisieren`, `Pull`, `Push`, `Commit`, `Clone` und `Publish`
- eine kombinierte Repository-Haupttabelle fuer lokale und reine Remote-Repositories
- ein eingebettetes Repository-Details-Panel
- getrennte Panels fuer Diagnose, Job-Historie und Laufzeitlog

Die Toolbar- und Menueaktionen reagieren auf den aktuellen `Sync State` des ausgewaehlten Repositorys. Die Diagnose oeffnet sich weiterhin ueber das separate, nicht-modale Fenster `Diagnosefenster`, waehrend das MainWindow bedienbar bleibt.

Im Diagnosefenster sieht man fuer das aktuell ausgewaehlte Repository:

- den persistierten State-Status
- Remote- und Online-Zustand
- letzte lokale Scan- und Remote-Check-Zeit
- die juengsten `repo_status_events`
- ein Live-Log-Feld, das die zentrale `logs/log.txt` mit Auto-Refresh spiegelt

Zusaetzlich zeigt das Diagnosefenster einen Bereich `Job-Historie`:

- die juengsten Clone-, Commit-, Push-, Delete- und Struktur-Aktionen
- die kombinierte Sicht aus `clone_history` und `action_history`

## Remote-Tabelle

In der Remote-Liste kann die Sichtbarkeit eines Eintrags jetzt direkt ueber das Kontextmenue der Zeile geaendert werden:

- `Auf private setzen`
- `Auf public setzen`

Zusetzlich gilt jetzt fuer STUFE 2:

- beim Start zeigt die Remote-Liste sofort den zuletzt bekannten SQLite-Zustand
- der GitHub-Refresh aktualisiert nur geaenderte Remote-Zeilen
- verschwundene GitHub-Repositories werden gezielt aus der Tabelle entfernt
- die fuer Tooltips benoetigten GitHub-Basisfelder wie `topics`, `description`, `contributors_summary`, `created_at`, `updated_at`, `pushed_at` und `size` werden ebenfalls im State-Cache gehalten
- die Tabelle zeigt jetzt auch den verknuepften `Local Path`, `Sync State`, `Health` und die `Recommended Action`

## Menues

Die Menuestruktur ist jetzt operativ gruppiert:

- `Datei`: GitHub-Hinweis, Zielordner, Einstellungen, Datenordner, Log-Datei und Beenden
- `Synchronisieren`: Remote laden, lokalen Scan, Alles aktualisieren, Normal Refresh, Hard Refresh, ausgewaehltes Repository aktualisieren
- `Repository`: zustandsabhaengige Repository-Aktionen fuer die aktuelle Selektion
- `Analyse`: Repo Explorer, Historie, Diagnose, Struktur-Scan und Status-Neuberechnung
- `Ansicht`: Diagnosebereich, Job-Historie, Logbereich, Repo-Explorer-Einstieg, Spalten-Hinweis und Filter-Reset
- `Hilfe`: Ueber-Dialog, README und Entwicklerdokumentation

Das Repository-Menue, die Toolbar und das Kontextmenue aktivieren nur Aktionen, die zur aktuellen lokalen oder Remote-Selektion passen.

## Logging

iGitty schreibt jetzt ein deutlich erweitertes Laufzeitprotokoll nach `logs/log.txt`.

Dort landen unter anderem:

- App-Start und Initialisierungsschritte
- Widget-Fokus, Fensteroeffnungen und Klicks auf wichtige UI-Elemente
- Git-Kommandos und deren Erfolg oder Fehler
- detaillierte lokale Repository-Scans, Remote-Validierungen und Dateiindexierung

## RepoViewer Phase II

Ein Doppelklick auf ein Remote- oder lokales Repository oeffnet jetzt den RepoViewer fuer MVP Phase II.

Der RepoViewer ist SQLite-first und kombiniert Local-, Remote-, State-, Struktur- und Historiedaten in Tabs:

- `Ueberblick`: kompakte Metadaten und Diagnose-Kurzansicht
- `Dashboard`: `Health State`, `Sync State`, `Recommended Action`, letzte Scans und persistierte Fingerprints
- `Repo Explorer`: baumartige Struktur aus `repo_struct_vault.db` mit Git-Status und Extension-Filter
- `Historie`: Clone-, Commit-, Push-, Delete- und Struktur-Aktionen aus den Job-Tabellen
- `Diagnose`: append-only `repo_status_events` plus juengste `scan_runs`

Neu in Phase II:

- `RepositorySyncOrchestrator` als zentrale Sync-Koordinationsschicht
- persistierte `recommended_action`- und `available_actions`-Felder im State-Layer
- deltafaehiger `RepositoryStructureScanner` fuer `repo_struct_vault.db`
- strukturierte Diagnoseevents wie `STRUCT_SCAN_DONE`, `REMOTE_SYNC_COMPLETED` oder `LOCAL_SCAN_SKIPPED_UNCHANGED`

## Time-Travel & Evolution Explorer

iGitty fuehrt jetzt zusaetzlich ein Repository-Time-Travel-System ein:

- `RepositorySnapshotService` erzeugt bei erfolgreichen Scans und relevanten Aktionen neue Snapshots
- redundante Scan-Snapshots werden uebersprungen, solange Fingerprint, Commit und Struktur unveraendert bleiben
- `repo_snapshots` speichert jetzt auch `repo_key`, `snapshot_timestamp`, `branch`, `head_commit`, `file_count`, `change_count`, `scan_fingerprint` und `structure_hash`
- `repo_snapshot_files` haelt die diffbare Dateimenge je Snapshot
- `RepositoryEvolutionAnalyzer` berechnet Wachstum, Dateitypenhaeufigkeit, Strukturveraenderungen und Aktivitaetsphasen

Der RepoViewer enthaelt dafuer zwei weitere Tabs:

- `Timeline`: Snapshots, Aktionen, Diagnoseevents und Scan-Laeufe in einer Chronologie
- `Evolution`: Wachstumskennzahlen, Snapshot-Diffs und Strukturentwicklung

Noch weiterhin nicht enthalten:

- Editor
- Diff-Ansicht
- Merge- oder Rebase-Workflows

## Starten

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Tests

```powershell
python -m compileall core controllers db models services ui tests
python -m pytest tests/test_masking.py tests/test_init_db.py tests/test_local_repo_service.py tests/test_local_repo_controller.py tests/test_remote_repo_controller.py tests/test_remote_repo_service.py tests/test_main_window.py tests/test_repo_action_resolver.py tests/test_clone_service.py tests/test_push_service.py tests/test_delete_service.py tests/test_repo_struct_service.py tests/test_repo_context_service.py tests/test_repository_structure_scanner.py tests/test_repository_sync_orchestrator.py tests/test_repository_snapshot_service.py tests/test_repository_evolution_analyzer.py tests/test_repo_context_dialog.py tests/test_state_services.py tests/test_state_view_service.py tests/test_github_service.py tests/test_remote_visibility_service.py tests/test_logger.py tests/test_diagnostics_window.py
```

## Architekturhinweise

- Keine Businesslogik in Widgets oder Dialogen
- SQLite-Zugriffe liegen in Repository- oder Service-Schichten
- Langsame lokale Scans laufen weiterhin ausserhalb des UI-Threads
- Langsame Remote-Refreshes synchronisieren zuerst in SQLite und aktualisieren danach nur geaenderte UI-Zeilen
- Pushes beruecksichtigen jetzt den persistierten Repository-Status vor dem eigentlichen `git push`
- Der Statusbereich zeigt beim erfolgreichen Remote-Laden den ermittelten GitHub-Login an, wenn die API ihn liefern konnte

`igitty_jobs.db` fuehrt inzwischen neben der allgemeinen Job-Uebersicht auch die naeher an den Langprompt angelehnten Tabellen:

- `job_steps`
- `repo_snapshots`
- `commit_history`
- `push_history`
- `delete_history`
