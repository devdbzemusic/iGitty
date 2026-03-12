"""Dialog fuer bestaetigte Remote-Loeschvorgaenge."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout


class DeleteConfirmDialog(QDialog):
    """Verlangt eine harte Textbestaetigung vor dem Remote-Delete."""

    def __init__(self, repo_name: str, local_path_hint: str, parent=None) -> None:
        """
        Baut den Bestaetigungsdialog fuer ein einzelnes Remote-Repository auf.

        Eingabeparameter:
        - repo_name: Zu loeschendes Remote-Repository.
        - local_path_hint: Hinweis auf das lokale Clone-Ziel.
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Dialogtexte betonen absichtlich die Relevanz und den vorhandenen lokalen Sicherungspfad.
        """

        super().__init__(parent)
        self.setWindowTitle("Remote-Repository loeschen")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Remote '{repo_name}' wird nur mit bestaetigtem Text geloescht."))
        layout.addWidget(QLabel(f"Lokaler Clone-Hinweis: {local_path_hint}"))
        layout.addWidget(QLabel("Bitte zur Bestaetigung 'LOESCHEN' eingeben"))
        self._confirm_edit = QLineEdit()
        layout.addWidget(self._confirm_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def is_confirmation_valid(self) -> bool:
        """
        Prueft, ob der geforderte Bestaetigungstext korrekt eingegeben wurde.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - `True` bei exakter Eingabe des Zieltexts.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Pruefung bleibt streng, damit versehentliche Deletes erschwert werden.
        """

        return self._confirm_edit.text().strip() == "LOESCHEN"
