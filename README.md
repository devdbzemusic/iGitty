# iGitty

iGitty ist ein Windows-first Desktop-Werkzeug fuer das gemeinsame Verwalten von Remote-GitHub-Repositories und lokalen Git-Repositories in einer zweispaltigen Arbeitsoberflaeche.

## MVP Teil 1

- Startbare PySide6-Anwendung mit 2-Pane-Hauptfenster
- Dunkles QSS-Theme
- Laden von `GITHUB_ACCESS_TOKEN`, `GITHUBAPP_CLIENT_ID` und `IGITTY_REPO_DIR`
- Initialisierung von `igitty_jobs.db` und `repo_struct_vault.db`
- Remote-GitHub-Repository-Ladelogik ueber die GitHub-REST-API mit Pagination
- Checkbox-Tabelle fuer Remote-Repositories inklusive Filter und "Alle auswaehlen"
- Lokale Repository-Erkennung mit Git-CLI-Statusdaten
- Lokale Hauptliste ohne sichtbare Pfad-Spalte; der Pfad bleibt intern erhalten und ist per Tooltip verfuegbar
- Public-Spalte in der lokalen Tabelle mit sauberer Unterscheidung zwischen `public`, `private`, `unknown` und `not_published`
- Clone-Workflow mit sicherem Ueberspringen vorhandener Zielordner
- Commit-Workflow mit Dialog fuer Nachricht und Stage-Modus
- Push-Workflow mit optionaler Remote-Erstellung auf GitHub
- Sichere Remote-Loeschung nur mit Clone-Nachweis aus SQLite und Textbestaetigung
- Struktur-Scan lokaler Repositories in `repo_struct_vault.db`
- Statusanzeige fuer GitHub-Verbindung, Rate Limit, Repo-Anzahl und Zielordner

## Start

1. Python 3.12 installieren.
2. Abhaengigkeiten installieren:

```powershell
python -m pip install -r requirements.txt
```

3. Umgebungsvariablen setzen oder `.env.example` als Vorlage verwenden.
4. Anwendung starten:

```powershell
python main.py
```

## Umgebungsvariablen

- `GITHUB_ACCESS_TOKEN`: Personal Access Token fuer GitHub.
- `GITHUBAPP_CLIENT_ID`: Reserviert fuer spaetere GitHub-App-Authentifizierung.
- `IGITTY_REPO_DIR`: Standardzielordner fuer lokale Repositories.

## Projektstruktur

- `ui/`: Fenster, Widgets und Worker
- `controllers/`: Verbindet UI und Services
- `services/`: GitHub-, Git- und Fachlogik
- `db/`: SQLite-Verwaltung und Repositories
- `models/`: Datamodelle fuer Repositories und Jobs
- `core/`: Konfiguration, Pfade, Logging und Hilfsfunktionen

## RepoViewer Teil 2

- Doppelklick auf Remote- und Local-Zeilen ist bereits an `open_repo_context(...)` angebunden.
- Der aktuelle RepoViewer nutzt den Struktur-Vault aus `repo_struct_vault.db` und zeigt gespeicherte Strukturknoten in einer Baumansicht an.
- Fuer lokale Repositories ist der Viewer nach einem Struktur-Scan direkt nutzbar.
- Fuer Remote-Repositories wird ein gespeicherter `remote_clone`-Strukturstand erwartet.

## Verifikation

- Build-Check: `python -m compileall .`
- Testlauf: `python -m pytest`
- GUI-Start: `python main.py`

## Logging und Datenbanken

- `igitty_jobs.db` enthaelt `jobs`, `clone_history` und `action_history`.
- `repo_struct_vault.db` speichert baumartige Strukturknoten fuer den spaeteren RepoViewer.
- Delete-Pruefungen verwenden Clone-Nachweise ueber `repo_name`, `remote_url` und `repo_id`.
- Lokale Repositories speichern zusaetzlich `remote_visibility` sowie eine optionale lokale Push-Vorgabe `publish_as_public`.

## Bekannte Grenzen

- Der RepoViewer ist als erster Vault-basierter Viewer vorhanden, aber noch kein vollwertiger Code-/Datei-Explorer.
- Push setzt voraus, dass das lokale Repository bereits initialisiert und commit-faehig ist.
- Remote-Viewer-Inhalte haengen davon ab, dass fuer geklonte Remotes bereits Strukturdaten gespeichert wurden.
