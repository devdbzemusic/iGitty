# iGitty

iGitty ist eine Windows-first Desktop-Anwendung auf Basis von PySide6 zum Verwalten von Remote-GitHub-Repositories und lokalen Git-Repositories in einer gemeinsamen Oberflaeche.

## Aktueller Stand

MVP Teil 1 ist umgesetzt und um einen persistenten lokalen State-Layer erweitert:

- Remote-GitHub-Repositories laden und anzeigen
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

- `repositories`: lokaler Repository-Zustand inklusive Branch, HEAD, Remote-Metadaten und Status
- `repo_files`: einfacher Dateiindex pro Repository
- `repo_status_events`: technische Zustandsereignisse wie lokale Scans oder Remote-Validierungen

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

Unter der lokalen Tabelle zeigt ein eigener Diagnosebereich fuer das aktuell ausgewaehlte Repository:

- den persistierten State-Status
- Remote- und Online-Zustand
- letzte lokale Scan- und Remote-Check-Zeit
- die juengsten `repo_status_events`

Zusaetzlich zeigt ein eigener Bereich `Job-Historie` unter der lokalen Tabelle:

- die juengsten Clone-, Commit-, Push-, Delete- und Struktur-Aktionen
- die kombinierte Sicht aus `clone_history` und `action_history`

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
python -m pytest tests/test_masking.py tests/test_init_db.py tests/test_local_repo_service.py tests/test_clone_service.py tests/test_push_service.py tests/test_delete_service.py tests/test_repo_struct_service.py tests/test_repo_context_service.py tests/test_state_services.py tests/test_state_view_service.py tests/test_github_service.py
```

## Architekturhinweise

- Keine Businesslogik in Widgets oder Dialogen
- SQLite-Zugriffe liegen in Repository- oder Service-Schichten
- Langsame lokale Scans laufen weiterhin ausserhalb des UI-Threads
- Pushes beruecksichtigen jetzt den persistierten Repository-Status vor dem eigentlichen `git push`
- Der Statusbereich zeigt beim erfolgreichen Remote-Laden den ermittelten GitHub-Login an, wenn die API ihn liefern konnte

`igitty_jobs.db` fuehrt inzwischen neben der allgemeinen Job-Uebersicht auch die naeher an den Langprompt angelehnten Tabellen:

- `job_steps`
- `repo_snapshots`
- `commit_history`
- `push_history`
- `delete_history`
