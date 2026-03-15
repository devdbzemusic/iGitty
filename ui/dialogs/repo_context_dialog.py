"""RepoViewer-Dialog fuer Dashboard, Explorer, Historie und Diagnose."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from models.view_models import RepoContext
from ui.widgets.repo_dashboard_panel import RepoDashboardPanel
from ui.widgets.repo_diagnostics_panel import RepoDiagnosticsPanel
from ui.widgets.repo_explorer_panel import RepoExplorerPanel
from ui.widgets.repo_history_panel import RepoHistoryPanel
from ui.widgets.repository_evolution_panel import RepositoryEvolutionPanel
from ui.widgets.repository_timeline_panel import RepositoryTimelinePanel


class RepoContextDialog(QDialog):
    """Zeigt den zusammengefuehrten RepoViewer-Kontext fuer ein einzelnes Repository an."""

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
        - Der Dialog bleibt bewusst rein lesend und bildet den Phase-II-Einstieg fuer
          Dashboard, Explorer, Historie und Diagnose.
        """

        super().__init__(parent)
        self.setWindowTitle(f"RepoViewer | {context.repo_name}")
        self.resize(1040, 760)
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
        form_layout.addRow("Repository Status", QLabel(context.repository_status or "-"))
        form_layout.addRow("Health / Sync", QLabel(f"{context.health_state or '-'} / {context.sync_state or '-'}"))
        form_layout.addRow("Empfohlene Aktion", QLabel(context.recommended_action or "-"))
        form_layout.addRow("Struktur-Vault", QLabel("Ja" if context.has_struct_vault_data else "Nein"))
        form_layout.addRow("Struktur-Eintraege", QLabel(str(context.struct_item_count)))
        form_layout.addRow("Letzter Struktur-Scan", QLabel(context.last_struct_scan_timestamp or "-"))
        form_layout.addRow("Letzter lokaler Scan", QLabel(context.last_scan_at or "-"))
        form_layout.addRow("Letzter Remote-Check", QLabel(context.last_remote_check_at or "-"))
        root_layout.addLayout(form_layout)

        tabs = QTabWidget()
        root_layout.addWidget(tabs, stretch=1)

        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        description_box = QTextEdit()
        description_box.setReadOnly(True)
        description_box.setPlainText(context.description or "")
        overview_layout.addWidget(QLabel("Beschreibung"))
        overview_layout.addWidget(description_box, stretch=1)

        diagnostics_box = QTextEdit()
        diagnostics_box.setReadOnly(True)
        diagnostics_box.setPlainText("\n".join(context.diagnostic_events) if context.diagnostic_events else "Keine State-Diagnoseereignisse vorhanden.")
        overview_layout.addWidget(QLabel("Diagnose-Kurzansicht"))
        overview_layout.addWidget(diagnostics_box, stretch=1)
        tabs.addTab(overview_tab, "Ueberblick")

        self._dashboard_panel = RepoDashboardPanel()
        self._dashboard_panel.set_context(context)
        tabs.addTab(self._dashboard_panel, "Dashboard")

        self._explorer_panel = RepoExplorerPanel()
        self._explorer_panel.set_items(context.tree_items)
        tabs.addTab(self._explorer_panel, "Repo Explorer")

        self._history_panel = RepoHistoryPanel()
        self._history_panel.set_entries(context.history_entries)
        tabs.addTab(self._history_panel, "Historie")

        self._timeline_panel = RepositoryTimelinePanel()
        self._timeline_panel.set_entries(context.timeline_entries)
        tabs.addTab(self._timeline_panel, "Timeline")

        self._diagnostics_panel = RepoDiagnosticsPanel()
        self._diagnostics_panel.set_status_events(context.status_events)
        self._diagnostics_panel.set_scan_runs(context.recent_scan_runs)
        tabs.addTab(self._diagnostics_panel, "Diagnose")

        self._evolution_panel = RepositoryEvolutionPanel()
        self._evolution_panel.set_analysis(context.evolution_summary, context.snapshot_diffs)
        tabs.addTab(self._evolution_panel, "Evolution")
