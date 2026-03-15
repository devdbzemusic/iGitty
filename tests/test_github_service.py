"""Tests fuer die GitHub-Metadatenabbildung im Remote-Modell."""

from __future__ import annotations

from core.env import EnvSettings
from services.github_service import GitHubService


class _DummyResponse:
    """Kleines Testobjekt fuer GitHub-HTTP-Antworten ohne echte Netzwerkaufrufe."""

    def __init__(self, status_code: int, payload, headers: dict[str, str] | None = None) -> None:
        """
        Speichert Status, Payload und Header fuer spaetere Testauswertung.
        """

        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {"content-type": "application/json"}

    def json(self):
        """
        Liefert die vorbereitete JSON-Payload zurueck.
        """

        return self._payload


class _DummySession:
    """Minimale Session-Attrappe fuer deterministische GitHub-Service-Tests."""

    def __init__(self, responses: list[_DummyResponse]) -> None:
        """
        Speichert eine feste Reihenfolge von Antworten fuer aufeinanderfolgende GET-Aufrufe.
        """

        self.headers: dict[str, str] = {}
        self._responses = responses
        self.patched_requests: list[tuple[str, dict]] = []

    def get(self, url: str, params=None, timeout: int = 0):  # noqa: ANN001
        """
        Liefert die naechste vorbereitete Antwort unabhaengig von URL oder Parametern.
        """

        return self._responses.pop(0)

    def patch(self, url: str, json=None, timeout: int = 0):  # noqa: ANN001
        """
        Liefert die naechste vorbereitete Antwort fuer PATCH-Aufrufe und merkt sich die Nutzlast.
        """

        self.patched_requests.append((url, json or {}))
        return self._responses.pop(0)


def test_map_remote_repo_includes_extended_metadata() -> None:
    """
    Prueft, dass das Remote-Modell die erweiterten Basisfelder aus der API uebernimmt.
    """

    service = GitHubService(EnvSettings(github_access_token="", github_app_client_id="", repo_dir=None))

    repository = service._map_remote_repo(  # noqa: SLF001
        {
            "id": 7,
            "name": "demo",
            "full_name": "dbzs/demo",
            "owner": {"login": "dbzs"},
            "private": False,
            "default_branch": "main",
            "language": "Python",
            "archived": False,
            "fork": False,
            "clone_url": "https://github.com/dbzs/demo.git",
            "ssh_url": "git@github.com:dbzs/demo.git",
            "html_url": "https://github.com/dbzs/demo",
            "description": "Demo Repository",
            "topics": ["tooling", "python"],
            "created_at": "2026-03-01T10:00:00Z",
            "updated_at": "2026-03-10T10:00:00Z",
            "pushed_at": "2026-03-11T10:00:00Z",
            "size": 123,
        }
    )

    assert repository.created_at == "2026-03-01T10:00:00Z"
    assert repository.updated_at == "2026-03-10T10:00:00Z"
    assert repository.pushed_at == "2026-03-11T10:00:00Z"
    assert repository.size == 123
    assert repository.topics == ["tooling", "python"]


def test_fetch_contributors_info_builds_summary_from_api_response() -> None:
    """
    Prueft, dass der Service eine kompakte Contributor-Zusammenfassung erzeugt.
    """

    service = GitHubService(EnvSettings(github_access_token="token", github_app_client_id="", repo_dir=None))
    service._session = _DummySession(  # noqa: SLF001
        [
            _DummyResponse(
                200,
                [{"login": "alice"}, {"login": "bob"}, {"login": "carol"}],
                {
                    "content-type": "application/json",
                    "Link": '<https://api.github.com/repositories/7/contributors?page=2&per_page=3>; rel="next", <https://api.github.com/repositories/7/contributors?page=2&per_page=3>; rel="last"',
                },
            )
        ]
    )

    count, summary = service._fetch_contributors_info({"contributors_url": "https://api.github.com/repos/dbzs/demo/contributors"})  # noqa: SLF001

    assert count == 6
    assert summary == "alice, bob, carol (+3)"


def test_fetch_remote_repositories_updates_authenticated_login() -> None:
    """
    Prueft, dass beim Remote-Laden der authentifizierte GitHub-Login gespeichert wird.
    """

    service = GitHubService(EnvSettings(github_access_token="token", github_app_client_id="", repo_dir=None))
    service._session = _DummySession(  # noqa: SLF001
        [
            _DummyResponse(200, {"login": "devdbzemusic"}),
            _DummyResponse(
                200,
                [
                    {
                        "id": 7,
                        "name": "demo",
                        "full_name": "dbzs/demo",
                        "owner": {"login": "dbzs"},
                        "private": False,
                        "default_branch": "main",
                        "language": "Python",
                        "archived": False,
                        "fork": False,
                        "clone_url": "https://github.com/dbzs/demo.git",
                        "ssh_url": "git@github.com:dbzs/demo.git",
                        "html_url": "https://github.com/dbzs/demo",
                        "description": "Demo",
                        "topics": [],
                        "contributors_url": "https://api.github.com/repos/dbzs/demo/contributors",
                        "updated_at": "2026-03-10T10:00:00Z",
                    }
                ],
                {
                    "content-type": "application/json",
                    "X-RateLimit-Limit": "5000",
                    "X-RateLimit-Remaining": "4999",
                    "X-RateLimit-Reset": "0",
                },
            ),
            _DummyResponse(200, [{"login": "alice"}]),
            _DummyResponse(
                200,
                [],
                {
                    "content-type": "application/json",
                    "X-RateLimit-Limit": "5000",
                    "X-RateLimit-Remaining": "4998",
                    "X-RateLimit-Reset": "0",
                },
            ),
        ]
    )

    repositories, _rate_limit = service.fetch_remote_repositories()

    assert service.last_authenticated_login == "devdbzemusic"
    assert repositories[0].contributors_summary == "alice"


def test_update_repository_visibility_uses_patch_and_maps_updated_repo() -> None:
    """
    Prueft, dass die Sichtbarkeitsaenderung per PATCH an GitHub gesendet und korrekt gemappt wird.
    """

    service = GitHubService(EnvSettings(github_access_token="token", github_app_client_id="", repo_dir=None))
    dummy_session = _DummySession(
        [
            _DummyResponse(
                200,
                {
                    "id": 7,
                    "name": "demo",
                    "full_name": "dbzs/demo",
                    "owner": {"login": "dbzs"},
                    "private": True,
                    "default_branch": "main",
                    "language": "Python",
                    "archived": False,
                    "fork": False,
                    "clone_url": "https://github.com/dbzs/demo.git",
                    "ssh_url": "git@github.com:dbzs/demo.git",
                    "html_url": "https://github.com/dbzs/demo",
                    "description": "Demo",
                    "topics": [],
                },
            )
        ]
    )
    service._session = dummy_session  # noqa: SLF001

    repository = service.update_repository_visibility("dbzs", "demo", private=True)

    assert dummy_session.patched_requests == [
        ("https://api.github.com/repos/dbzs/demo", {"private": True})
    ]
    assert repository.visibility == "private"
    assert repository.full_name == "dbzs/demo"
