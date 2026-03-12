"""Kleine Hilfsschicht fuer SQLite-Verbindungen."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def sqlite_connection(database_file: Path) -> Iterator[sqlite3.Connection]:
    """
    Oeffnet eine SQLite-Verbindung und kuemmert sich um Commit und Close.

    Eingabeparameter:
    - database_file: Zielpfad der Datenbankdatei.

    Rueckgabewerte:
    - Iterator ueber eine geoeffnete SQLite-Verbindung.

    Moegliche Fehlerfaelle:
    - Nicht erstellbare Datenbankdatei.
    - Ungueltiges SQL in spaeteren Aufrufern.

    Wichtige interne Logik:
    - Aktiviert `Row`-Objekte, damit spaetere Repository-Schichten sprechender arbeiten koennen.
    """

    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
