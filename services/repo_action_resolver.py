"""Zentrale Ableitung von UI-Aktionen aus Repository-Zustand und Regeln."""

from __future__ import annotations

from dataclasses import dataclass

from models.repo_models import LocalRepo


@dataclass(slots=True)
class ResolvedRepoAction:
    """
    Beschreibt eine aus dem aktuellen Repository-Zustand abgeleitete UI-Aktion.

    Eingabeparameter:
    - action_id: Technischer Schluessel fuer Controller und Kontextmenues.
    - label: Sichtbare Bezeichnung in der UI.
    - recommended: Kennzeichnet die primaere oder bevorzugte Aktion.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Die Trennung aus `action_id` und `label` verhindert, dass Controller-Logik an
      sichtbaren Texten haengt.
    """

    action_id: str
    label: str
    recommended: bool = False


class RepoActionResolver:
    """Leitet lokale UI-Aktionen zentral aus Zustand und Regeln ab."""

    def resolve_local_actions(self, repository: LocalRepo) -> list[ResolvedRepoAction]:
        """
        Erzeugt die verfuegbaren Kontextaktionen fuer ein lokales Repository.

        Eingabeparameter:
        - repository: Bereits fuer die UI vorbereitetes lokales Repository.

        Rueckgabewerte:
        - Liste technisch und fachlich aufgeloester Aktionen.

        Moegliche Fehlerfaelle:
        - Keine; unklare Stati liefern eine kleine defensive Standardmenge.

        Wichtige interne Logik:
        - Die Regeln leben absichtlich an einer Stelle, damit Tabellenanzeige,
          Kontextmenue und spaetere DB-first-Workflows dieselbe Fachentscheidung nutzen.
        """

        if not repository.exists_local:
            return []

        if repository.remote_status == "REMOTE_MISSING":
            return [
                ResolvedRepoAction("repair_remote", "Repair remote", recommended=True),
                ResolvedRepoAction("remove_remote", "Remove remote"),
                ResolvedRepoAction("create_remote", "Create GitHub repository"),
            ]

        if repository.remote_status == "BROKEN_GIT":
            return [
                ResolvedRepoAction("reinitialize_repository", "Reinitialize repository", recommended=True),
            ]

        if not repository.has_remote or repository.remote_status == "LOCAL_ONLY":
            return [
                ResolvedRepoAction("create_remote", "Create GitHub repository", recommended=True),
                ResolvedRepoAction("reinitialize_repository", "Reinitialize repository"),
            ]

        actions = [
            ResolvedRepoAction("remove_remote", "Remove remote"),
            ResolvedRepoAction("reinitialize_repository", "Reinitialize repository"),
        ]
        if repository.remote_status == "REMOTE_UNREACHABLE":
            actions.insert(0, ResolvedRepoAction("repair_remote", "Repair remote", recommended=True))
        return actions

    def resolve_local_primary_action(self, repository: LocalRepo) -> str:
        """
        Liefert die kompakte Primaerempfehlung fuer die lokale Tabellenansicht.

        Eingabeparameter:
        - repository: Bereits fuer die UI vorbereitetes lokales Repository.

        Rueckgabewerte:
        - Kurzer Empfehlungstext fuer die Spalte `Recommended Action`.

        Moegliche Fehlerfaelle:
        - Keine; unklare Faelle liefern `-`.

        Wichtige interne Logik:
        - Die Methode konzentriert sich auf die sichtbar wichtigste Aktion und wird
          vom breiteren Kontextmenue in `resolve_local_actions` ergaenzt.
        """

        if not repository.exists_local:
            return "Pfad fehlt"
        if repository.remote_status == "REMOTE_OK":
            return "Normal pushen"
        if repository.remote_status == "LOCAL_ONLY":
            return "GitHub-Repo anlegen"
        if repository.remote_status == "REMOTE_MISSING":
            return "Remote reparieren"
        if repository.remote_status == "REMOTE_UNREACHABLE":
            return "Remote pruefen"
        if repository.remote_status == "BROKEN_GIT":
            return "Repo reparieren"
        if repository.remote_status == "NOT_INITIALIZED":
            return "Git initialisieren"
        return "-"
