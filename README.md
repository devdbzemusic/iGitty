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

## Lokale Tabelle

Die lokale Repository-Tabelle zeigt jetzt zusaetzlich:

- `Remote Status`
- `Online`
- `Recommended Action`

`REMOTE_MISSING`-Zeilen werden markiert. Ueber das Kontextmenue einer lokalen Zeile stehen diese Reparaturpfade bereit:

- `Repair remote`
- `Remove remote`
- `Create GitHub repository`
- `Reinitialize repository`

Das Hauptfenster enthaelt jetzt nur noch die lokale Repository-Tabelle. Die Diagnose oeffnet sich ueber das separate, nicht-modale Fenster `Diagnosefenster`, waehrend das MainWindow weiter bedienbar bleibt.

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

## Logging

iGitty schreibt jetzt ein deutlich erweitertes Laufzeitprotokoll nach `logs/log.txt`.

Dort landen unter anderem:

- App-Start und Initialisierungsschritte
- Widget-Fokus, Fensteroeffnungen und Klicks auf wichtige UI-Elemente
- Git-Kommandos und deren Erfolg oder Fehler
- detaillierte lokale Repository-Scans, Remote-Validierungen und Dateiindexierung

## Repo-Kontext

Ein Doppelklick auf ein Remote- oder lokales Repository oeffnet aktuell keinen vollstaendigen RepoViewer, sondern einen einfachen Repo-Kontext-Dialog.

Dieser Dialog ist die saubere Eintrittsschicht fuer Teil 2 und zeigt nur zusammengefuehrte Metadaten:

- Name und Full Name
- Local Path und Remote URL
- Branch- und Sichtbarkeitsdaten
- letzte bekannte Aktion
- Struktur-Vault-Zusammenfassung
- juengste State-Diagnoseereignisse aus `repo_status_events`

Die Remote-Tabelle bleibt kompakt; zusaetzliche GitHub-Basisfelder wie `created_at`, `pushed_at`, `size` und `topics` stehen aktuell ueber Tooltips an der Namensspalte zur Verfuegung.
Soweit praktikabel werden auch Contributor-Zusammenfassungen geladen und in Tooltip sowie Repo-Kontext angezeigt.

Noch nicht enthalten:

- Dateiansicht
- Editor
- Diff-Ansicht

## Starten

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Tests

```powershell
python -m compileall core controllers db models services ui tests
python -m pytest tests/test_masking.py tests/test_init_db.py tests/test_local_repo_service.py tests/test_local_repo_controller.py tests/test_remote_repo_controller.py tests/test_remote_repo_service.py tests/test_main_window.py tests/test_repo_action_resolver.py tests/test_clone_service.py tests/test_push_service.py tests/test_delete_service.py tests/test_repo_struct_service.py tests/test_repo_context_service.py tests/test_state_services.py tests/test_state_view_service.py tests/test_github_service.py tests/test_remote_visibility_service.py tests/test_logger.py tests/test_diagnostics_window.py
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
