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
        self._last_authenticated_login = ""
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
        self._last_authenticated_login = self._fetch_authenticated_login()

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

            repositories.extend(
                self._map_remote_repo(item, self._fetch_contributors_info(item))
                for item in payload
            )

            if len(payload) < 100:
                break
            page += 1

        return repositories, rate_limit

    @property
    def last_authenticated_login(self) -> str:
        """
        Liefert den zuletzt erfolgreich ermittelten GitHub-Login fuer Statusanzeigen.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Loginname des authentifizierten GitHub-Accounts oder Leerstring.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Daten werden als leerer String dargestellt.

        Wichtige interne Logik:
        - Der Wert wird beim Laden der Remote-Repositories aktualisiert und danach von der UI gelesen.
        """

        return self._last_authenticated_login

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

    def update_repository_visibility(self, owner: str, name: str, private: bool) -> RemoteRepo:
        """
        Aendert die Sichtbarkeit eines bestehenden GitHub-Repositories.

        Eingabeparameter:
        - owner: GitHub-Owner des Ziel-Repositories.
        - name: Repository-Name.
        - private: Zielzustand fuer die GitHub-API; `True` bedeutet privat.

        Rueckgabewerte:
        - Das von GitHub zurueckgelieferte Repository im internen Datamodell.

        Moegliche Fehlerfaelle:
        - Fehlendes Access Token.
        - GitHub lehnt die Sichtbarkeitsaenderung ab.

        Wichtige interne Logik:
        - Die Methode nutzt denselben Repository-Endpoint wie andere Metadatenoperationen,
          aendert aber ausschliesslich das `private`-Flag, damit keine unbeabsichtigten
          Seiteneffekte auf andere Repository-Eigenschaften entstehen.
        """

        self._ensure_authorization()
        response = self._session.patch(
            f"https://api.github.com/repos/{owner}/{name}",
            json={"private": private},
            timeout=self._timeout_seconds,
        )
        if response.status_code >= 400:
            message = response.json().get("message", "Repository-Sichtbarkeit konnte nicht aktualisiert werden")
            raise GitHubApiError(f"GitHub API Fehler {response.status_code}: {message}")
        return self._map_remote_repo(response.json())

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

    def fetch_repository_metadata(self, owner: str, name: str) -> tuple[int, dict]:
        """
        Laedt rohe Metadaten eines GitHub-Repositories ueber Owner und Namen.

        Eingabeparameter:
        - owner: GitHub-Besitzer des Ziel-Repositories.
        - name: Repository-Name ohne `.git`.

        Rueckgabewerte:
        - Tupel aus HTTP-Statuscode und JSON-Payload.

        Moegliche Fehlerfaelle:
        - Fehlendes Access Token.
        - Netzwerkfehler oder ungueltige Antworten.

        Wichtige interne Logik:
        - Die Methode exponiert bewusst den HTTP-Status, damit spezialisierte Services
          zwischen `404`, `200` und temporaren API-Problemen unterscheiden koennen.
        """

        self._ensure_authorization()
        response = self._session.get(
            f"https://api.github.com/repos/{owner}/{name}",
            timeout=self._timeout_seconds,
        )
        payload = {}
        if response.headers.get("content-type", "").startswith("application/json"):
            payload = response.json()
        return response.status_code, payload

    def parse_github_remote(self, remote_url: str) -> tuple[str, str] | None:
        """
        Gibt Owner und Repository-Name fuer eine GitHub-Remote-URL frei.

        Eingabeparameter:
        - remote_url: HTTPS- oder SSH-Remote eines GitHub-Repositories.

        Rueckgabewerte:
        - Tupel aus Owner und Repository-Name oder `None`.

        Moegliche Fehlerfaelle:
        - Keine; unpassende URLs liefern `None`.

        Wichtige interne Logik:
        - Die oeffentliche Methode verhindert, dass andere Services auf private Hilfslogik zugreifen muessen.
        """

        return self._parse_github_remote(remote_url)

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

    def _map_remote_repo(
        self,
        item: dict,
        contributors_info: tuple[int | None, str] | None = None,
    ) -> RemoteRepo:
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
        contributors_count, contributors_summary = contributors_info or (None, "-")
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
            contributors_count=contributors_count,
            contributors_summary=contributors_summary,
            created_at=item.get("created_at", ""),
            updated_at=item.get("updated_at", ""),
            pushed_at=item.get("pushed_at", ""),
            size=int(item.get("size") or 0),
        )

    def _fetch_authenticated_login(self) -> str:
        """
        Ermittelt den Login des aktuell authentifizierten GitHub-Accounts.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - GitHub-Loginname oder Leerstring, wenn die Information nicht ermittelt werden konnte.

        Moegliche Fehlerfaelle:
        - Netzwerk- oder API-Fehler fuehren defensiv zu einem leeren Rueckgabewert.

        Wichtige interne Logik:
        - Der Login wird getrennt vom Repository-Laden geholt, damit der Statusbereich
          einen konkreten Account statt eines generischen Verbunden-Status anzeigen kann.
        """

        try:
            response = self._session.get(
                "https://api.github.com/user",
                timeout=self._timeout_seconds,
            )
        except requests.RequestException:
            return ""
        if response.status_code >= 400:
            return ""
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return str(payload.get("login") or "")

    def _fetch_contributors_info(self, item: dict) -> tuple[int | None, str]:
        """
        Liest eine kompakte Contributor-Zusammenfassung fuer ein Remote-Repository.

        Eingabeparameter:
        - item: Einzelnes Repository-Objekt aus der GitHub-API.

        Rueckgabewerte:
        - Tupel aus Contributor-Anzahl und kurzer Textzusammenfassung.

        Moegliche Fehlerfaelle:
        - Fehlende Berechtigung, API-Fehler oder nicht verfuegbare Daten liefern `None` und `-`.

        Wichtige interne Logik:
        - Die Methode beschraenkt sich auf eine kleine erste Seite mit maximal drei Namen,
          damit der MVP nuetzliche Informationen zeigt ohne das Rate-Limit unnoetig zu belasten.
        """

        contributors_url = str(item.get("contributors_url") or "")
        if not contributors_url:
            return None, "-"

        try:
            response = self._session.get(
                contributors_url,
                params={"per_page": 3, "anon": 1},
                timeout=self._timeout_seconds,
            )
        except requests.RequestException:
            return None, "-"
        if response.status_code >= 400:
            return None, "-"

        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else []
        if not isinstance(payload, list) or not payload:
            return 0, "-"

        names: list[str] = []
        for contributor in payload[:3]:
            if not isinstance(contributor, dict):
                continue
            names.append(
                str(
                    contributor.get("login")
                    or contributor.get("name")
                    or contributor.get("email")
                    or "unbekannt"
                )
            )

        contributors_count = self._extract_total_count_from_link(response.headers.get("Link", ""), fallback_count=len(payload))
        summary = ", ".join(names) if names else "-"
        if contributors_count > len(names):
            summary = f"{summary} (+{contributors_count - len(names)})"
        return contributors_count, summary

    def _extract_total_count_from_link(self, link_header: str, fallback_count: int) -> int:
        """
        Schaetzt die Gesamtanzahl paginierter Elemente aus dem GitHub-Link-Header.

        Eingabeparameter:
        - link_header: Vollstaendiger HTTP-Link-Header der GitHub-API.
        - fallback_count: Fallback-Wert, wenn keine Pagination erkennbar ist.

        Rueckgabewerte:
        - Geschaetzte Gesamtanzahl der Elemente.

        Moegliche Fehlerfaelle:
        - Nicht parsebare Header fallen auf den Fallback zurueck.

        Wichtige interne Logik:
        - GitHub liefert im `last`-Link die letzte Seitennummer; mit `per_page=3`
          laesst sich daraus eine brauchbare Obergrenze fuer die Anzeige ableiten.
        """

        if not link_header:
            return fallback_count
        match = re.search(r"[?&]page=(\d+)[^>]*>; rel=\"last\"", link_header)
        if not match:
            return fallback_count
        last_page = int(match.group(1))
        return max(fallback_count, last_page * 3)

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
