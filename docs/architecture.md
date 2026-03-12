# Architektur

iGitty trennt die Anwendung in `ui`, `controllers`, `services`, `db`, `models` und `core`.

- `ui` enthaelt nur Darstellung, Widgets und Worker.
- `controllers` verbinden UI-Signale mit Fachoperationen.
- `services` kapseln GitHub- und spaetere Git-Operationen.
- `db` kapselt SQLite-Schemata und Schreibzugriffe.
- `core` enthaelt Konfiguration, Pfade, Logging und Hilfsfunktionen.

Der aktuelle MVP-Stand setzt den startbaren Rahmen und das asynchrone Laden von Remote-GitHub-Repositories um.
