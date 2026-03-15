# AGENTS.md — iGitty

## Projektname
iGitty

## Produktkontext
iGitty ist eine Windows-first Desktop-App für das Verwalten von **Remote-GitHub-Repositories** und **lokalen Git-Repositories** in einer gemeinsamen Oberfläche.

Der Schwerpunkt von **MVP Teil 1** liegt auf:

- Remote-GitHub-Repositories laden und anzeigen
- lokale Git-Repositories erkennen und anzeigen
- ausgewählte Remote-Repositories lokal klonen
- ausgewählte lokale Repositories committen
- lokale Repositories auf GitHub hochschieben
- neue GitHub-Repositories für lokale Repositories anlegen
- alle relevanten Aktionen in SQLite protokollieren
- Remote-Löschen nur mit Sicherheitslogik und Clone-Nachweis erlauben
- Vorbereitung des Repo-Struktur-Vaults für Teil 2
- Vorbereitung eines späteren RepoViewers, aber noch ohne Implementierung

**Nicht Ziel von MVP Teil 1:**
- vollständiger RepoViewer
- Diff-Ansichten
- Merge-/Rebase-Workflows
- Branch-Visualisierung
- GitHub Issues / Pull Requests / Actions Management
- Secret Management UI
- Multi-Account-Orchestrierung
- Cloud-Sync außerhalb GitHub

---

## Grundprinzipien

1. **Stabilität vor Cleverness**
   - Bevorzuge robuste, gut lesbare Lösungen.
   - Keine unnötig komplexen Abstraktionen.

2. **Saubere Architektur**
   - Trenne UI, Geschäftslogik, Services, Datenmodelle und DB-Zugriffe strikt.
   - Keine Businesslogik direkt in Widgets oder Dialogen.

3. **Nicht-blockierende UI**
   - Alle langsamen Operationen laufen in Worker-Threads oder vergleichbaren Hintergrundmechanismen.
   - Die UI darf nie einfrieren.

4. **Nachvollziehbarkeit**
   - Jede relevante Aktion muss in SQLite protokolliert werden.
   - Jede protokollierte Aktion erhält eine `job_id`.

5. **Sichere Defaults**
   - Destruktive Aktionen brauchen Validierung, Vorprüfung und Bestätigung.
   - Remote-Löschen niemals leichtfertig implementieren.

6. **Erweiterbarkeit**
   - Architektur für RepoViewer Teil 2 vorbereiten.
   - Hooks und saubere Schnittstellen vorsehen.

7. **Keine Geheimnisse leaken**
   - Tokens, Zugangsdaten und andere sensible Inhalte niemals unmaskiert loggen oder anzeigen.

8. **State-DB zuerst**
   - Persistente Repository-Stammdaten, Status, Dateiindex und Scan-Ereignisse bleiben in SQLite die zentrale Quelle.
   - Normale Refreshes sollen ueber Fingerprints und Delta-Updates unnoetige Tiefenscans vermeiden.
   - Missing-/Soft-Delete-Marker sind zu bevorzugen, wenn Repositories temporaer verschwinden.

9. **DB-first-UI**
   - Lokale und Remote-Listen sollen beim Start zuerst den letzten bekannten SQLite-Zustand anzeigen.
   - Hintergrundsyncs sollen danach nur geaenderte Zeilen gezielt nachziehen statt komplette Listen neu aufzubauen.
   - UI-Aktionen sollen zentral aus Zustand und Regeln abgeleitet werden.
   - Remote-Metadaten fuer Tooltips und spaetere RepoViewer-Einstiege sollen ebenfalls im State-Cache landen.

10. **Pairing und Sync-Analyse**
   - Lokale und entfernte Repositories sollen ueber `repo_links` oder gleichwertige State-Strukturen verknuepft werden.
   - Sichere Matches ueber URL oder GitHub-ID haben Vorrang vor unsicheren Namensmatches.
   - Sync-Zustaende muessen auf Git-Beziehungen wie HEAD, Merge-Base, Ahead/Behind und ungecommitteten Aenderungen basieren.
   - Gefaehrliche Git-Aktionen bleiben explizit und duerfen nie blind automatisiert werden.

---

## Technologie-Stack

- Python 3.12
- PySide6
- requests
- subprocess für Git CLI
- sqlite3
- pathlib
- Standardbibliothek bevorzugen, wenn ausreichend

### Erlaubt
- dataclasses
- typing
- enum
- json
- logging
- threading / Qt Worker
- datetime
- os / sys
- traceback

### Nicht bevorzugt
- unnötige Heavyweight-Frameworks
- überladene Dependency-Ketten
- GitPython nur dann, wenn wirklich nötig — standardmäßig **git CLI via subprocess** verwenden

---

## Umgebungsvariablen

Die Anwendung muss diese Variablen berücksichtigen:

- `GITHUB_ACCESS_TOKEN`
- `GITHUBAPP_CLIENT_ID`
- `IGITTY_REPO_DIR`

### Regeln
- Werte aus EnvVars bevorzugt verwenden
- manuelle Eingaben optional ermöglichen, aber nicht erzwingen
- Secrets maskieren
- Secrets niemals im Klartext loggen
- bei fehlenden Variablen klare Fehlermeldung oder Hinweis anzeigen

---

## Zielarchitektur

Die Projektstruktur soll sich an dieser Form orientieren:

```text
iGitty/
├─ app.py
├─ main.py
├─ requirements.txt
├─ README.md
├─ .env.example
├─ assets/
├─ data/
├─ logs/
├─ ui/
│  ├─ dialogs/
│  ├─ widgets/
│  └─ workers/
├─ core/
├─ models/
├─ services/
├─ db/
├─ controllers/
├─ tests/
└─ docs/
