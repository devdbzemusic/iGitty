"""Lesende Aufbereitung des State-Layers fuer Diagnoseanzeigen in der UI."""

from __future__ import annotations

from db.state_repository import StateRepository


class StateViewService:
    """Bereitet persistente Repository-Zustaende fuer kompakte UI-Diagnosen auf."""

    def __init__(self, state_repository: StateRepository) -> None:
        """
        Initialisiert den Service mit Zugriff auf die State-Datenbank.

        Eingabeparameter:
        - state_repository: Repository-Zugriff auf `igitty_state.db`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Der Service bleibt rein lesend und erzeugt bereits formatierte Textzeilen fuer die UI.
        """

        self._state_repository = state_repository

    def build_local_repo_diagnostics(self, local_path: str) -> list[str]:
        """
        Baut eine kompakte Diagnoseansicht fuer ein lokales Repository.

        Eingabeparameter:
        - local_path: Vollstaendiger lokaler Repository-Pfad.

        Rueckgabewerte:
        - Liste formatierter Textzeilen fuer eine Diagnosebox.

        Moegliche Fehlerfaelle:
        - Unbekannte Repositories liefern eine kurze Platzhalterdiagnose statt eines Fehlers.

        Wichtige interne Logik:
        - Kombiniert Repository-Grundzustand und juengste Ereignisse in einer lesbaren Reihenfolge.
        """

        repository = self._state_repository.fetch_repository_by_local_path(local_path)
        if repository is None or repository.id is None:
            return ["Noch kein persistierter State-Eintrag fuer dieses Repository vorhanden."]

        lines = [
            f"Status: {repository.status}",
            f"Remote: {repository.remote_url or '-'}",
            f"Online: {self._format_online_state(repository.remote_exists_online)}",
            f"Visibility: {repository.remote_visibility or '-'}",
            f"Letzter lokaler Scan: {repository.last_local_scan_at or '-'}",
            f"Letzter Remote-Check: {repository.last_remote_check_at or '-'}",
            "",
            "Juengste Diagnoseereignisse:",
        ]
        events = self._state_repository.fetch_recent_events(int(repository.id), limit=8)
        if not events:
            lines.append("- Keine Diagnoseereignisse vorhanden.")
            return lines

        lines.extend(f"- {event.created_at} | {event.event_type} | {event.message or '-'}" for event in events)
        return lines

    def _format_online_state(self, remote_exists_online: int | None) -> str:
        """
        Uebersetzt den gespeicherten Online-Status in einen lesbaren Text.

        Eingabeparameter:
        - remote_exists_online: `1`, `0` oder `None`.

        Rueckgabewerte:
        - Lesbarer Diagnosewert fuer die UI.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Abbildung bleibt zentral, damit Diagnosefenster und Tabellen dieselben Begriffe verwenden.
        """

        if remote_exists_online == 1:
            return "vorhanden"
        if remote_exists_online == 0:
            return "fehlt"
        return "unbekannt"
