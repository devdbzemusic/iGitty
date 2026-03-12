"""Dialog fuer die Erstellung neuer GitHub-Repositories beim Push."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout


class CreateRemoteDialog(QDialog):
    """Fragt Sichtbarkeit und Beschreibung fuer neue Remotes ab."""

    def __init__(self, repo_name: str, initial_private: bool = False, parent=None) -> None:
        """
        Baut den Dialog mit vorausgefuelltem Repository-Namen auf.

        Eingabeparameter:
        - repo_name: Name des lokalen Repositories.
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Name ist bewusst read-only, weil im MVP lokal und remote synchron bleiben sollen.
        """

        super().__init__(parent)
        self.setWindowTitle("Remote-Repository anlegen")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Repository-Name"))
        self._name_edit = QLineEdit(repo_name)
        self._name_edit.setReadOnly(True)
        self._private_checkbox = QCheckBox("Privates Repository erstellen")
        self._private_checkbox.setChecked(initial_private)
        self._description_edit = QLineEdit()
        self._description_edit.setPlaceholderText("Optionale Beschreibung")
        layout.addWidget(self._name_edit)
        layout.addWidget(self._private_checkbox)
        layout.addWidget(QLabel("Beschreibung"))
        layout.addWidget(self._description_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> tuple[bool, str]:
        """
        Liefert Sichtbarkeit und Beschreibung des neuen Remotes.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Tupel aus Private-Flag und Beschreibung.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Rueckgabe ist auf die fuer `GitHubService.create_repository` benoetigten Felder begrenzt.
        """

        return self._private_checkbox.isChecked(), self._description_edit.text().strip()
