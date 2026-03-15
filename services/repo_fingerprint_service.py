"""Erzeugt leichte und stabile Fingerprints fuer Delta-Scans."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from models.repo_models import RemoteRepo
from models.state_models import RepoFileState, RepositoryState


class RepoFingerprintService:
    """Kapselt alle Hash- und Fingerprint-Berechnungen fuer den State-Layer."""

    def build_local_quick_fingerprint(self, repo_path: Path) -> str:
        """
        Erzeugt einen leichten Fingerprint fuer ein lokales Repository ohne Tiefenscan.

        Eingabeparameter:
        - repo_path: Lokaler Repository-Pfad.

        Rueckgabewerte:
        - Stabiler SHA256-Hash ueber guenstige Dateisystemindikatoren.

        Moegliche Fehlerfaelle:
        - Nicht vorhandene Pfade oder fehlende Dateien liefern trotzdem einen stabilen Hash.

        Wichtige interne Logik:
        - Die Berechnung betrachtet nur billige Marker wie `.git`, `HEAD`, `index`,
          `packed-refs` und einige Ref-Verzeichnisse, damit unveraenderte Repositories
          ohne `git status` oder Dateiindexierung erkannt werden koennen.
        """

        git_dir = repo_path / ".git"
        payload = {
            "repo_path": str(repo_path),
            "repo_exists": repo_path.exists(),
            "git_exists": git_dir.exists(),
            "repo_mtime_ns": self._safe_mtime_ns(repo_path),
            "git_mtime_ns": self._safe_mtime_ns(git_dir),
            "head_file": self._stat_payload(git_dir / "HEAD"),
            "index_file": self._stat_payload(git_dir / "index"),
            "packed_refs_file": self._stat_payload(git_dir / "packed-refs"),
            "refs_heads_dir": self._stat_payload(git_dir / "refs" / "heads"),
            "refs_tags_dir": self._stat_payload(git_dir / "refs" / "tags"),
            "refs_remotes_dir": self._stat_payload(git_dir / "refs" / "remotes"),
        }
        return self._hash_payload(payload)

    def build_repository_status_hash(self, repository: RepositoryState) -> str:
        """
        Erzeugt einen Hash ueber die fuer Status und UI relevanten Repository-Zustandsfelder.

        Eingabeparameter:
        - repository: Vollstaendiger persistierter oder vorbereiteter Repository-Zustand.

        Rueckgabewerte:
        - Stabiler SHA256-Hash ueber Status- und Sync-relevante Felder.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Werte werden als regulaere String-/Bool-Werte serialisiert.

        Wichtige interne Logik:
        - Der Hash dient dazu, fachliche Zustandsaenderungen von reinen Zeitstempel-Updates
          zu trennen und nur echte inhaltliche Delta-Updates als geaendert zu markieren.
        """

        payload = {
            "source_type": repository.source_type,
            "local_path": repository.local_path,
            "remote_url": repository.remote_url,
            "github_repo_id": repository.github_repo_id,
            "default_branch": repository.default_branch,
            "visibility": repository.visibility,
            "is_archived": repository.is_archived,
            "is_fork": repository.is_fork,
            "is_deleted": repository.is_deleted,
            "is_missing": repository.is_missing,
            "language": repository.language,
            "description": repository.description,
            "topics_json": repository.topics_json,
            "contributors_count": repository.contributors_count,
            "contributors_summary": repository.contributors_summary,
            "created_at": repository.created_at,
            "updated_at": repository.updated_at,
            "pushed_at": repository.pushed_at,
            "size_kb": repository.size_kb,
            "is_git_repo": repository.is_git_repo,
            "current_branch": repository.current_branch,
            "head_commit": repository.head_commit,
            "head_commit_date": repository.head_commit_date,
            "has_remote": repository.has_remote,
            "remote_exists_online": repository.remote_exists_online,
            "remote_visibility": repository.remote_visibility,
            "exists_local": repository.exists_local,
            "exists_remote": repository.exists_remote,
            "git_initialized": repository.git_initialized,
            "remote_configured": repository.remote_configured,
            "has_uncommitted_changes": repository.has_uncommitted_changes,
            "ahead_count": repository.ahead_count,
            "behind_count": repository.behind_count,
            "is_diverged": repository.is_diverged,
            "auth_state": repository.auth_state,
            "sync_state": repository.sync_state,
            "health_state": repository.health_state,
            "dirty_hint": repository.dirty_hint,
            "needs_rescan": repository.needs_rescan,
            "status": repository.status,
            "linked_repo_key": repository.linked_repo_key,
            "linked_local_path": repository.linked_local_path,
            "link_type": repository.link_type,
            "link_confidence": repository.link_confidence,
            "local_head_commit": repository.local_head_commit,
            "remote_head_commit": repository.remote_head_commit,
            "merge_base_commit": repository.merge_base_commit,
            "last_sync_decision": repository.last_sync_decision,
            "sync_policy": repository.sync_policy,
            "recommended_action": repository.recommended_action,
            "available_actions_json": repository.available_actions_json,
        }
        return self._hash_payload(payload)

    def build_remote_fingerprint(self, repository: RemoteRepo) -> str:
        """
        Erzeugt einen Fingerprint ueber die fuer Remote-Delta-Updates relevanten Felder.

        Eingabeparameter:
        - repository: Remote-Repository aus der GitHub-API.

        Rueckgabewerte:
        - Stabiler SHA256-Hash ueber relevante Remote-Metadaten.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Auswahl konzentriert sich auf Felder, die fachlich sichtbare Aenderungen
          in iGitty ausloesen koennen, statt jedes API-Detail mitzuspeichern.
        """

        payload = {
            "repo_id": repository.repo_id,
            "full_name": repository.full_name,
            "visibility": repository.visibility,
            "default_branch": repository.default_branch,
            "language": repository.language,
            "description": repository.description,
            "topics": repository.topics,
            "contributors_count": repository.contributors_count,
            "contributors_summary": repository.contributors_summary,
            "archived": repository.archived,
            "fork": repository.fork,
            "created_at": repository.created_at,
            "updated_at": repository.updated_at,
            "pushed_at": repository.pushed_at,
            "size": repository.size,
        }
        return self._hash_payload(payload)

    def build_file_delta_hash(self, file_state: RepoFileState) -> str:
        """
        Erzeugt einen Hash ueber die relevanten Delta-Felder eines Dateiindex-Eintrags.

        Eingabeparameter:
        - file_state: Einzelner persistierbarer Dateieintrag.

        Rueckgabewerte:
        - Stabiler SHA256-Hash fuer Delta-Vergleiche.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Hash trennt echte Dateiaenderungen von reinem `last_seen_at`-Touching.
        """

        payload = {
            "relative_path": file_state.relative_path,
            "path_type": file_state.path_type,
            "size_bytes": file_state.size_bytes,
            "modified_at": file_state.modified_at,
            "content_hash": file_state.content_hash,
            "is_tracked": file_state.is_tracked,
            "is_ignored": file_state.is_ignored,
            "is_deleted": file_state.is_deleted,
        }
        return self._hash_payload(payload)

    def _stat_payload(self, path: Path) -> dict[str, object]:
        """
        Baut eine kompakte, fehlertolerante Dateistatus-Beschreibung fuer Fingerprints.

        Eingabeparameter:
        - path: Zu pruefender Dateisystempfad.

        Rueckgabewerte:
        - Dictionary mit Existenz- und Zeitstempelinformationen.

        Moegliche Fehlerfaelle:
        - Nicht zugreifbare Pfade werden defensiv als nicht vorhanden behandelt.

        Wichtige interne Logik:
        - Die Funktion ist bewusst schmal, damit Fingerprint-Berechnungen auch bei defekten
          Repositories stabil bleiben.
        """

        return {
            "exists": path.exists(),
            "mtime_ns": self._safe_mtime_ns(path),
        }

    def _safe_mtime_ns(self, path: Path) -> int:
        """
        Liest die Nanosekunden-Mtime eines Pfads fehlertolerant aus.

        Eingabeparameter:
        - path: Zu pruefender Dateisystempfad.

        Rueckgabewerte:
        - Nanosekunden-Zeitstempel oder `0`, wenn der Pfad fehlt oder nicht lesbar ist.

        Moegliche Fehlerfaelle:
        - Dateisystemfehler werden defensiv abgefangen.

        Wichtige interne Logik:
        - `0` als Fallback haelt die Hash-Bildung deterministisch und einfach testbar.
        """

        try:
            return path.stat().st_mtime_ns
        except OSError:
            return 0

    def _hash_payload(self, payload: dict[str, object]) -> str:
        """
        Serialisiert ein Dictionary stabil und erzeugt daraus einen SHA256-Hash.

        Eingabeparameter:
        - payload: Beliebige serialisierbare Fingerprint-Nutzlast.

        Rueckgabewerte:
        - Hexadezimale SHA256-Darstellung.

        Moegliche Fehlerfaelle:
        - Nicht serialisierbare Werte sind in den aufrufenden Methoden bereits ausgeschlossen.

        Wichtige interne Logik:
        - `sort_keys=True` sorgt fuer deterministische Hashes unabhaengig von der
          Einfuegereihenfolge der Nutzlastfelder.
        """

        rendered = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
