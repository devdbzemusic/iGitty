"""Git-CLI-Zugriffe fuer lokale Repository-Informationen."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.exceptions import IGittyError


class GitService:
    """Kapselt alle direkten Aufrufe der Git-CLI fuer den MVP."""

    def ensure_git_available(self) -> None:
        """
        Prueft, ob `git` im aktuellen Systempfad verfuegbar ist.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git ist nicht installiert oder nicht im `PATH`.

        Wichtige interne Logik:
        - Die Vorpruefung vermeidet unklare Fehlermeldungen in spaeteren Detailabfragen.
        """

        if shutil.which("git") is None:
            raise IGittyError("Git CLI wurde nicht gefunden. Bitte Git installieren oder PATH pruefen.")

    def get_repo_details(self, repo_path: Path) -> dict[str, object]:
        """
        Liest Kerninformationen eines lokalen Git-Repositories ueber die CLI aus.

        Eingabeparameter:
        - repo_path: Dateisystempfad zum lokalen Repository.

        Rueckgabewerte:
        - Dictionary mit Branch-, Remote-, Status- und Commit-Informationen.

        Moegliche Fehlerfaelle:
        - Git-Befehle schlagen fehl oder liefern unerwartete Ausgaben.

        Wichtige interne Logik:
        - Nutzt nur lesende Git-Befehle, damit der Scan sicher und reversibel bleibt.
        """

        branch = self._run_git(repo_path, ["branch", "--show-current"]).strip() or "-"
        remote_url = self._run_git(repo_path, ["remote", "get-url", "origin"], allow_failure=True).strip()
        status_lines = self._run_git(repo_path, ["status", "--porcelain"], allow_failure=True).splitlines()
        last_commit_raw = self._run_git(
            repo_path,
            ["log", "-1", "--pretty=format:%h|%cI|%s"],
            allow_failure=True,
        ).strip()

        last_commit_hash = "-"
        last_commit_date = "-"
        last_commit_message = "-"
        if last_commit_raw:
            parts = last_commit_raw.split("|", 2)
            if len(parts) == 3:
                last_commit_hash, last_commit_date, last_commit_message = parts

        modified_count = 0
        untracked_count = 0
        for line in status_lines:
            if line.startswith("??"):
                untracked_count += 1
            elif line.strip():
                modified_count += 1

        return {
            "branch": branch,
            "has_remote": bool(remote_url),
            "remote_url": remote_url,
            "has_changes": bool(status_lines),
            "untracked_count": untracked_count,
            "modified_count": modified_count,
            "last_commit_hash": last_commit_hash,
            "last_commit_date": last_commit_date,
            "last_commit_message": last_commit_message,
        }

    def clone_repository(self, clone_url: str, target_path: Path) -> None:
        """
        Klont ein Remote-Repository ueber die Git-CLI in ein lokales Zielverzeichnis.

        Eingabeparameter:
        - clone_url: Vollstaendige Clone-URL des Remote-Repositories.
        - target_path: Noch nicht existierender Zielpfad fuer den Clone.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git-Clone schlaegt fehl.
        - Das Zielverzeichnis ist nicht beschreibbar.

        Wichtige interne Logik:
        - Verwendet bewusst keine Shell, damit URL und Pfad robust uebergeben werden.
        """

        try:
            subprocess.run(
                ["git", "clone", clone_url, str(target_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            raise IGittyError(f"Clone von '{clone_url}' nach '{target_path}' fehlgeschlagen: {error}") from error

    def stage_all_changes(self, repo_path: Path) -> None:
        """
        Fuehrt `git add -A` fuer ein lokales Repository aus.

        Eingabeparameter:
        - repo_path: Ziel-Repository fuer das Staging.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git meldet einen Fehler beim Staging.

        Wichtige interne Logik:
        - Nutzt die zentrale Git-Ausfuehrung, damit Fehler konsistent behandelt werden.
        """

        self._run_git(repo_path, ["add", "-A"])

    def stage_tracked_changes(self, repo_path: Path) -> None:
        """
        Fuehrt `git add -u` fuer bereits verfolgte Dateien aus.

        Eingabeparameter:
        - repo_path: Ziel-Repository fuer das selektive Staging.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git meldet einen Fehler beim Staging.

        Wichtige interne Logik:
        - Verwendet bewusst nur tracked files fuer den entsprechenden Commit-Modus.
        """

        self._run_git(repo_path, ["add", "-u"])

    def commit(self, repo_path: Path, message: str) -> None:
        """
        Fuehrt einen Git-Commit mit der uebergebenen Nachricht aus.

        Eingabeparameter:
        - repo_path: Lokales Ziel-Repository.
        - message: Commit-Nachricht fuer den neuen Commit.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git verweigert den Commit, etwa wegen leerem Index oder fehlender Konfiguration.

        Wichtige interne Logik:
        - Der Commit nutzt keine Shell und gibt Fehler kontrolliert weiter.
        """

        self._run_git(repo_path, ["commit", "-m", message])

    def set_remote_origin(self, repo_path: Path, remote_url: str) -> None:
        """
        Setzt oder aktualisiert den `origin`-Remote eines lokalen Repositories.

        Eingabeparameter:
        - repo_path: Lokales Ziel-Repository.
        - remote_url: Gewuenschte Remote-URL fuer `origin`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git lehnt das Setzen oder Aktualisieren des Remotes ab.

        Wichtige interne Logik:
        - Prueft zuerst, ob `origin` bereits existiert und waehlt dann add oder set-url.
        """

        current_origin = self._run_git(repo_path, ["remote", "get-url", "origin"], allow_failure=True).strip()
        if current_origin:
            self._run_git(repo_path, ["remote", "set-url", "origin", remote_url])
        else:
            self._run_git(repo_path, ["remote", "add", "origin", remote_url])

    def push_current_branch(self, repo_path: Path, branch_name: str) -> None:
        """
        Pusht den aktuellen Branch inklusive Upstream-Setzung zu `origin`.

        Eingabeparameter:
        - repo_path: Lokales Ziel-Repository.
        - branch_name: Zu pushender Branch-Name.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git-Push schlaegt fehl.

        Wichtige interne Logik:
        - Setzt den Upstream beim ersten Push direkt mit, um Folgeaufrufe zu vereinfachen.
        """

        self._run_git(repo_path, ["push", "-u", "origin", branch_name])

    def _run_git(self, repo_path: Path, arguments: list[str], allow_failure: bool = False) -> str:
        """
        Fuehrt einen Git-Befehl im angegebenen Repository aus.

        Eingabeparameter:
        - repo_path: Zielpfad fuer den Git-Aufruf.
        - arguments: Argumentliste hinter dem `git`-Kommando.
        - allow_failure: Wenn `True`, werden Fehler als Leerstring zurueckgegeben.

        Rueckgabewerte:
        - Standardausgabe des Git-Kommandos als Text.

        Moegliche Fehlerfaelle:
        - Prozessfehler oder fehlende Git-Installation.

        Wichtige interne Logik:
        - Kapselt `subprocess.run`, damit die restliche Anwendung keine Shell-Details kennen muss.
        """

        try:
            completed = subprocess.run(
                ["git", *arguments],
                cwd=repo_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
            return completed.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            if allow_failure:
                return ""
            raise IGittyError(f"Git-Abfrage fuer '{repo_path}' fehlgeschlagen: {error}") from error
