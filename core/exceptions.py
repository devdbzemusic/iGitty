"""Eigene Ausnahmearten fuer die Anwendung."""


class IGittyError(Exception):
    """Basisklasse fuer kontrolliert behandelbare Anwendungsfehler."""


class ConfigurationError(IGittyError):
    """Signalisiert fehlerhafte oder unvollstaendige Konfiguration."""


class GitHubApiError(IGittyError):
    """Signalisiert einen fachlich verwertbaren Fehler der GitHub-API."""
