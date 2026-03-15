"""Zentrale Ableitung von UI-Aktionen aus Repository-Zustand und Regeln."""

from __future__ import annotations

from dataclasses import dataclass

from models.repo_models import LocalRepo, RemoteRepo
from models.state_models import RepositoryState


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
    """Leitet lokale und entfernte UI-Aktionen zentral aus Persistenz- und Sync-Zustaenden ab."""

    _ACTION_LABELS = {
        "open_repository": "Oeffnen",
        "show_in_explorer": "Im Explorer anzeigen",
        "clone": "Klonen",
        "pull": "Pull",
        "push": "Push",
        "commit": "Commit",
        "review_changes": "Aenderungen pruefen",
        "stash_changes": "Aenderungen sichern",
        "create_remote": "GitHub-Repository anlegen",
        "repair_remote": "Remote reparieren",
        "remove_remote": "Remote entfernen",
        "reinitialize_repository": "Repository neu initialisieren",
        "delete_local_repository": "Lokales Repository loeschen",
        "delete_remote_repository": "Remote-Repository loeschen",
        "resolve_divergence": "Divergenz aufloesen",
        "open_repo_explorer": "Repo Explorer oeffnen",
        "show_history": "Verlauf anzeigen",
        "show_diagnostics": "Diagnose anzeigen",
        "set_private": "Auf private setzen",
        "set_public": "Auf public setzen",
        "reauthenticate": "GitHub erneut verbinden",
        "refresh_repository": "Repository aktualisieren",
        "rescan": "Pfad pruefen",
    }

    def resolve_repo_actions(self, repository: RepositoryState) -> list[ResolvedRepoAction]:
        """
        Erzeugt die zentrale Aktionsliste direkt aus dem persistierten RepositoryState.

        Eingabeparameter:
        - repository: Persistierter Gesamtzustand des Repositories aus der State-DB.

        Rueckgabewerte:
        - Liste fachlich empfohlener und verfuegbarer Aktionen fuer Menues, Tabellen und Viewer.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte Kombinationen liefern eine defensive Minimalmenge.

        Wichtige interne Logik:
        - Die Methode ist die einzige Regelinstanz fuer Aktionsempfehlungen, damit
          Kontextmenues, Toolbar, Dashboard und spaetere Policies dieselben Entscheidungen nutzen.
        """

        if repository.source_type == "remote" and not repository.linked_local_path:
            return self._build_remote_only_actions(repository)

        sync_state = self._normalize_sync_state(repository.sync_state or repository.status or "NOT_INITIALIZED")
        if sync_state == "LOCAL_MISSING" or repository.is_missing or not repository.exists_local:
            return [self._action("rescan", recommended=True), self._action("show_diagnostics")]
        if sync_state == "REMOTE_ONLY":
            return self._build_remote_only_actions(repository)
        if sync_state == "LOCAL_ONLY":
            return self._merge_actions(
                [
                    self._action("create_remote", recommended=True),
                    self._action("open_repository"),
                    self._action("show_in_explorer"),
                    self._action("open_repo_explorer"),
                    self._action("show_history"),
                    self._action("show_diagnostics"),
                    self._action("reinitialize_repository"),
                ]
            )
        if sync_state == "IN_SYNC":
            return self._merge_actions(
                [
                    self._action("open_repository", recommended=True),
                    self._action("show_in_explorer"),
                    self._action("open_repo_explorer"),
                    self._action("show_history"),
                    self._action("show_diagnostics"),
                    self._visibility_action(repository),
                ]
            )
        if sync_state == "LOCAL_AHEAD":
            return self._merge_actions(
                [
                    self._action("push", recommended=True),
                    self._action("commit", recommended=repository.has_uncommitted_changes),
                    self._action("review_changes"),
                    self._action("open_repository"),
                    self._action("show_diagnostics"),
                    self._action("show_history"),
                ]
            )
        if sync_state == "REMOTE_AHEAD":
            return self._merge_actions(
                [
                    self._action("pull", recommended=True),
                    self._action("open_repository"),
                    self._action("show_diagnostics"),
                    self._action("show_history"),
                ]
            )
        if sync_state == "DIVERGED":
            return self._merge_actions(
                [
                    self._action("resolve_divergence", recommended=True),
                    self._action("show_diagnostics"),
                    self._action("show_history"),
                    self._action("open_repo_explorer"),
                ]
            )
        if sync_state == "UNCOMMITTED_LOCAL_CHANGES":
            return self._merge_actions(
                [
                    self._action("commit", recommended=True),
                    self._action("review_changes"),
                    self._action("stash_changes"),
                    self._action("open_repository"),
                    self._action("show_diagnostics"),
                ]
            )
        if sync_state == "REMOTE_MISSING":
            return self._merge_actions(
                [
                    self._action("repair_remote", recommended=True),
                    self._action("create_remote"),
                    self._action("remove_remote"),
                    self._action("show_diagnostics"),
                    self._action("show_history"),
                ]
            )
        if sync_state == "BROKEN_REMOTE":
            return self._merge_actions(
                [
                    self._action("repair_remote", recommended=True),
                    self._action("remove_remote"),
                    self._action("show_diagnostics"),
                    self._action("refresh_repository"),
                ]
            )
        if sync_state == "AUTH_REQUIRED":
            return self._merge_actions(
                [
                    self._action("reauthenticate", recommended=True),
                    self._action("show_diagnostics"),
                ]
            )
        if sync_state == "NOT_INITIALIZED":
            return self._merge_actions(
                [
                    self._action("reinitialize_repository", recommended=True),
                    self._action("show_in_explorer"),
                    self._action("show_diagnostics"),
                ]
            )
        return self._merge_actions(
            [
                self._action("refresh_repository", recommended=True),
                self._action("show_diagnostics"),
                self._action("show_history"),
            ]
        )

    def resolve_repo_primary_action(self, repository: RepositoryState) -> str:
        """
        Liefert die wichtigste empfohlene Aktion direkt aus dem persistierten RepositoryState.

        Eingabeparameter:
        - repository: Persistierter Gesamtzustand eines Repositories.

        Rueckgabewerte:
        - Kurze lesbare Primaeraktion fuer Dashboard und RepoViewer.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte Faelle liefern `-`.

        Wichtige interne Logik:
        - Textempfehlung und Aktionsliste basieren auf derselben Regelinstanz und laufen
          dadurch bei neuen Sync-Zustaenden nicht auseinander.
        """

        resolved_actions = self.resolve_repo_actions(repository)
        for action in resolved_actions:
            if action.recommended:
                return action.label
        return resolved_actions[0].label if resolved_actions else "-"

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
        - Die Local-UI wird bewusst ueber eine Abbildung auf den zentralen RepositoryState
          an dieselben Regeln wie Dashboard und RepoViewer gekoppelt.
        """

        if not repository.exists_local:
            return []
        return self.resolve_repo_actions(self._map_local_repo(repository))

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
        - Die Methode verwendet dieselbe zentrale Regelmenge wie die uebrigen UI-Bereiche.
        """

        if not repository.exists_local:
            return "Pfad fehlt"
        return self.resolve_repo_primary_action(self._map_local_repo(repository))

    def resolve_remote_actions(self, repository: RemoteRepo) -> list[ResolvedRepoAction]:
        """
        Erzeugt die verfuegbaren Kontextaktionen fuer ein Remote-Repository.

        Eingabeparameter:
        - repository: Bereits fuer die UI vorbereitetes Remote-Repository.

        Rueckgabewerte:
        - Liste der aus Sichtbarkeit, Pairing und Sync-Zustand abgeleiteten Aktionen.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte Sichtbarkeiten liefern eine defensive Minimalmenge.

        Wichtige interne Logik:
        - Auch die Remote-Seite nutzt den gemeinsamen Resolver statt einer separaten
          Sonderlogik fuer Sichtbarkeit und Repo-Zustand.
        """

        mapped_repository = self._map_remote_repo(repository)
        resolved_actions = self.resolve_repo_actions(mapped_repository)
        visibility_action = self._visibility_action(mapped_repository, recommended=True)
        if visibility_action is None:
            return resolved_actions
        return self._merge_actions([visibility_action, *resolved_actions])

    def _build_remote_only_actions(self, repository: RepositoryState) -> list[ResolvedRepoAction]:
        """
        Baut die Aktionsmenge fuer reine Remote-Repositories ohne lokales Gegenstueck.

        Eingabeparameter:
        - repository: Persistierter Remote-Repository-Zustand.

        Rueckgabewerte:
        - Liste passender Aktionen fuer Clone, Diagnose und Sichtbarkeit.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Clone ist hier die fachlich wichtigste Primaeraktion, waehrend Sichtbarkeit
          und Detailansichten als Sekundaeraktionen ergaenzt werden.
        """

        return self._merge_actions(
            [
                self._action("clone", recommended=True),
                self._action("open_repo_explorer"),
                self._action("show_history"),
                self._action("show_diagnostics"),
                self._visibility_action(repository),
            ]
        )

    def _visibility_action(self, repository: RepositoryState, recommended: bool = False) -> ResolvedRepoAction | None:
        """
        Liefert optional die passende Sichtbarkeitsaktion fuer ein GitHub-Repository.

        Eingabeparameter:
        - repository: Persistierter Zustand mit bekannter Remote-Sichtbarkeit.

        Rueckgabewerte:
        - Sichtbarkeitsaktion oder `None`, wenn keine sichere Umschaltung moeglich ist.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Sichtbarkeitsumschaltung bleibt eine separate, nicht automatisch empfohlene
          Aktion und wird nur bei echten GitHub-Repositories angeboten.
        """

        visibility = (repository.visibility or repository.remote_visibility or "").lower()
        if visibility == "public":
            return self._action("set_private", recommended=recommended)
        if visibility == "private":
            return self._action("set_public", recommended=recommended)
        return None

    def _map_local_repo(self, repository: LocalRepo) -> RepositoryState:
        """
        Uebersetzt ein LocalRepo in den zentralen RepositoryState fuer die Regelauflosung.

        Eingabeparameter:
        - repository: UI-nahes lokales Repository-Modell.

        Rueckgabewerte:
        - Minimal angereicherter RepositoryState fuer die Regelinstanz.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Mapping stellt sicher, dass Tabellen- und Persistenzsicht dieselbe
          Regelbasis nutzen, selbst wenn einzelne Felder im UI-Modell reduziert sind.
        """

        return RepositoryState(
            id=repository.state_repo_id or None,
            name=repository.name,
            source_type="local",
            local_path=repository.full_path,
            remote_url=repository.remote_url,
            github_repo_id=repository.remote_repo_id,
            visibility=repository.remote_visibility,
            is_git_repo=repository.sync_state != "NOT_INITIALIZED",
            has_remote=repository.has_remote,
            remote_configured=repository.has_remote,
            remote_owner=repository.owner,
            remote_repo_name=repository.remote_name,
            remote_exists_online=repository.remote_exists_online,
            remote_visibility=repository.remote_visibility,
            exists_local=repository.exists_local,
            git_initialized=repository.sync_state != "NOT_INITIALIZED",
            has_uncommitted_changes=repository.has_changes,
            ahead_count=repository.ahead_count,
            behind_count=repository.behind_count,
            auth_state="unknown",
            sync_state=self._normalize_sync_state(
                repository.remote_status
                if not repository.sync_state or repository.sync_state == "NOT_INITIALIZED"
                else repository.sync_state
            ),
            health_state=repository.health_state,
            needs_rescan=repository.needs_rescan,
            status=repository.remote_status or repository.sync_state,
            last_checked_at=repository.last_checked_at,
            linked_local_path=repository.full_path,
            link_type=repository.link_type,
            link_confidence=repository.link_confidence,
            sync_policy=repository.sync_policy,
            local_head_commit=repository.local_head_commit,
            remote_head_commit=repository.remote_head_commit,
            merge_base_commit=repository.merge_base_commit,
        )

    def _map_remote_repo(self, repository: RemoteRepo) -> RepositoryState:
        """
        Uebersetzt ein RemoteRepo in den zentralen RepositoryState fuer die Regelauflosung.

        Eingabeparameter:
        - repository: UI-nahes Remote-Repository-Modell.

        Rueckgabewerte:
        - Minimal angereicherter RepositoryState fuer die Regelinstanz.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Auch Remote-Kontextmenues nutzen dadurch dieselbe Logik wie persistierte
          RepositoryStates aus dem State-Layer.
        """

        return RepositoryState(
            repo_key=f"remote::{repository.repo_id}",
            name=repository.name,
            source_type="remote",
            local_path=repository.linked_local_path,
            remote_url=repository.clone_url,
            github_repo_id=repository.repo_id,
            default_branch=repository.default_branch,
            visibility=repository.visibility,
            is_archived=repository.archived,
            is_fork=repository.fork,
            remote_owner=repository.owner,
            remote_repo_name=repository.name,
            exists_local=bool(repository.linked_local_path),
            exists_remote=True,
            sync_state=self._normalize_sync_state(repository.sync_state),
            health_state=repository.health_state,
            status=repository.sync_state,
            linked_local_path=repository.linked_local_path,
            link_type=repository.link_type,
            link_confidence=repository.link_confidence,
            ahead_count=repository.ahead_count,
            behind_count=repository.behind_count,
            last_checked_at=repository.last_checked_at,
        )

    def _action(self, action_id: str, recommended: bool = False) -> ResolvedRepoAction:
        """
        Baut aus einer technischen Aktions-ID das sichtbare Aktionsobjekt auf.

        Eingabeparameter:
        - action_id: Technischer Schluessel der Aktion.
        - recommended: Kennzeichnet die Primaerempfehlung.

        Rueckgabewerte:
        - Vollstaendig vorbereitetes ResolvedRepoAction-Objekt.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte IDs werden mit ihrem Schluesseltext sichtbar gemacht.

        Wichtige interne Logik:
        - Die Methode haelt sichtbare Labels an einer zentralen Stelle zusammen.
        """

        return ResolvedRepoAction(
            action_id=action_id,
            label=self._ACTION_LABELS.get(action_id, action_id),
            recommended=recommended,
        )

    def _normalize_sync_state(self, sync_state: str) -> str:
        """
        Normalisiert Alias- und Legacy-Statuswerte auf die zentrale Sync-State-Menge.

        Eingabeparameter:
        - sync_state: Eingehender Zustand aus altem oder neuem State-Layer.

        Rueckgabewerte:
        - Normalisierter Sync-State fuer die Regelauflosung.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte Werte werden grossgeschrieben zurueckgegeben.

        Wichtige interne Logik:
        - Die Methode haelt alte Statuswerte wie `REMOTE_OK` oder `AHEAD` kompatibel,
          waehrend die neue Regelinstanz mit einer kleineren festen Zielmenge arbeitet.
        """

        normalized_state = sync_state.strip().upper()
        aliases = {
            "REMOTE_OK": "IN_SYNC",
            "AHEAD": "LOCAL_AHEAD",
            "BEHIND": "REMOTE_AHEAD",
            "REMOTE_UNREACHABLE": "BROKEN_REMOTE",
        }
        return aliases.get(normalized_state, normalized_state)

    def _merge_actions(self, actions: list[ResolvedRepoAction | None]) -> list[ResolvedRepoAction]:
        """
        Entfernt `None`-Eintraege und doppelte Aktionen aus einer Aktionsliste.

        Eingabeparameter:
        - actions: Vorlaeufige Aktionsfolge mit optionalen Eintraegen.

        Rueckgabewerte:
        - Bereinigte Liste eindeutiger Aktionen in stabiler Reihenfolge.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Doppelte technische Aktionen werden verhindert, ohne die inhaltliche
          Prioritaet der urspruenglichen Reihenfolge zu verlieren.
        """

        merged_actions: list[ResolvedRepoAction] = []
        seen_action_ids: set[str] = set()
        for action in actions:
            if action is None or action.action_id in seen_action_ids:
                continue
            merged_actions.append(action)
            seen_action_ids.add(action.action_id)
        return merged_actions
