"""Einfacher Kontextdialog fuer den Eintritt in RepoViewer Teil 2."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QTextEdit, QVBoxLayout

from models.view_models import RepoContext


class RepoContextDialog(QDialog):
    """Zeigt einen zusammengefuehrten Repo-Kontext ohne Dateibaum oder Editor an."""

    def __init__(self, context: RepoContext, parent=None) -> None:
        """
        Baut den Kontextdialog fuer ein einzelnes Repository auf.

        Eingabeparameter:
        - context: Bereits zusammengefuehrter RepoContext.
        - parent: Optionales Eltern-Widget.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine in der UI-Erstellung.

        Wichtige interne Logik:
        - Der Dialog bleibt bewusst ein reiner Informationscontainer als Eintrittsschicht fuer Teil 2.
        """

        super().__init__(parent)
        self.setWindowTitle(f"Repo-Kontext | {context.repo_name}")
        self.resize(820, 620)
        root_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.addRow("Name", QLabel(context.repo_name or "-"))
        form_layout.addRow("Full Name", QLabel(context.repo_full_name or "-"))
        form_layout.addRow("Source Type", QLabel(context.source_type or "-"))
        form_layout.addRow("Remote Repo ID", QLabel(str(context.remote_repo_id or "-")))
        form_layout.addRow("Local Path", QLabel(context.local_path or "-"))
        form_layout.addRow("Remote URL", QLabel(context.remote_url or "-"))
        form_layout.addRow("Clone URL", QLabel(context.clone_url or "-"))
        form_layout.addRow("Current Branch", QLabel(context.current_branch or "-"))
        form_layout.addRow("Default Branch", QLabel(context.default_branch or "-"))
        form_layout.addRow("Public/Private", QLabel(context.remote_visibility or "-"))
        form_layout.addRow("Has Remote", QLabel("Ja" if context.has_remote else "Nein"))
        form_layout.addRow("Has Local Clone", QLabel("Ja" if context.has_local_clone else "Nein"))
        form_layout.addRow("Archived / Fork", QLabel(f"{'Ja' if context.archived else 'Nein'} / {'Ja' if context.fork else 'Nein'}"))
        form_layout.addRow("Languages", QLabel(context.languages or "-"))
        form_layout.addRow("Contributors", QLabel(context.contributors_summary or "-"))
        form_layout.addRow(
            "Letzte Aktion",
            QLabel(
                f"{context.last_action_type or '-'} | {context.last_action_status or '-'} | {context.last_action_timestamp or '-'}"
            ),
        )
        form_layout.addRow("Struktur-Vault", QLabel("Ja" if context.has_struct_vault_data else "Nein"))
        form_layout.addRow("Struktur-Eintraege", QLabel(str(context.struct_item_count)))
        form_layout.addRow("Letzter Struktur-Scan", QLabel(context.last_struct_scan_timestamp or "-"))
        root_layout.addLayout(form_layout)

        description_box = QTextEdit()
        description_box.setReadOnly(True)
        description_box.setPlainText(context.description or "")
        root_layout.addWidget(QLabel("Beschreibung"))
        root_layout.addWidget(description_box, stretch=1)

        diagnostics_box = QTextEdit()
        diagnostics_box.setReadOnly(True)
        diagnostics_box.setPlainText("\n".join(context.diagnostic_events) if context.diagnostic_events else "Keine State-Diagnoseereignisse vorhanden.")
        root_layout.addWidget(QLabel("Diagnose"))
        root_layout.addWidget(diagnostics_box, stretch=1)
