"""Git-CLI-Zugriffe fuer lokale Repository-Informationen."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.exceptions import IGittyError
from core.logger import AppLogger


class GitService:
    """Kapselt alle direkten Aufrufe der Git-CLI fuer den MVP."""

    def __init__(self, logger: AppLogger | None = None) -> None:
        """
        Initialisiert den Git-Service optional mit einem Logger.

        Eingabeparameter:
        - logger: Optionaler zentraler Logger fuer detailreiche Git-Kommando-Protokolle.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine bei der Initialisierung.

        Wichtige interne Logik:
        - Das Logging bleibt optional, damit Tests den Service weiterhin leichtgewichtig
          ohne weitere Infrastruktur verwenden koennen.
        """

        self._logger = logger

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

        if self._logger is not None:
            self._logger.event("git", "ensure_git_available", "Pruefe Git-CLI im PATH.")
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

    def is_git_repository(self, repo_path: Path) -> bool:
        """
        Prueft ueber die Git-CLI, ob sich ein Pfad innerhalb eines Work-Trees befindet.

        Eingabeparameter:
        - repo_path: Zu pruefender Dateisystempfad.

        Rueckgabewerte:
        - `True`, wenn Git den Pfad als Work-Tree erkennt, sonst `False`.

        Moegliche Fehlerfaelle:
        - Fehlerhafte oder fehlende Git-Umgebung fuehren zu `False`.

        Wichtige interne Logik:
        - Die Methode bleibt fehlertolerant, damit Scans auch bei defekten Repositories weiterlaufen koennen.
        """

        result = self._run_git(repo_path, ["rev-parse", "--is-inside-work-tree"], allow_failure=True).strip().lower()
        return result == "true"

    def get_head_commit_hash(self, repo_path: Path) -> str:
        """
        Liest den aktuellen HEAD-Commit-Hash eines Repositories aus.

        Eingabeparameter:
        - repo_path: Lokaler Repository-Pfad.

        Rueckgabewerte:
        - Vollstaendiger Commit-Hash oder Leerstring bei nicht verfuegbarem HEAD.

        Moegliche Fehlerfaelle:
        - Fehler bei Git-Aufrufen werden defensiv als Leerstring behandelt.

        Wichtige interne Logik:
        - Die Rueckgabe bleibt leer statt mit Platzhalterwerten zu arbeiten, damit Services
          selbst entscheiden koennen, wie sie fehlende Commits darstellen.
        """

        return self._run_git(repo_path, ["rev-parse", "HEAD"], allow_failure=True).strip()

    def get_last_commit_date(self, repo_path: Path) -> str:
        """
        Liest das Datum des letzten Commits im ISO-Format aus.

        Eingabeparameter:
        - repo_path: Lokaler Repository-Pfad.

        Rueckgabewerte:
        - ISO-Zeitstempel des letzten Commits oder Leerstring.

        Moegliche Fehlerfaelle:
        - Git-Fehler liefern defensiv einen Leerstring.

        Wichtige interne Logik:
        - Verwendet `%cI`, damit Datum und Zeitzone fuer die State-Datenbank stabil bleiben.
        """

        return self._run_git(repo_path, ["log", "-1", "--pretty=format:%cI"], allow_failure=True).strip()

    def get_remote_names(self, repo_path: Path) -> list[str]:
        """
        Liest alle konfigurierten Remote-Namen eines Repositories aus.

        Eingabeparameter:
        - repo_path: Lokaler Repository-Pfad.

        Rueckgabewerte:
        - Liste der konfigurierten Remote-Namen.

        Moegliche Fehlerfaelle:
        - Git-Fehler fuehren zu einer leeren Liste.

        Wichtige interne Logik:
        - Die Methode kapselt die einfache Listenlogik, damit hoehere Services keine CLI-Details kennen muessen.
        """

        output = self._run_git(repo_path, ["remote"], allow_failure=True)
        return [line.strip() for line in output.splitlines() if line.strip()]

    def get_remote_url(self, repo_path: Path, remote_name: str = "origin") -> str:
        """
        Liest die URL eines konfigurierten Remotes aus.

        Eingabeparameter:
        - repo_path: Lokaler Repository-Pfad.
        - remote_name: Name des Ziel-Remotes, standardmaessig `origin`.

        Rueckgabewerte:
        - Remote-URL oder Leerstring, wenn kein Remote vorhanden ist.

        Moegliche Fehlerfaelle:
        - Git-Fehler werden defensiv als Leerstring behandelt.

        Wichtige interne Logik:
        - Die Methode wird sowohl fuer Scans als auch fuer Reparaturaktionen genutzt.
        """

        return self._run_git(repo_path, ["remote", "get-url", remote_name], allow_failure=True).strip()

    def get_status_porcelain(self, repo_path: Path) -> list[str]:
        """
        Liest den kompakten Git-Status fuer Aenderungs- und Tracking-Pruefungen aus.

        Eingabeparameter:
        - repo_path: Lokaler Repository-Pfad.

        Rueckgabewerte:
        - Liste der Zeilen aus `git status --porcelain`.

        Moegliche Fehlerfaelle:
        - Git-Fehler fuehren zu einer leeren Liste.

        Wichtige interne Logik:
        - Das rohe Porzellanformat bleibt erhalten, damit Services unterschiedliche
          Auswertungen darauf aufbauen koennen.
        """

        return self._run_git(repo_path, ["status", "--porcelain"], allow_failure=True).splitlines()

    def get_ahead_behind_counts(
        self,
        repo_path: Path,
        branch_name: str,
        remote_name: str = "origin",
    ) -> tuple[int, int, bool]:
        """
        Liest Ahead-/Behind-Werte gegen den vermuteten Upstream des aktuellen Branches aus.

        Eingabeparameter:
        - repo_path: Lokaler Repository-Pfad.
        - branch_name: Aktueller lokaler Branch.
        - remote_name: Name des zu pruefenden Remotes, standardmaessig `origin`.

        Rueckgabewerte:
        - Tupel aus Ahead-Anzahl, Behind-Anzahl und Diverged-Flag.

        Moegliche Fehlerfaelle:
        - Fehlender Upstream oder Git-Fehler liefern defensiv `(0, 0, False)`.

        Wichtige interne Logik:
        - Die Methode wird nur im Tiefenscan genutzt und bleibt daher bewusst fehlertolerant,
          damit Repositories ohne Upstream die Scan-Pipeline nicht blockieren.
        """

        if not branch_name or branch_name == "-":
            return 0, 0, False
        upstream_ref = f"{remote_name}/{branch_name}"
        output = self._run_git(
            repo_path,
            ["rev-list", "--left-right", "--count", f"{upstream_ref}...HEAD"],
            allow_failure=True,
        ).strip()
        if not output:
            return 0, 0, False
        parts = output.split()
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            return 0, 0, False
        behind_count = int(parts[0])
        ahead_count = int(parts[1])
        return ahead_count, behind_count, ahead_count > 0 and behind_count > 0

    def list_tracked_files(self, repo_path: Path) -> list[str]:
        """
        Listet alle von Git verfolgten Dateien eines Repositories auf.

        Eingabeparameter:
        - repo_path: Lokaler Repository-Pfad.

        Rueckgabewerte:
        - Liste relativer Dateipfade.

        Moegliche Fehlerfaelle:
        - Git-Fehler fuehren zu einer leeren Liste.

        Wichtige interne Logik:
        - Die Methode dient dem State-Dateiindex und kapselt das konkrete CLI-Kommando.
        """

        return [line.strip() for line in self._run_git(repo_path, ["ls-files"], allow_failure=True).splitlines() if line.strip()]

    def list_ignored_paths(self, repo_path: Path) -> list[str]:
        """
        Listet von Git ignorierte Dateien und Verzeichnisse eines Repositories auf.

        Eingabeparameter:
        - repo_path: Lokaler Repository-Pfad.

        Rueckgabewerte:
        - Liste relativer Pfade aus Git-Sicht.

        Moegliche Fehlerfaelle:
        - Git-Fehler fuehren zu einer leeren Liste.

        Wichtige interne Logik:
        - Nutzt `--directory`, damit ganze ignorierte Verzeichnisse kompakt erkannt werden.
        """

        return [
            line.strip()
            for line in self._run_git(
                repo_path,
                ["ls-files", "--others", "-i", "--exclude-standard", "--directory"],
                allow_failure=True,
            ).splitlines()
            if line.strip()
        ]

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
            if self._logger is not None:
                self._logger.event(
                    "git",
                    "clone_repository",
                    f"clone_url={clone_url} | target_path={target_path}",
                )
            subprocess.run(
                ["git", "clone", clone_url, str(target_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            if self._logger is not None:
                self._logger.error(f"Git-Clone fehlgeschlagen fuer '{clone_url}' nach '{target_path}': {error}")
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

    def remove_remote_origin(self, repo_path: Path) -> None:
        """
        Entfernt den `origin`-Remote eines lokalen Repositories.

        Eingabeparameter:
        - repo_path: Ziel-Repository fuer das Entfernen des Remotes.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git lehnt das Entfernen ab.

        Wichtige interne Logik:
        - Das Entfernen wird nur versucht, wenn `origin` aktuell existiert.
        """

        current_origin = self.get_remote_url(repo_path, "origin")
        if current_origin:
            self._run_git(repo_path, ["remote", "remove", "origin"])

    def initialize_repository(self, repo_path: Path) -> None:
        """
        Initialisiert einen Ordner neu als Git-Repository.

        Eingabeparameter:
        - repo_path: Zielpfad fuer `git init`.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Git-Initialisierung schlaegt fehl.

        Wichtige interne Logik:
        - Die Methode wird nur fuer explizite Reparaturpfade verwendet und fuehrt
          keine weiteren Seiteneffekte wie Initial-Commits aus.
        """

        self._run_git(repo_path, ["init"])

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

        if self._logger is not None:
            self._logger.event(
                "git",
                "run_command",
                f"repo_path={repo_path} | args={' '.join(arguments)} | allow_failure={allow_failure}",
            )
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
            if self._logger is not None:
                stdout_preview = completed.stdout.strip().replace("\n", " | ")
                stderr_preview = completed.stderr.strip().replace("\n", " | ")
                details = f"stdout={stdout_preview[:240]!r}"
                if stderr_preview:
                    details = f"{details} | stderr={stderr_preview[:240]!r}"
                self._logger.event("git", "command_success", details)
            return completed.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            if self._logger is not None:
                if allow_failure:
                    self._logger.event(
                        "git",
                        "command_expected_failure",
                        f"repo_path={repo_path} | args={' '.join(arguments)} | error={error}",
                    )
                else:
                    self._logger.warning(
                        f"Git-Kommando fehlgeschlagen fuer '{repo_path}' mit args={' '.join(arguments)}: {error}"
                    )
            if allow_failure:
                return ""
            raise IGittyError(f"Git-Abfrage fuer '{repo_path}' fehlgeschlagen: {error}") from error
