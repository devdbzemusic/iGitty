"""Hilfsfunktionen zum Maskieren sensibler Informationen."""

from __future__ import annotations


def mask_secret(value: str, visible_prefix: int = 4, visible_suffix: int = 2) -> str:
    """
    Maskiert einen geheimen String fuer Logs oder UI-Ausgaben.

    Eingabeparameter:
    - value: Zu maskierender Klartext.
    - visible_prefix: Anzahl sichtbarer Zeichen am Anfang.
    - visible_suffix: Anzahl sichtbarer Zeichen am Ende.

    Rueckgabewerte:
    - Maskierte Darstellung des Geheimnisses.

    Moegliche Fehlerfaelle:
    - Keine funktionalen Fehler; leere Werte werden als Platzhalter behandelt.

    Wichtige interne Logik:
    - Sehr kurze Werte werden komplett ersetzt, um versehentliche Leaks zu vermeiden.
    """

    if not value:
        return "<leer>"
    if len(value) <= visible_prefix + visible_suffix:
        return "*" * len(value)
    return f"{value[:visible_prefix]}{'*' * (len(value) - visible_prefix - visible_suffix)}{value[-visible_suffix:]}"
