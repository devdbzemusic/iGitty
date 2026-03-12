"""Dialog fuer Commit-Nachricht und Staging-Modus."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout


class CommitDialog(QDialog):
    """Fragt Commit-Nachricht und Staging-Modus fuer einen Batch ab."""

    def __init__(self, parent=None) -> None:
        """
        Baut den Commit-Dialog auf.

        Eingabeparameter:
        - parent: Optionales Eltern-Widget fuer den modalen Dialog.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der UI-Erstellung.

        Wichtige interne Logik:
        - Der Dialog liefert nur Benutzereingaben, keine Fachlogik.
        """

        super().__init__(parent)
        self.setWindowTitle("Commit vorbereiten")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Commit-Nachricht"))
        self._message_edit = QLineEdit()
        self._message_edit.setPlaceholderText("Commit Message eingeben")
        self._stage_all_checkbox = QCheckBox("Alle Aenderungen stagen (git add -A)")
        self._stage_all_checkbox.setChecked(True)
        layout.addWidget(self._message_edit)
        layout.addWidget(self._stage_all_checkbox)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> tuple[str, bool]:
        """
        Liefert die im Dialog erfassten Werte in kompakter Form.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Tupel aus Commit-Nachricht und Stage-All-Flag.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Rueckgabe bleibt bewusst simpel, damit Controller direkt damit arbeiten koennen.
        """

        return self._message_edit.text().strip(), self._stage_all_checkbox.isChecked()
