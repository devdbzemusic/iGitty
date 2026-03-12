"""GitHub-REST-API-Zugriff fuer Remote-Repository-Daten."""

from __future__ import annotations

from datetime import datetime, timezone
import re

import requests

from core.env import EnvSettings
from core.exceptions import ConfigurationError, GitHubApiError
from models.repo_models import RateLimitInfo, RemoteRepo


class GitHubService:
    """Laedt und transformiert Remote-Repository-Daten aus der GitHub-API."""

    def __init__(self, env_settings: EnvSettings, timeout_seconds: int = 20) -> None:
        """
        Bereitet eine Session fuer spaetere GitHub-Anfragen vor.

        Eingabeparameter:
        - env_settings: Umgebungswerte mit Access Token.
        - timeout_seconds: Maximale Wartezeit pro HTTP-Anfrage.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehlendes Access Token wird erst beim ersten fachlichen Zugriff beanstandet.

        Wichtige interne Logik:
        - Die Session kapselt die Authentifizierung, damit Controller und Worker davon getrennt bleiben.
        """

        self._env_settings = env_settings
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def fetch_remote_repositories(self) -> tuple[list[RemoteRepo], RateLimitInfo]:
        """
        Laedt alle Remote-Repositories des authentifizierten Accounts per Pagination.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Tupel aus Liste der geladenen Repositories und Rate-Limit-Informationen.

        Moegliche Fehlerfaelle:
        - Fehlendes Access Token.
        - Netzwerkfehler oder ungueltige GitHub-Antworten.
        - Abgewiesene Authentifizierung.

        Wichtige interne Logik:
        - Verwendet die GitHub-Endpoint-Pagination mit `page` und `per_page=100`.
        - Transformiert jede API-Antwort sofort in das interne Datamodell.
        """

        if not self._env_settings.github_access_token:
            raise ConfigurationError("GITHUB_ACCESS_TOKEN ist nicht gesetzt.")

        self._session.headers["Authorization"] = f"Bearer {self._env_settings.github_access_token}"

        repositories: list[RemoteRepo] = []
        page = 1
        rate_limit = RateLimitInfo()

        while True:
            response = self._session.get(
                "https://api.github.com/user/repos",
                params={
                    "affiliation": "owner,collaborator,organization_member",
                    "page": page,
                    "per_page": 100,
                    "sort": "updated",
                },
                timeout=self._timeout_seconds,
            )
            rate_limit = self._extract_rate_limit(response)

            if response.status_code >= 400:
                error_payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                message = error_payload.get("message", "Unbekannter GitHub-Fehler")
                raise GitHubApiError(f"GitHub API Fehler {response.status_code}: {message}")

            payload = response.json()
            if not payload:
                break

            repositories.extend(self._map_remote_repo(item) for item in payload)

            if len(payload) < 100:
                break
            page += 1

        return repositories, rate_limit

    def create_repository(self, name: str, private: bool, description: str) -> RemoteRepo:
        """
        Erstellt ein neues GitHub-Repository fuer den authentifizierten Benutzer.

        Eingabeparameter:
        - name: Gewuenschter Repository-Name.
        - private: Sichtbarkeit des neuen Repositories.
        - description: Optionale Beschreibung.

        Rueckgabewerte:
        - Das neu erzeugte Repository im internen Datamodell.

        Moegliche Fehlerfaelle:
        - Fehlendes Access Token.
        - GitHub lehnt die Erstellung ab.

        Wichtige interne Logik:
        - Nutzt den Benutzer-Endpoint `/user/repos`, damit kein zusaetzlicher Owner-Dialog noetig ist.
        """

        self._ensure_authorization()
        response = self._session.post(
            "https://api.github.com/user/repos",
            json={
                "name": name,
                "private": private,
                "description": description,
                "auto_init": False,
            },
            timeout=self._timeout_seconds,
        )
        if response.status_code >= 400:
            message = response.json().get("message", "Repository konnte nicht erstellt werden")
            raise GitHubApiError(f"GitHub API Fehler {response.status_code}: {message}")
        return self._map_remote_repo(response.json())

    def delete_repository(self, owner: str, name: str) -> None:
        """
        Loescht ein GitHub-Repository ueber die REST-API.

        Eingabeparameter:
        - owner: GitHub-Owner des Ziel-Repositories.
        - name: Repository-Name.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehlendes Access Token.
        - GitHub lehnt den Delete-Aufruf ab.

        Wichtige interne Logik:
        - Die Methode loescht nur remote und erwartet, dass die Sicherheitspruefung bereits extern stattgefunden hat.
        """

        self._ensure_authorization()
        response = self._session.delete(
            f"https://api.github.com/repos/{owner}/{name}",
            timeout=self._timeout_seconds,
        )
        if response.status_code >= 400:
            message = response.json().get("message", "Repository konnte nicht geloescht werden")
            raise GitHubApiError(f"GitHub API Fehler {response.status_code}: {message}")

    def resolve_remote_metadata(self, remote_url: str) -> tuple[str, int]:
        """
        Ermittelt Sichtbarkeit und Repository-ID fuer eine bekannte GitHub-Remote-URL.

        Eingabeparameter:
        - remote_url: HTTPS- oder SSH-Remote eines GitHub-Repositories.

        Rueckgabewerte:
        - Tupel aus Sichtbarkeit (`public`, `private`, `unknown`) und Repository-ID.

        Moegliche Fehlerfaelle:
        - Fehlendes Access Token.
        - Unerwartete API-Fehler.

        Wichtige interne Logik:
        - Nicht-GitHub-URLs werden defensiv als `unknown` behandelt.
        """

        owner_repo = self._parse_github_remote(remote_url)
        if owner_repo is None:
            return "unknown", 0

        owner, name = owner_repo
        self._ensure_authorization()
        response = self._session.get(
            f"https://api.github.com/repos/{owner}/{name}",
            timeout=self._timeout_seconds,
        )
        if response.status_code >= 400:
            return "unknown", 0

        payload = response.json()
        visibility = payload.get("visibility")
        if not visibility:
            visibility = "private" if payload.get("private") else "public"
        return str(visibility), int(payload.get("id", 0))

    def _extract_rate_limit(self, response: requests.Response) -> RateLimitInfo:
        """
        Liest die relevanten Rate-Limit-Header aus einer GitHub-Antwort aus.

        Eingabeparameter:
        - response: HTTP-Antwort der GitHub-API.

        Rueckgabewerte:
        - Befuellte RateLimitInfo-Instanz.

        Moegliche Fehlerfaelle:
        - Fehlende Headerwerte werden defensiv als `0` oder `-` behandelt.

        Wichtige interne Logik:
        - Wandelt den Reset-Zeitstempel in eine lesbare UTC-Anzeige um.
        """

        reset_value = response.headers.get("X-RateLimit-Reset", "0")
        reset_display = "-"
        if reset_value.isdigit() and int(reset_value) > 0:
            reset_display = datetime.fromtimestamp(int(reset_value), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return RateLimitInfo(
            limit=int(response.headers.get("X-RateLimit-Limit", "0")),
            remaining=int(response.headers.get("X-RateLimit-Remaining", "0")),
            reset_at=reset_display,
        )

    def _ensure_authorization(self) -> None:
        """
        Stellt sicher, dass die Session einen gueltigen Bearer-Token gesetzt hat.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - `GITHUB_ACCESS_TOKEN` ist nicht gesetzt.

        Wichtige interne Logik:
        - Zentralisiert die Auth-Initialisierung fuer mehrere API-Methoden.
        """

        if not self._env_settings.github_access_token:
            raise ConfigurationError("GITHUB_ACCESS_TOKEN ist nicht gesetzt.")
        self._session.headers["Authorization"] = f"Bearer {self._env_settings.github_access_token}"

    def _map_remote_repo(self, item: dict) -> RemoteRepo:
        """
        Transformiert ein GitHub-Repository-JSON in das interne Datamodell.

        Eingabeparameter:
        - item: Einzelnes Repository-Objekt aus der API.

        Rueckgabewerte:
        - RemoteRepo-Instanz fuer UI und weitere Verarbeitung.

        Moegliche Fehlerfaelle:
        - Fehlende Felder werden mit robusten Defaults behandelt.

        Wichtige interne Logik:
        - Reduziert das API-Modell auf die fuer den MVP direkt benoetigten Felder.
        """

        visibility = "private" if item.get("private") else "public"
        owner = (item.get("owner") or {}).get("login", "")
        return RemoteRepo(
            repo_id=item.get("id", 0),
            name=item.get("name", ""),
            full_name=item.get("full_name", ""),
            owner=owner,
            visibility=visibility,
            default_branch=item.get("default_branch", ""),
            language=item.get("language") or "-",
            archived=bool(item.get("archived", False)),
            fork=bool(item.get("fork", False)),
            clone_url=item.get("clone_url", ""),
            ssh_url=item.get("ssh_url", ""),
            html_url=item.get("html_url", ""),
            description=item.get("description") or "",
            topics=list(item.get("topics") or []),
            contributors_count=None,
            updated_at=item.get("updated_at", ""),
        )

    def _parse_github_remote(self, remote_url: str) -> tuple[str, str] | None:
        """
        Zerlegt eine GitHub-Remote-URL in Owner und Repository-Namen.

        Eingabeparameter:
        - remote_url: HTTPS- oder SSH-Remote eines GitHub-Repositories.

        Rueckgabewerte:
        - Tupel aus Owner und Repository-Name oder `None`, wenn keine GitHub-URL erkannt wurde.

        Moegliche Fehlerfaelle:
        - Keine; nicht passende URLs liefern `None`.

        Wichtige interne Logik:
        - Unterstuetzt die in Windows- und GitHub-Workflows typischen HTTPS- und SSH-Formate.
        """

        patterns = [
            r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
            r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        ]
        for pattern in patterns:
            match = re.match(pattern, remote_url.strip())
            if match:
                return match.group("owner"), match.group("repo")
        return None
