"""Hauptfenster der iGitty-Anwendung."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from models.repo_models import LocalRepo, RemoteRepo
from models.view_models import StatusSnapshot
from ui.dialogs.diagnostics_window import DiagnosticsWindow
from ui.widgets.log_panel_widget import LogPanelWidget
from ui.widgets.path_selector_widget import PathSelectorWidget
from ui.widgets.repo_table_widget import RepoTableWidget
from ui.widgets.status_bar_widget import StatusBarWidget


@dataclass(slots=True)
class RepositoryTableEntry:
    """
    Beschreibt einen einzelnen sichtbaren Eintrag der kombinierten Repository-Tabelle.

    Eingabeparameter:
    - source_type: Herkunft des Eintrags als `local` oder `remote`.
    - repository: Zugehoeriges View-Model aus der bestehenden Local- oder Remote-Liste.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - Keine direkt in der Dataklasse.

    Wichtige interne Logik:
    - Die kombinierte Haupttabelle zeigt genau diese abstrahierten Eintraege an, waehrend
      die bestehenden Controller weiterhin mit ihren spezialisierten Listenmodellen arbeiten.
    """

    source_type: str
    repository: object


class MainWindow(QMainWindow):
    """Stellt das zweispaltige Arbeitsfenster des MVP bereit."""

    refresh_remote_requested = Signal()
    refresh_all_requested = Signal()
    normal_refresh_requested = Signal()
    hard_refresh_requested = Signal()
    refresh_selected_repository_requested = Signal()
    remote_filter_changed = Signal(str)
    scan_local_requested = Signal()
    local_filter_changed = Signal(str)
    target_directory_change_requested = Signal(str)
    clone_requested = Signal()
    commit_requested = Signal()
    push_requested = Signal()
    delete_remote_requested = Signal()
    struct_scan_requested = Signal()
    remote_repo_open_requested = Signal(object, str)
    remote_repo_action_requested = Signal(object, str)
    local_repo_open_requested = Signal(object, str)
    local_repo_action_requested = Signal(object, str)
    local_repo_selected = Signal(object)
    remote_repo_selected = Signal(object)

    def __init__(self) -> None:
        """
        Baut die Grundstruktur des Hauptfensters auf.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine direkten Fehler; UI-Elemente werden rein lokal aufgebaut.

        Wichtige interne Logik:
        - Das Fenster kennt nur Widgets und Signale, aber keine Businesslogik.
        """

        super().__init__()
        self.setWindowTitle("iGitty")
        self.resize(1600, 920)
        self.setObjectName("main_window")

        self._repository_table = RepoTableWidget(
            title="Repository Table",
            columns=[
                "Auswahl",
                "Name",
                "Branch",
                "Sync State",
                "Ahead",
                "Behind",
                "Health",
                "Recommended Action",
                "Last Checked",
            ],
        )
        self._remote_table = RepoTableWidget(
            title="Remote GitHub Repositories",
            columns=[
                "Auswahl",
                "Name",
                "Owner",
                "Local Path",
                "Branch",
                "Sync State",
                "Health",
                "Recommended Action",
                "Visibility",
                "Updated",
            ],
        )
        self._local_table = RepoTableWidget(
            title="Lokale Repositories",
            columns=[
                "Auswahl",
                "Name",
                "Owner",
                "Local Path",
                "Branch",
                "Sync State",
                "Ahead",
                "Behind",
                "Health",
                "Recommended Action",
                "Last Checked",
            ],
        )
        self._path_selector = PathSelectorWidget()
        self._log_panel = LogPanelWidget()
        self._diagnostics_window = DiagnosticsWindow(self)
        self._status_bar_widget = StatusBarWidget()
        self._remote_repositories: list[RemoteRepo] = []
        self._local_repositories: list[LocalRepo] = []
        self._repository_entries: list[RepositoryTableEntry] = []
        self._selected_remote_index: int = -1
        self._selected_local_index: int = -1
        self._selected_repository_index: int = -1
        self._selection_source: str = ""
        self._repository_menu_actions: dict[str, QAction] = {}

        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        """
        Erstellt das Layout des Hauptfensters.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Verwendet Splitter, damit beide Arbeitsbereiche flexibel groessenveraenderbar bleiben.
        """

        central_widget = QWidget()
        central_widget.setObjectName("main_central_widget")
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        self._main_toolbar = self.addToolBar("Hauptaktionen")
        self._main_toolbar.setMovable(False)
        self._toolbar_refresh_all_action = QAction("Alles aktualisieren", self)
        self._toolbar_pull_action = QAction("Pull", self)
        self._toolbar_push_action = QAction("Push", self)
        self._toolbar_commit_action = QAction("Commit", self)
        self._toolbar_clone_action = QAction("Clone", self)
        self._toolbar_publish_action = QAction("Publish", self)
        for action in (
            self._toolbar_refresh_all_action,
            self._toolbar_pull_action,
            self._toolbar_push_action,
            self._toolbar_commit_action,
            self._toolbar_clone_action,
            self._toolbar_publish_action,
        ):
            self._main_toolbar.addAction(action)
        self._main_toolbar.addSeparator()
        target_container = QWidget()
        target_layout = QHBoxLayout(target_container)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addWidget(QLabel("Zielordner"))
        target_layout.addWidget(self._path_selector)
        self._main_toolbar.addWidget(target_container)

        repository_box = QGroupBox("Repositories")
        repository_layout = QVBoxLayout(repository_box)
        repository_layout.addWidget(self._repository_table, stretch=1)

        details_box = QGroupBox("Repository Details")
        details_layout = QVBoxLayout(details_box)
        self._details_panel = LogPanelWidget()
        self._details_panel.set_messages([], "Kein Repository ausgewaehlt.")
        details_layout.addWidget(self._details_panel)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(repository_box)
        main_splitter.addWidget(details_box)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)

        diagnostics_box = QGroupBox("Diagnose")
        self._diagnostics_box = diagnostics_box
        diagnostics_layout = QVBoxLayout(diagnostics_box)
        self._diagnostics_panel = LogPanelWidget()
        self._diagnostics_panel.set_messages([], "Keine Repository-Diagnose vorhanden.")
        diagnostics_layout.addWidget(self._diagnostics_panel)

        history_box = QGroupBox("Job-Historie")
        self._history_box = history_box
        history_layout = QVBoxLayout(history_box)
        self._history_panel = LogPanelWidget()
        self._history_panel.set_messages([], "Keine Job-Historie vorhanden.")
        history_layout.addWidget(self._history_panel)

        log_box = QGroupBox("Logbereich")
        self._log_box = log_box
        log_layout = QVBoxLayout(log_box)
        log_layout.addWidget(self._log_panel)

        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.addWidget(diagnostics_box)
        bottom_splitter.addWidget(history_box)
        bottom_splitter.addWidget(log_box)
        bottom_splitter.setStretchFactor(0, 2)
        bottom_splitter.setStretchFactor(1, 2)
        bottom_splitter.setStretchFactor(2, 2)

        root_layout.addWidget(main_splitter, stretch=3)
        root_layout.addWidget(bottom_splitter, stretch=2)

        self.setCentralWidget(central_widget)
        self.setStatusBar(self._status_bar_widget)
        self._build_menu_bar()

    def _wire_signals(self) -> None:
        """
        Verbindet interne Widget-Signale mit den oeffentlichen Fenstersignalen.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Fenster exponiert nur die Signale, die Controller wirklich benoetigen.
        """

        self._toolbar_refresh_all_action.triggered.connect(self.refresh_all_requested.emit)
        self._toolbar_pull_action.triggered.connect(lambda: self._trigger_repository_action("pull"))
        self._toolbar_push_action.triggered.connect(lambda: self._trigger_repository_action("push"))
        self._toolbar_commit_action.triggered.connect(lambda: self._trigger_repository_action("commit"))
        self._toolbar_clone_action.triggered.connect(lambda: self._trigger_repository_action("clone"))
        self._toolbar_publish_action.triggered.connect(lambda: self._trigger_repository_action("create_remote"))
        self._repository_table.filter_text_changed.connect(self.local_filter_changed.emit)
        self._repository_table.row_activated.connect(self._open_repository_row)
        self._repository_table.row_context_requested.connect(self._show_repository_context_menu)
        self._repository_table.row_selected.connect(self._select_repository_row)
        self._path_selector.browse_requested.connect(self._choose_target_directory)
        self._toolbar_refresh_all_action.setEnabled(True)
        self._toolbar_pull_action.setEnabled(False)
        self._toolbar_push_action.setEnabled(False)
        self._toolbar_commit_action.setEnabled(False)
        self._toolbar_clone_action.setEnabled(False)
        self._toolbar_publish_action.setEnabled(False)
        self._update_repository_menu_actions()

    def _build_menu_bar(self) -> None:
        """
        Baut die zentrale Menueleiste fuer Laden, Synchronisieren, Repository-Aktionen und Diagnose auf.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Menues spiegeln die neue operative Struktur der Anwendung wider und
          aktivieren Repository-Aktionen spaeter dynamisch anhand der aktuellen Selektion.
        """

        menu_bar = self.menuBar()

        datei_menu = menu_bar.addMenu("Datei")
        datei_menu.addAction(self._create_simple_action("GitHub verbinden", self._show_github_connect_hint))
        datei_menu.addAction(self._create_simple_action("Zielordner waehlen", self._choose_target_directory))
        datei_menu.addAction(self._create_simple_action("Einstellungen", self._show_settings_hint))
        datei_menu.addAction(self._create_simple_action("Datenordner oeffnen", self._open_data_directory))
        datei_menu.addAction(self._create_simple_action("Log-Datei oeffnen", self._open_live_log_file))
        datei_menu.addSeparator()
        datei_menu.addAction(self._create_simple_action("Beenden", self.close))

        sync_menu = menu_bar.addMenu("Synchronisieren")
        sync_menu.addAction(self._create_simple_action("Remote-Repositories laden", self.refresh_remote_requested.emit))
        sync_menu.addAction(self._create_simple_action("Lokale Repositories scannen", self.scan_local_requested.emit))
        sync_menu.addAction(self._create_simple_action("Alles aktualisieren", self.refresh_all_requested.emit))
        sync_menu.addSeparator()
        sync_menu.addAction(self._create_simple_action("Normal Refresh", self.normal_refresh_requested.emit))
        sync_menu.addAction(self._create_simple_action("Hard Refresh", self.hard_refresh_requested.emit))
        sync_menu.addAction(
            self._create_simple_action(
                "Ausgewaehltes Repository aktualisieren",
                self.refresh_selected_repository_requested.emit,
            )
        )

        repository_menu = menu_bar.addMenu("Repository")
        for action_id in (
            "open_repository",
            "show_in_explorer",
            "pull",
            "push",
            "commit",
            "clone",
            "create_remote",
            "repair_remote",
            "remove_remote",
            "reinitialize_repository",
            "resolve_divergence",
        ):
            action = QAction(self._action_label(action_id), self)
            action.triggered.connect(lambda _checked=False, current_action_id=action_id: self._trigger_repository_action(current_action_id))
            action.setEnabled(False)
            repository_menu.addAction(action)
            self._repository_menu_actions[action_id] = action

        analyse_menu = menu_bar.addMenu("Analyse")
        for action_id in ("open_repo_explorer", "show_history", "show_diagnostics"):
            action = QAction(self._action_label(action_id), self)
            action.triggered.connect(lambda _checked=False, current_action_id=action_id: self._trigger_repository_action(current_action_id))
            action.setEnabled(False)
            analyse_menu.addAction(action)
            self._repository_menu_actions[action_id] = action
        analyse_menu.addSeparator()
        analyse_menu.addAction(self._create_simple_action("Struktur-Scan starten", self.struct_scan_requested.emit))
        analyse_menu.addAction(self._create_simple_action("Status neu berechnen", self.normal_refresh_requested.emit))

        ansicht_menu = menu_bar.addMenu("Ansicht")
        ansicht_menu.addAction(self._create_simple_action("Diagnosebereich anzeigen", self._toggle_diagnostics_panel_visibility))
        ansicht_menu.addAction(self._create_simple_action("Job-Historie anzeigen", self._toggle_history_panel_visibility))
        ansicht_menu.addAction(self._create_simple_action("Logbereich anzeigen", self._toggle_log_panel_visibility))
        ansicht_menu.addAction(self._create_simple_action("Repo Explorer anzeigen", lambda: self._trigger_repository_action("open_repo_explorer")))
        ansicht_menu.addAction(self._create_simple_action("Spalten konfigurieren", self._show_column_configuration_hint))
        ansicht_menu.addAction(self._create_simple_action("Filter zuruecksetzen", self._reset_filters))

        hilfe_menu = menu_bar.addMenu("Hilfe")
        hilfe_menu.addAction(self._create_simple_action("Ueber iGitty", self._show_about_dialog))
        hilfe_menu.addAction(self._create_simple_action("README oeffnen", self._open_readme_file))
        hilfe_menu.addAction(self._create_simple_action("Entwicklerdokumentation", self._open_developer_documentation))

    def _create_simple_action(self, label: str, callback=None) -> QAction:
        """
        Erzeugt eine einfache Menu-Aktion mit optionalem Callback.

        Eingabeparameter:
        - label: Sichtbarer Menueeintrag.
        - callback: Optionaler Aufruf bei Aktivierung.

        Rueckgabewerte:
        - Vollstaendig vorbereitete QAction.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Hilfsmethode haelt den Menueaufbau kompakt und lesbar.
        """

        action = QAction(label, self)
        if callback is not None:
            action.triggered.connect(lambda _checked=False, current_callback=callback: current_callback())
        return action

    def _action_label(self, action_id: str) -> str:
        """
        Liefert die sichtbare UI-Bezeichnung fuer eine technische Repository-Aktion.

        Eingabeparameter:
        - action_id: Technische Aktions-ID wie `push` oder `show_diagnostics`.

        Rueckgabewerte:
        - Sichtbares Label fuer Menue und Kontextmenue.

        Moegliche Fehlerfaelle:
        - Unbekannte Aktionen liefern ihre ID zurueck.

        Wichtige interne Logik:
        - Die Labels bleiben an einer Stelle gebuendelt, damit Menue und Kontextmenue
          dieselbe Sprache sprechen wie der zentrale Action-Resolver.
        """

        labels = {
            "open_repository": "Oeffnen",
            "show_in_explorer": "Im Explorer anzeigen",
            "clone": "Klonen",
            "pull": "Pull",
            "push": "Push",
            "commit": "Commit",
            "review_changes": "Aenderungen pruefen",
            "stash_changes": "Aenderungen sichern",
            "create_remote": "Publish",
            "repair_remote": "Remote reparieren",
            "remove_remote": "Remote entfernen",
            "reinitialize_repository": "Repository neu initialisieren",
            "resolve_divergence": "Divergenz aufloesen",
            "open_repo_explorer": "Repo Explorer oeffnen",
            "show_history": "Verlauf anzeigen",
            "show_diagnostics": "Diagnose anzeigen",
            "set_private": "Auf private setzen",
            "set_public": "Auf public setzen",
            "refresh_repository": "Repository aktualisieren",
            "rescan": "Pfad pruefen",
        }
        return labels.get(action_id, action_id)

    def _toggle_diagnostics_panel_visibility(self) -> None:
        """
        Blendet den eingebetteten Diagnosebereich der Hauptansicht ein oder aus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Hauptansicht behaelt eine schnelle Inline-Diagnose, waehrend das separate
          Diagnosefenster weiterhin fuer die tieferen Laufzeitdetails existiert.
        """

        self._diagnostics_box.setVisible(not self._diagnostics_box.isVisible())

    def _toggle_history_panel_visibility(self) -> None:
        """
        Blendet den eingebetteten Job-Historienbereich der Hauptansicht ein oder aus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Methode trennt Historie und Diagnose sauber, ohne die gesamte untere
          Panel-Zone der Anwendung verstecken zu muessen.
        """

        self._history_box.setVisible(not self._history_box.isVisible())

    def _toggle_log_panel_visibility(self) -> None:
        """
        Blendet das Logpanel im Hauptfenster ein oder aus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Ansicht bleibt rein UI-seitig und veraendert keine Laufzeitdaten.
        """

        self._log_box.setVisible(not self._log_box.isVisible())

    def _reset_filters(self) -> None:
        """
        Setzt die Tabellenfilter der Hauptansicht auf leer zurueck.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Methode kapselt den Reset fuer Menues und spaetere Toolbar-Aktionen.
        """

        self._repository_table.apply_filter("")
        self.set_remote_filter_text("")
        self.set_local_filter_text("")

    def _show_github_connect_hint(self) -> None:
        """
        Zeigt einen sicheren Hinweis zur GitHub-Verbindung an, ohne sofort eine riskante Aktion auszufuehren.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Menueaktion bleibt bewusst informativ, weil Zugangsdaten in iGitty ueber
          Umgebungsvariablen und bestehende Ladepfade gesteuert werden.
        """

        QMessageBox.information(
            self,
            "GitHub verbinden",
            (
                "iGitty verwendet die bestehende GitHub-Konfiguration aus der Umgebung.\n\n"
                "Pruefe bei Bedarf `GITHUB_ACCESS_TOKEN` und lade danach die Remote-Repositories neu."
            ),
        )

    def _show_settings_hint(self) -> None:
        """
        Zeigt einen sicheren Platzhalter fuer spaetere Anwendungseinstellungen an.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Redesign fuehrt den Menuepunkt bereits sichtbar ein, ohne eine zweite
          Konfigurationslogik ausserhalb der bestehenden Architektur zu erfinden.
        """

        QMessageBox.information(
            self,
            "Einstellungen",
            "Ein separater Einstellungsdialog ist vorbereitet, aber in diesem Stand noch nicht implementiert.",
        )

    def _show_column_configuration_hint(self) -> None:
        """
        Informiert ueber die geplante Spaltenkonfiguration der Haupttabelle.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Menuepunkt ist bereits Teil der neuen Struktur, bleibt aber bewusst
          folgenlos, bis eine persistente Spaltenkonfiguration vorhanden ist.
        """

        QMessageBox.information(
            self,
            "Spalten konfigurieren",
            "Die persistente Spaltenkonfiguration folgt in einem spaeteren UI-Ausbau.",
        )

    def _show_about_dialog(self) -> None:
        """
        Zeigt eine kompakte Ueber-Box mit Produktkontext der Anwendung an.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Hilfe bleibt lokal und leichtgewichtig, ohne zusaetzliche Dialogklassen
          fuer einen kleinen statischen Informationsblock einzufuehren.
        """

        QMessageBox.information(
            self,
            "Ueber iGitty",
            "iGitty ist ein intelligenter Repository Manager fuer lokale und GitHub-Repositories.",
        )

    def _open_live_log_file(self) -> None:
        """
        Oeffnet die zentrale Laufzeit-Logdatei im Betriebssystem, sofern bekannt.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Nicht vorhandene Dateien werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode ist bewusst rein lesend und betrifft nur lokale UI-Hilfsnavigation.
        """

        live_log_file = self._diagnostics_window.live_log_file()
        if live_log_file is not None and live_log_file.exists():
            os.startfile(live_log_file)  # type: ignore[attr-defined]

    def _open_data_directory(self) -> None:
        """
        Oeffnet den gemeinsamen Datenordner der Anwendung, sofern aus dem Logpfad ableitbar.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Nicht vorhandene Verzeichnisse werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode leitet den Datenpfad aus bekannten Runtime-Dateien ab, statt
          zusaetzlichen Zustand im Hauptfenster zu spiegeln.
        """

        live_log_file = self._diagnostics_window.live_log_file()
        if live_log_file is None:
            return
        candidate_directory = live_log_file.parent.parent / "data"
        if candidate_directory.exists():
            os.startfile(candidate_directory)  # type: ignore[attr-defined]

    def _open_readme_file(self) -> None:
        """
        Oeffnet die README-Datei des Projekts im Standardprogramm des Betriebssystems.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehlende Dateien werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Hilfeeintraege bleiben einfache lokale Dateiaktionen und fuehren keine
          netzwerkabhaengige Dokumentationslogik ein.
        """

        readme_file = Path.cwd() / "README.md"
        if readme_file.exists():
            os.startfile(readme_file)  # type: ignore[attr-defined]

    def _open_developer_documentation(self) -> None:
        """
        Oeffnet die Entwicklerhinweise des Projekts im Standardprogramm.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehlende Dateien werden defensiv ignoriert.

        Wichtige interne Logik:
        - Als Startpunkt wird bewusst die projektinterne `AGENTS.md` genutzt, weil dort
          die aktuellsten Entwicklungsregeln und Architekturhinweise gepflegt werden.
        """

        documentation_file = Path.cwd() / "AGENTS.md"
        if documentation_file.exists():
            os.startfile(documentation_file)  # type: ignore[attr-defined]

    def populate_remote_repositories(self, repositories: list[RemoteRepo]) -> None:
        """
        Fuellt die linke Tabelle mit geladenen Remote-Repositories.

        Eingabeparameter:
        - repositories: Vollstaendig aufbereitete RemoteRepo-Objekte.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; die Darstellung behandelt fehlende Felder defensiv.

        Wichtige interne Logik:
        - Reduziert das View-Mapping auf eine einzige Stelle im UI-Layer.
        """

        self._remote_repositories = list(repositories)
        rows = [self._build_remote_row_values(repo) for repo in repositories]
        self._remote_table.populate_rows(rows)
        for row_index, repo in enumerate(repositories):
            self._render_remote_row(row_index, repo)
        self._refresh_repository_table()
        self._update_remote_action_buttons()

    def populate_local_repositories(self, repositories) -> None:
        """
        Fuellt die rechte Tabelle mit erkannten lokalen Repositories.

        Eingabeparameter:
        - repositories: Vollstaendig aufbereitete LocalRepo-Objekte.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Felder werden defensiv in Strings umgesetzt.

        Wichtige interne Logik:
        - Die Darstellung konzentriert sich auf die fuer den MVP wichtigsten Statuswerte.
        """

        self._local_repositories = list(repositories)
        rows = [self._build_local_row_values(repo) for repo in repositories]
        self._local_table.populate_rows(rows)
        for row_index, repo in enumerate(repositories):
            self._render_local_row(row_index, repo)
        self._refresh_repository_table()
        self._update_local_action_buttons()
        if not self._local_repositories:
            self._diagnostics_window.set_local_repo_diagnostics([])
            self._diagnostics_window.set_local_repo_history([])
            self._diagnostics_panel.set_messages([], "Keine Repository-Diagnose vorhanden.")
            self._history_panel.set_messages([], "Keine Job-Historie vorhanden.")

    def update_status(self, status: StatusSnapshot) -> None:
        """
        Aktualisiert die sichtbare Statusleiste des Hauptfensters.

        Eingabeparameter:
        - status: Vollstaendig vorbereitete Statuswerte.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Delegiert die eigentliche Darstellung an ein dediziertes Widget.
        """

        self._status_bar_widget.update_snapshot(status)

    def append_log_line(self, message: str) -> None:
        """
        Fuegt dem Logpanel eine neue Zeile hinzu.

        Eingabeparameter:
        - message: Bereits formatierte Lognachricht.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Logpanel bleibt append-only, um die Nachvollziehbarkeit im MVP zu erhalten.
        """

        self._log_panel.append_message(message)

    def _refresh_repository_table(self) -> None:
        """
        Baut die sichtbare kombinierte Repository-Tabelle aus den aktuellen Local-/Remote-Listen neu auf.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Datenquellen fuehren lediglich zu einer leeren Tabelle.

        Wichtige interne Logik:
        - Gekoppelte oder bereits lokal vorhandene Repositories werden nur einmal gezeigt.
        - Reine Remote-Repositories bleiben als eigene Zeilen sichtbar, damit Clone und
          Diagnose weiterhin direkt aus der Hauptansicht moeglich sind.
        """

        entries: list[RepositoryTableEntry] = []
        linked_remote_ids = {
            repository.remote_repo_id
            for repository in self._local_repositories
            if repository.remote_repo_id > 0
        }
        linked_remote_paths = {
            repository.full_path
            for repository in self._local_repositories
            if repository.full_path
        }

        for repository in sorted(self._local_repositories, key=lambda item: item.name.lower()):
            entries.append(RepositoryTableEntry(source_type="local", repository=repository))

        for repository in sorted(self._remote_repositories, key=lambda item: (item.full_name or item.name).lower()):
            if repository.repo_id in linked_remote_ids:
                continue
            if repository.linked_local_path and repository.linked_local_path in linked_remote_paths:
                continue
            entries.append(RepositoryTableEntry(source_type="remote", repository=repository))

        self._repository_entries = entries
        rows = [self._build_repository_row_values(entry) for entry in entries]
        self._repository_table.populate_rows(rows)
        for row_index, entry in enumerate(entries):
            self._render_repository_row(row_index, entry)
        self._update_primary_toolbar_actions()
        self._update_repository_menu_actions()

    def _build_repository_row_values(self, entry: RepositoryTableEntry) -> list[str]:
        """
        Erzeugt die sichtbaren Standardwerte einer kombinierten Repository-Zeile.

        Eingabeparameter:
        - entry: Sichtbarer Eintrag aus der kombinierten Repository-Liste.

        Rueckgabewerte:
        - Liste der Standardzellwerte fuer die Haupttabelle.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Lokale und entfernte Repositories werden auf dieselben Kernspalten abgebildet,
          damit die Bedienung in einer einzigen Haupttabelle konsistent bleibt.
        """

        if entry.source_type == "local":
            repository = entry.repository
            assert isinstance(repository, LocalRepo)
            return [
                "",
                repository.name,
                repository.current_branch or "-",
                repository.sync_state or repository.remote_status,
                str(repository.ahead_count),
                str(repository.behind_count),
                repository.health_state or "-",
                repository.recommended_action or "-",
                repository.last_checked_at or repository.last_commit_date or "-",
            ]

        repository = entry.repository
        assert isinstance(repository, RemoteRepo)
        return [
            "",
            repository.full_name or repository.name,
            repository.default_branch or "-",
            repository.sync_state or "REMOTE_ONLY",
            str(repository.ahead_count),
            str(repository.behind_count),
            repository.health_state or "-",
            repository.recommended_action or "-",
            repository.last_checked_at or repository.updated_at or "-",
        ]

    def _render_repository_row(self, row_index: int, entry: RepositoryTableEntry) -> None:
        """
        Ergaenzt Tooltip- und Statusdarstellung fuer eine Zeile der kombinierten Repository-Tabelle.

        Eingabeparameter:
        - row_index: Zielzeile innerhalb der sichtbaren Haupttabelle.
        - entry: Sichtbarer Eintrag aus der kombinierten Repository-Liste.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Zeilenfaerbung orientiert sich am Sync-State und macht Problemfaelle
          sofort sichtbar, ohne die Tabelle mit weiteren Warnspalten zu ueberladen.
        """

        from PySide6.QtWidgets import QTableWidgetItem

        repository = entry.repository
        if entry.source_type == "local":
            assert isinstance(repository, LocalRepo)
            item = QTableWidgetItem(repository.name)
            item.setToolTip(
                "\n".join(
                    [
                        "Quelle: Lokal",
                        f"Pfad: {repository.full_path}",
                        f"Remote: {repository.remote_url or '-'}",
                        f"Recommended: {repository.recommended_action or '-'}",
                    ]
                )
            )
            sync_state = repository.sync_state
        else:
            assert isinstance(repository, RemoteRepo)
            item = QTableWidgetItem(repository.full_name or repository.name)
            item.setToolTip(
                "\n".join(
                    [
                        "Quelle: Remote",
                        f"Clone URL: {repository.clone_url or '-'}",
                        f"Lokaler Pfad: {repository.linked_local_path or '-'}",
                        f"Recommended: {repository.recommended_action or '-'}",
                    ]
                )
            )
            sync_state = repository.sync_state

        self._repository_table.set_item(row_index, 1, item)
        self._repository_table.clear_row_background(row_index)
        if sync_state == "REMOTE_MISSING":
            self._repository_table.set_row_background(row_index, "#5c1f24")
        elif sync_state == "DIVERGED":
            self._repository_table.set_row_background(row_index, "#5b3d12")
        elif sync_state == "LOCAL_AHEAD":
            self._repository_table.set_row_background(row_index, "#1f3b4d")
        elif sync_state == "REMOTE_ONLY":
            self._repository_table.set_row_background(row_index, "#1f2c3c")

    def set_local_repo_diagnostics(self, lines: list[str]) -> None:
        """
        Aktualisiert den Diagnosebereich fuer das aktuell selektierte lokale Repository.

        Eingabeparameter:
        - lines: Bereits formatierte Diagnosezeilen aus der Controller-/Service-Schicht.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Hauptfenster zeigt nur vorbereiteten Text an und enthaelt keine Diagnosefachlogik.
        """

        self._diagnostics_window.set_local_repo_diagnostics(lines)
        self._diagnostics_panel.set_messages(lines, "Keine Repository-Diagnose vorhanden.")

    def set_local_repo_history(self, lines: list[str]) -> None:
        """
        Aktualisiert den Historienbereich fuer das aktuell selektierte lokale Repository.

        Eingabeparameter:
        - lines: Bereits formatierte Historienzeilen aus der Controller-/Service-Schicht.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Hauptfenster zeigt nur vorbereitete Daten an und haelt keine Job-Logik selbst vor.
        """

        self._diagnostics_window.set_local_repo_history(lines)
        self._history_panel.set_messages(lines, "Keine Job-Historie vorhanden.")

    def show_diagnostics_window(self) -> None:
        """
        Oeffnet das separate Diagnosefenster im nicht-modalen Modus.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - `show()` statt `exec()` haelt das Hauptfenster waehrend der Diagnose nutzbar.
        """

        self._diagnostics_window.show()
        self._diagnostics_window.raise_()
        self._diagnostics_window.activateWindow()

    def set_target_directory(self, path_text: str) -> None:
        """
        Zeigt den aktuell konfigurierten Zielordner im UI an.

        Eingabeparameter:
        - path_text: Darzustellender Zielpfad.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die UI speichert den Pfad nicht fachlich, sondern nur zur Anzeige.
        """

        self._path_selector.set_path(path_text)

    def set_live_log_file(self, log_file: Path) -> None:
        """
        Uebergibt den Pfad der zentralen `log.txt` an das Diagnosefenster.

        Eingabeparameter:
        - log_file: Vollstaendiger Dateipfad der Laufzeit-Logdatei.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Hauptfenster bleibt reine Durchreiche und haelt keine eigene Dateilogik.
        """

        self._diagnostics_window.set_live_log_file(log_file)

    def set_remote_loading(self, is_loading: bool) -> None:
        """
        Aktiviert oder deaktiviert die Remote-Ladeaktion im UI.

        Eingabeparameter:
        - is_loading: `True` waehrend eines aktiven Ladevorgangs.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Schuetzt vor Mehrfachstarts und signalisiert den aktuellen Zustand direkt im Buttontext.
        """

        self._toolbar_refresh_all_action.setEnabled(not is_loading)
        self._toolbar_refresh_all_action.setText("Aktualisiere..." if is_loading else "Alles aktualisieren")

    def set_clone_loading(self, is_loading: bool) -> None:
        """
        Aktiviert oder deaktiviert den Clone-Button waehrend eines aktiven Batch-Clones.

        Eingabeparameter:
        - is_loading: `True` solange der Clone-Worker aktiv ist.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Schuetzt vor parallelen Clone-Vorgaengen und macht den Zustand sichtbar.
        """

        self._toolbar_clone_action.setText("Clone..." if is_loading else "Clone")
        if not is_loading:
            self._update_primary_toolbar_actions()

    def set_commit_loading(self, is_loading: bool) -> None:
        """
        Aktualisiert den UI-Zustand fuer laufende Commit-Aktionen.

        Eingabeparameter:
        - is_loading: `True` waehrend eines aktiven Commit-Batches.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Sperrt den Button waehrend des Workers und macht den Zustand sichtbar.
        """

        self._toolbar_commit_action.setText("Commit..." if is_loading else "Commit")
        if not is_loading:
            self._update_primary_toolbar_actions()

    def set_push_loading(self, is_loading: bool) -> None:
        """
        Aktualisiert den UI-Zustand fuer laufende Push-Aktionen.

        Eingabeparameter:
        - is_loading: `True` waehrend eines aktiven Push-Batches.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Verhindert parallele Push-Aktionen.
        """

        self._toolbar_push_action.setText("Push..." if is_loading else "Push")
        if not is_loading:
            self._update_primary_toolbar_actions()

    def set_delete_loading(self, is_loading: bool) -> None:
        """
        Aktualisiert den UI-Zustand fuer laufende Remote-Delete-Aktionen.

        Eingabeparameter:
        - is_loading: `True` waehrend eines aktiven Delete-Batches.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Sperrt den Delete-Button waehrend des Workers.
        """

        self._update_repository_menu_actions()

    def set_struct_scan_loading(self, is_loading: bool) -> None:
        """
        Aktualisiert den UI-Zustand fuer laufende Struktur-Scans.

        Eingabeparameter:
        - is_loading: `True` waehrend eines aktiven Struktur-Batches.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Button wird waehrend des Scans deaktiviert, damit keine Ueberlappung entsteht.
        """

        self._update_repository_menu_actions()

    def set_remote_filter_text(self, filter_text: str) -> None:
        """
        Uebergibt den aktuellen Filtertext an die Remote-Tabelle.

        Eingabeparameter:
        - filter_text: Freitext fuer die Tabellenfilterung.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Hauptfenster delegiert die eigentliche Filterlogik an das Tabellenwidget.
        """

        self._remote_table.apply_filter(filter_text)
        self._repository_table.apply_filter(filter_text)

    def set_local_filter_text(self, filter_text: str) -> None:
        """
        Uebergibt den aktuellen Filtertext an die lokale Tabelle.

        Eingabeparameter:
        - filter_text: Freitext fuer die Tabellenfilterung der lokalen Liste.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Entkoppelt den Controller von der konkreten Widget-Implementierung.
        """

        self._local_table.apply_filter(filter_text)
        self._repository_table.apply_filter(filter_text)

    def set_local_loading(self, is_loading: bool) -> None:
        """
        Aktiviert oder deaktiviert die lokale Scan-Aktion im UI.

        Eingabeparameter:
        - is_loading: `True` waehrend eines aktiven Scanvorgangs.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Verhindert Mehrfachstarts und macht den aktiven Zustand sichtbar.
        """

        self._toolbar_refresh_all_action.setEnabled(not is_loading)
        self._toolbar_refresh_all_action.setText("Aktualisiere..." if is_loading else "Alles aktualisieren")

    def upsert_local_repository(self, repository: LocalRepo) -> None:
        """
        Ersetzt oder ergaenzt genau einen lokalen Repository-Eintrag in der aktuellen Tabelle.

        Eingabeparameter:
        - repository: Neu eingelesener Zustand des lokalen Repositories.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte Eintraege werden einfach neu aufgenommen.

        Wichtige interne Logik:
        - Die Tabelle wird aus einer konsistenten Liste neu aufgebaut, damit alle
          Statusspalten zusammen aktualisiert werden.
        """

        previous_index = None
        for index, current_repository in enumerate(self._local_repositories):
            if current_repository.full_path == repository.full_path:
                previous_index = index
                break

        if previous_index is not None:
            del self._local_repositories[previous_index]
            self._local_table.remove_row(previous_index)

        insertion_index = self._find_local_insert_index(repository)
        self._local_repositories.insert(insertion_index, repository)
        self._local_table.insert_row(insertion_index, self._build_local_row_values(repository))
        self._render_local_row(insertion_index, repository)
        self._refresh_repository_table()
        self._update_local_action_buttons()
        self._update_repository_menu_actions()

    def remove_local_repository(self, local_path: str) -> None:
        """
        Entfernt genau einen lokalen Repository-Eintrag gezielt aus Tabelle und In-Memory-Liste.

        Eingabeparameter:
        - local_path: Vollstaendiger Pfad des zu entfernenden Repositories.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Unbekannte Pfade werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode wird fuer partielle UI-Aktualisierungen in STUFE 2 benoetigt,
          damit kein kompletter Tabellen-Rebuild fuer entfernte Eintraege noetig ist.
        """

        for index, repository in enumerate(self._local_repositories):
            if repository.full_path != local_path:
                continue
            del self._local_repositories[index]
            self._local_table.remove_row(index)
            self._refresh_repository_table()
            self._update_local_action_buttons()
            self._update_repository_menu_actions()
            if not self._local_repositories:
                self._diagnostics_window.set_local_repo_diagnostics([])
                self._diagnostics_window.set_local_repo_history([])
            return

    def upsert_remote_repository(self, repository: RemoteRepo) -> None:
        """
        Ersetzt oder ergaenzt genau einen Remote-Repository-Eintrag in der aktuellen Tabelle.

        Eingabeparameter:
        - repository: Neu geladener Zustand des Remote-Repositories.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; unbekannte Eintraege werden einfach neu aufgenommen.

        Wichtige interne Logik:
        - Der gezielte Neuaufbau der Remote-Liste sorgt dafuer, dass Sichtbarkeit,
          Tooltips und Sortierung gemeinsam aktualisiert werden.
        """

        previous_index = None
        for index, current_repository in enumerate(self._remote_repositories):
            if current_repository.repo_id == repository.repo_id:
                previous_index = index
                break

        if previous_index is not None:
            del self._remote_repositories[previous_index]
            self._remote_table.remove_row(previous_index)

        insertion_index = self._find_remote_insert_index(repository)
        self._remote_repositories.insert(insertion_index, repository)
        self._remote_table.insert_row(insertion_index, self._build_remote_row_values(repository))
        self._render_remote_row(insertion_index, repository)
        self._refresh_repository_table()
        self._update_remote_action_buttons()
        self._update_repository_menu_actions()

    def remove_remote_repository(self, repo_id: int) -> None:
        """
        Entfernt genau einen Remote-Repository-Eintrag gezielt aus Tabelle und In-Memory-Liste.

        Eingabeparameter:
        - repo_id: Stabile GitHub-Repository-ID des zu entfernenden Eintrags.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Unbekannte IDs werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode wird fuer partielle STUFE-2-Refreshes benoetigt, damit Remote-
          Loeschungen nicht mehr die komplette Tabelle neu aufbauen muessen.
        """

        for index, repository in enumerate(self._remote_repositories):
            if repository.repo_id != repo_id:
                continue
            del self._remote_repositories[index]
            self._remote_table.remove_row(index)
            self._refresh_repository_table()
            self._update_remote_action_buttons()
            self._update_repository_menu_actions()
            return

    def _choose_target_directory(self) -> None:
        """
        Oeffnet einen nativen Ordnerdialog fuer die Auswahl des Zielverzeichnisses.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Benutzer bricht die Auswahl ab; dann wird kein Signal emittiert.

        Wichtige interne Logik:
        - Das Fenster meldet nur den gewaehlten Pfad an den Controller und speichert ihn nicht fachlich selbst.
        """

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Zielordner fuer iGitty waehlen",
            self._path_selector.current_path(),
        )
        if selected_directory:
            self.target_directory_change_requested.emit(selected_directory)

    def selected_remote_repositories(self) -> list[RemoteRepo]:
        """
        Liefert die aktuell per Checkbox ausgewaehlten Remote-Repositories zurueck.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Liste der ausgewaehlten RemoteRepo-Objekte.

        Moegliche Fehlerfaelle:
        - Inkonsistente Tabellen- und Modellgroessen werden defensiv abgeschnitten.

        Wichtige interne Logik:
        - Das Hauptfenster mappt nur UI-Zeilen auf bereits gespeicherte Fachobjekte.
        """

        selected_repositories: list[RemoteRepo] = []
        for row_index in self._repository_table.checked_row_indices():
            if not (0 <= row_index < len(self._repository_entries)):
                continue
            entry = self._repository_entries[row_index]
            if entry.source_type != "remote":
                continue
            repository = entry.repository
            if isinstance(repository, RemoteRepo):
                selected_repositories.append(repository)
        return selected_repositories

    def selected_local_repositories(self) -> list[LocalRepo]:
        """
        Liefert die aktuell per Checkbox ausgewaehlten lokalen Repositories zurueck.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Liste der ausgewaehlten LocalRepo-Objekte.

        Moegliche Fehlerfaelle:
        - Inkonsistente Tabellen- und Modellgroessen werden defensiv abgeschnitten.

        Wichtige interne Logik:
        - Das Mapping spiegelt bewusst die Remote-Seite fuer ein konsistentes UI-Verhalten.
        """

        selected_repositories: list[LocalRepo] = []
        for row_index in self._repository_table.checked_row_indices():
            if not (0 <= row_index < len(self._repository_entries)):
                continue
            entry = self._repository_entries[row_index]
            if entry.source_type != "local":
                continue
            repository = entry.repository
            if isinstance(repository, LocalRepo):
                selected_repositories.append(repository)
        return selected_repositories

    def _open_repository_row(self, row_index: int) -> None:
        """
        Reagiert auf einen Doppelklick in der kombinierten Haupttabelle.

        Eingabeparameter:
        - row_index: Index der aktivierten Zeile in der sichtbaren Repository-Tabelle.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Indizes werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode leitet den Doppelklick auf die bestehenden Local- oder Remote-
          Oeffnungspfade weiter, statt einen zweiten Repo-Kontext-Workflow aufzubauen.
        """

        if not (0 <= row_index < len(self._repository_entries)):
            return
        self._select_repository_row(row_index)
        entry = self._repository_entries[row_index]
        if entry.source_type == "local":
            repository = entry.repository
            assert isinstance(repository, LocalRepo)
            self._open_local_row(self._local_repositories.index(repository))
            return
        repository = entry.repository
        assert isinstance(repository, RemoteRepo)
        self._open_remote_row(self._remote_repositories.index(repository))

    def _select_repository_row(self, row_index: int) -> None:
        """
        Uebernimmt die Selektion einer sichtbaren Haupttabellenzeile in die bestehende Local-/Remote-Auswahl.

        Eingabeparameter:
        - row_index: Selektierte Zeile der kombinierten Repository-Tabelle.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Indizes werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die sichtbare Haupttabelle bleibt damit die zentrale Bedienflaeche, waehrend
          die Fachsignale weiter in ihren etablierten Quelltypen bleiben.
        """

        if not (0 <= row_index < len(self._repository_entries)):
            return
        self._selected_repository_index = row_index
        entry = self._repository_entries[row_index]
        if entry.source_type == "local":
            repository = entry.repository
            assert isinstance(repository, LocalRepo)
            self._select_local_row(self._local_repositories.index(repository))
        else:
            repository = entry.repository
            assert isinstance(repository, RemoteRepo)
            self._select_remote_row(self._remote_repositories.index(repository))
        self._update_details_panel()

    def _show_repository_context_menu(self, row_index: int) -> None:
        """
        Oeffnet das passende dynamische Kontextmenue fuer die sichtbare Haupttabellenzeile.

        Eingabeparameter:
        - row_index: Zeile der kombinierten Repository-Tabelle.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Indizes werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode verteilt nur nach Quelltyp und nutzt dann die bestehenden
          zustandsabhaengigen Kontextmenues fuer lokale oder entfernte Repositories.
        """

        if not (0 <= row_index < len(self._repository_entries)):
            return
        entry = self._repository_entries[row_index]
        if entry.source_type == "local":
            self._show_local_context_menu(self._local_repositories.index(entry.repository))
            return
        self._show_remote_context_menu(self._remote_repositories.index(entry.repository))

    def _open_remote_row(self, row_index: int) -> None:
        """
        Meldet einen Doppelklick auf eine Remote-Zeile an den Hauptcontroller.

        Eingabeparameter:
        - row_index: Index der aktivierten Tabellenzeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Indizes werden defensiv ignoriert.

        Wichtige interne Logik:
        - Das Fenster reicht nur die fachliche Referenz und den Quelltyp weiter.
        """

        if 0 <= row_index < len(self._remote_repositories):
            repository = self._remote_repositories[row_index]
            self.remote_repo_open_requested.emit(
                {
                    "repo_id": repository.repo_id,
                    "remote_repo_id": repository.repo_id,
                    "repo_name": repository.name,
                    "repo_full_name": repository.full_name,
                    "remote_url": repository.html_url,
                    "clone_url": repository.clone_url,
                },
                "remote",
            )

    def _open_local_row(self, row_index: int) -> None:
        """
        Meldet einen Doppelklick auf eine lokale Zeile an den Hauptcontroller.

        Eingabeparameter:
        - row_index: Index der aktivierten Tabellenzeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Indizes werden defensiv ignoriert.

        Wichtige interne Logik:
        - Verwendet den Repository-Namen als Referenz fuer den Struktur-Vault des MVP.
        """

        if 0 <= row_index < len(self._local_repositories):
            repository = self._local_repositories[row_index]
            self.local_repo_open_requested.emit(
                {
                    "repo_name": repository.name,
                    "local_path": repository.full_path,
                    "remote_repo_id": repository.remote_repo_id,
                    "remote_url": repository.remote_url,
                    "clone_url": repository.remote_url,
                },
                "local",
            )

    def _select_local_row(self, row_index: int) -> None:
        """
        Meldet die aktuell selektierte lokale Tabellenzeile an den Controller.

        Eingabeparameter:
        - row_index: Selektierte Tabellenzeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Indizes werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Selektion wird ueber eine stabile fachliche Referenz statt ueber sichtbare Spaltentexte weitergereicht.
        """

        if 0 <= row_index < len(self._local_repositories):
            self._selected_local_index = row_index
            self._selection_source = "local"
            repository = self._local_repositories[row_index]
            self.local_repo_selected.emit(
                {
                    "repo_name": repository.name,
                    "local_path": repository.full_path,
                    "remote_repo_id": repository.remote_repo_id,
                    "remote_url": repository.remote_url,
                }
            )
            self._update_repository_menu_actions()
            self._update_primary_toolbar_actions()
            self._update_details_panel()

    def _select_remote_row(self, row_index: int) -> None:
        """
        Meldet die aktuell selektierte Remote-Tabellenzeile an den Controller und aktualisiert Menues.

        Eingabeparameter:
        - row_index: Selektierte Tabellenzeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Indizes werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die zuletzt aktive Selektion steuert die dynamische Menueaktivierung fuer
          repository-bezogene Aktionen im Hauptmenue.
        """

        if 0 <= row_index < len(self._remote_repositories):
            self._selected_remote_index = row_index
            self._selection_source = "remote"
            repository = self._remote_repositories[row_index]
            self.remote_repo_selected.emit(
                {
                    "repo_id": repository.repo_id,
                    "repo_name": repository.name,
                    "repo_owner": repository.owner,
                    "remote_url": repository.html_url,
                }
            )
            self._update_repository_menu_actions()
            self._update_primary_toolbar_actions()
            self._update_details_panel()

    def _update_details_panel(self) -> None:
        """
        Aktualisiert das sichtbare Repository-Details-Panel fuer die aktuelle Selektion.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Selektion fuehrt zu einem Platzhaltertext.

        Wichtige interne Logik:
        - Das Panel zeigt bewusst eine kompakte, sofort lesbare Zusammenfassung statt
          den vollstaendigen RepoViewer zu duplizieren.
        """

        if self._selection_source == "local":
            repository = self._current_local_repository()
            if repository is None:
                self._details_panel.set_messages([], "Kein Repository ausgewaehlt.")
                return
            self._details_panel.set_messages(
                [
                    f"Quelle: Lokal",
                    f"Name: {repository.name}",
                    f"Pfad: {repository.full_path}",
                    f"Branch: {repository.current_branch or '-'}",
                    f"Sync State: {repository.sync_state or repository.remote_status}",
                    f"Ahead / Behind: {repository.ahead_count} / {repository.behind_count}",
                    f"Health: {repository.health_state or '-'}",
                    f"Recommended Action: {repository.recommended_action or '-'}",
                    f"Remote URL: {repository.remote_url or '-'}",
                    f"Last Checked: {repository.last_checked_at or '-'}",
                ],
                "Kein Repository ausgewaehlt.",
            )
            return

        if self._selection_source == "remote":
            repository = self._current_remote_repository()
            if repository is None:
                self._details_panel.set_messages([], "Kein Repository ausgewaehlt.")
                return
            self._details_panel.set_messages(
                [
                    "Quelle: Remote",
                    f"Name: {repository.full_name or repository.name}",
                    f"Owner: {repository.owner or '-'}",
                    f"Linked Local Path: {repository.linked_local_path or '-'}",
                    f"Branch: {repository.default_branch or '-'}",
                    f"Sync State: {repository.sync_state or '-'}",
                    f"Ahead / Behind: {repository.ahead_count} / {repository.behind_count}",
                    f"Health: {repository.health_state or '-'}",
                    f"Recommended Action: {repository.recommended_action or '-'}",
                    f"Visibility: {repository.visibility or '-'}",
                    f"Updated: {repository.updated_at or '-'}",
                ],
                "Kein Repository ausgewaehlt.",
            )
            return

        self._details_panel.set_messages([], "Kein Repository ausgewaehlt.")

    def get_remote_repositories(self) -> list[RemoteRepo]:
        """
        Liefert die aktuell im Hauptfenster gehaltenen Remote-Repositories.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Flache Kopie der aktuellen Remote-Repository-Liste.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Stellt Controllern lesenden Zugriff bereit, ohne die internen Listen direkt freizugeben.
        """

        return list(self._remote_repositories)

    def _current_local_repository(self) -> LocalRepo | None:
        """
        Liefert das aktuell ausgewaehlte lokale Repository oder `None`.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Aktuell selektiertes LocalRepo oder `None`.

        Moegliche Fehlerfaelle:
        - Keine; ungueltige oder fehlende Selektion liefert `None`.

        Wichtige interne Logik:
        - Die Hilfsmethode entkoppelt Menue- und Kontextlogik von rohen Tabellenindizes.
        """

        if 0 <= self._selected_local_index < len(self._local_repositories):
            return self._local_repositories[self._selected_local_index]
        return None

    def _current_remote_repository(self) -> RemoteRepo | None:
        """
        Liefert das aktuell ausgewaehlte Remote-Repository oder `None`.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Aktuell selektiertes RemoteRepo oder `None`.

        Moegliche Fehlerfaelle:
        - Keine; ungueltige oder fehlende Selektion liefert `None`.

        Wichtige interne Logik:
        - Die Hilfsmethode entkoppelt Menue- und Kontextlogik von rohen Tabellenindizes.
        """

        if 0 <= self._selected_remote_index < len(self._remote_repositories):
            return self._remote_repositories[self._selected_remote_index]
        return None

    def get_local_repositories(self) -> list[LocalRepo]:
        """
        Liefert die aktuell im Hauptfenster gehaltenen lokalen Repositories.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Flache Kopie der aktuellen LocalRepo-Liste.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Dient der zentralen Repo-Kontext-Bildung im MainController.
        """

        return list(self._local_repositories)

    def current_repository_selection(self):
        """
        Liefert die aktuelle Repository-Selektion des Hauptfensters als Quelle plus Referenz.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Tupel aus Quelltyp (`local`, `remote` oder Leerstring) und Referenzdictionary oder `None`.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Selektion liefert eine leere Quelle und `None`.

        Wichtige interne Logik:
        - Der MainController kann dadurch menuebasierte Aktionen ausloesen, ohne auf
          interne Tabellenindizes des Fensters zugreifen zu muessen.
        """

        return self._selection_source, self._current_repository_reference()

    def _update_repository_menu_actions(self) -> None:
        """
        Aktiviert oder deaktiviert Repository-Menuepunkte anhand der aktuellen Selektion.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Das Menue liest seine Aktivierung ausschliesslich aus den bereits zentral
          aufgeloesten `available_actions` der selektierten Repository-Modelle.
        """

        current_actions = set(self._current_repository_action_ids())
        selection_available = bool(current_actions) or self._current_repository_reference() is not None
        always_allowed = {"open_repository", "open_repo_explorer", "show_history", "show_diagnostics"}
        supported_actions = {
            "open_repository",
            "show_in_explorer",
            "clone",
            "pull",
            "push",
            "commit",
            "create_remote",
            "repair_remote",
            "remove_remote",
            "reinitialize_repository",
            "resolve_divergence",
            "open_repo_explorer",
            "show_history",
            "show_diagnostics",
            "set_private",
            "set_public",
            "refresh_repository",
        }
        for action_id, action in self._repository_menu_actions.items():
            action.setEnabled(
                selection_available
                and action_id in supported_actions
                and (action_id in always_allowed or action_id in current_actions)
            )

    def _update_primary_toolbar_actions(self) -> None:
        """
        Aktiviert die sichtbaren Toolbar-Aktionen anhand des aktuell selektierten Repository-Zustands.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Toolbar zeigt nur die wichtigsten Primaeraktionen und liest ihre Aktivierung
          aus denselben `available_actions` wie Menue und Kontextmenue.
        """

        current_actions = set(self._current_repository_action_ids())
        self._toolbar_refresh_all_action.setEnabled(True)
        self._toolbar_pull_action.setEnabled("pull" in current_actions)
        self._toolbar_push_action.setEnabled("push" in current_actions)
        self._toolbar_commit_action.setEnabled("commit" in current_actions)
        self._toolbar_clone_action.setEnabled("clone" in current_actions)
        self._toolbar_publish_action.setEnabled("create_remote" in current_actions)

    def _current_repository_action_ids(self) -> list[str]:
        """
        Liefert die verfuegbaren technischen Aktionen der aktuellen Selektion.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Liste technischer Aktions-IDs fuer das aktive Repository.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Selektion liefert eine leere Liste.

        Wichtige interne Logik:
        - Die Methode bildet die Bruecke zwischen Resolver-Ergebnis in den View-Modellen
          und der dynamischen Menue-/Kontextsteuerung im Hauptfenster.
        """

        if self._selection_source == "local":
            repository = self._current_local_repository()
            return list(repository.available_actions) if repository is not None else []
        if self._selection_source == "remote":
            repository = self._current_remote_repository()
            return list(repository.available_actions) if repository is not None else []
        return []

    def _current_repository_reference(self):
        """
        Liefert die fachliche Referenz des aktuell selektierten Repositorys fuer Signal-Emissionen.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Referenzdictionary fuer Controller oder `None`.

        Moegliche Fehlerfaelle:
        - Keine; fehlende Selektion liefert `None`.

        Wichtige interne Logik:
        - Die Methode zentralisiert die Referenzbildung, damit Menue und Kontextmenue
          keine separaten Sonderpfade fuer dieselbe Auswahl pflegen.
        """

        if self._selection_source == "local":
            repository = self._current_local_repository()
            if repository is None:
                return None
            return {
                "repo_name": repository.name,
                "local_path": repository.full_path,
                "remote_repo_id": repository.remote_repo_id,
                "remote_url": repository.remote_url,
                "remote_status": repository.remote_status,
            }
        if self._selection_source == "remote":
            repository = self._current_remote_repository()
            if repository is None:
                return None
            return {
                "repo_id": repository.repo_id,
                "repo_name": repository.name,
                "repo_owner": repository.owner,
                "repo_full_name": repository.full_name,
                "remote_url": repository.html_url,
                "clone_url": repository.clone_url,
                "visibility": repository.visibility,
            }
        return None

    def _trigger_repository_action(self, action_id: str) -> None:
        """
        Leitet eine menueausgeloeste Repository-Aktion an das passende Signal oder die passende UI-Hilfe weiter.

        Eingabeparameter:
        - action_id: Technische Aktions-ID aus Menue oder Kontextmenue.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Fehlende oder ungueltige Selektionen werden defensiv ignoriert.

        Wichtige interne Logik:
        - Die Methode bleibt rein koordinierend und fuehrt keine Repository-Fachlogik
          direkt im Hauptfenster aus.
        """

        repo_ref = self._current_repository_reference()
        if repo_ref is None:
            return

        if self._selection_source == "local":
            if action_id == "refresh_repository":
                self.refresh_selected_repository_requested.emit()
                return
            if action_id in {"open_repository", "open_repo_explorer", "show_history", "show_diagnostics"}:
                self.local_repo_open_requested.emit(repo_ref, "local")
                return
            if action_id == "show_in_explorer":
                local_path = repo_ref.get("local_path")
                if local_path:
                    os.startfile(local_path)  # type: ignore[attr-defined]
                return
            self.local_repo_action_requested.emit(repo_ref, action_id)
            return

        if self._selection_source == "remote":
            if action_id == "refresh_repository":
                self.refresh_selected_repository_requested.emit()
                return
            if action_id in {"open_repository", "open_repo_explorer", "show_history", "show_diagnostics"}:
                self.remote_repo_open_requested.emit(repo_ref, "remote")
                return
            self.remote_repo_action_requested.emit(repo_ref, action_id)

    def _build_remote_row_values(self, repository: RemoteRepo) -> list[str]:
        """
        Erzeugt die Standard-Textwerte einer Remote-Tabellenzeile.

        Eingabeparameter:
        - repository: Remote-Repository fuer die darzustellende Zeile.

        Rueckgabewerte:
        - Liste der Standardzellwerte fuer das Tabellenwidget.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die zentrale Zeilenabbildung haelt Vollaufbau und partielle Remote-Updates konsistent.
        """

        return [
            "",
            repository.name,
            repository.owner,
            repository.linked_local_path or "-",
            repository.default_branch,
            repository.sync_state,
            repository.health_state,
            repository.recommended_action,
            repository.visibility,
            repository.updated_at or "-",
        ]

    def _render_remote_row(self, row_index: int, repository: RemoteRepo) -> None:
        """
        Vervollstaendigt Spezialzellen und Statusmarkierungen einer Remote-Tabellenzeile.

        Eingabeparameter:
        - row_index: Zielzeile innerhalb der Remote-Tabelle.
        - repository: Fachmodell fuer die aktuelle Zeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; ungueltige Zeilen werden von Qt defensiv behandelt.

        Wichtige interne Logik:
        - Name-Tooltip und optionale Statusfarben werden getrennt von den Standardzellen
          gepflegt, damit gezielte Remote-Row-Updates einfach bleiben.
        """

        self._remote_table.set_item(row_index, 1, self._build_remote_name_item(repository))
        self._remote_table.clear_row_background(row_index)
        if repository.archived:
            self._remote_table.set_row_background(row_index, "#3a3a3a")
        elif repository.sync_state == "REMOTE_ONLY":
            self._remote_table.set_row_background(row_index, "#1f2c3c")
        elif repository.sync_state == "DIVERGED":
            self._remote_table.set_row_background(row_index, "#5b3d12")

    def _find_remote_insert_index(self, repository: RemoteRepo) -> int:
        """
        Ermittelt die sortierte Einfuegeposition eines Remote-Repositories.

        Eingabeparameter:
        - repository: Neu einzufuegendes oder verschobenes Remote-Repository.

        Rueckgabewerte:
        - Zielindex innerhalb der Remote-In-Memory-Liste und Tabelle.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Remote-Tabelle bleibt alphabetisch stabil, ohne bei Einzelupdates einen
          kompletten Neuaufbau zu benoetigen.
        """

        repository_key = (repository.full_name or repository.name).lower()
        for index, current_repository in enumerate(self._remote_repositories):
            current_key = (current_repository.full_name or current_repository.name).lower()
            if repository_key < current_key:
                return index
        return len(self._remote_repositories)

    def _update_remote_action_buttons(self) -> None:
        """
        Synchronisiert Clone- und Delete-Button mit der aktuellen Remote-Tabellenbelegung.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Button-Logik bleibt an einer zentralen Stelle, damit Vollaufbau und Delta-
          Updates dasselbe Verhalten fuer die Toolbar nutzen.
        """

        self._update_primary_toolbar_actions()

    def _build_local_row_values(self, repository: LocalRepo) -> list[str]:
        """
        Erzeugt die Standard-Textwerte einer lokalen Tabellenzeile.

        Eingabeparameter:
        - repository: Lokales Repository fuer die darzustellende Zeile.

        Rueckgabewerte:
        - Liste der Standardzellwerte fuer das Tabellenwidget.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die zentrale Zeilenabbildung haelt Vollaufbau und partielle Updates konsistent.
        """

        return [
            "",
            repository.name,
            repository.owner or "-",
            repository.full_path,
            repository.current_branch,
            repository.sync_state or repository.remote_status,
            str(repository.ahead_count),
            str(repository.behind_count),
            repository.health_state,
            repository.recommended_action,
            repository.last_checked_at or repository.last_commit_date or "-",
        ]

    def _render_local_row(self, row_index: int, repository: LocalRepo) -> None:
        """
        Vervollstaendigt Spezialzellen und Statusfarben einer lokalen Tabellenzeile.

        Eingabeparameter:
        - row_index: Zielzeile innerhalb der lokalen Tabelle.
        - repository: Fachmodell fuer die aktuelle Zeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine; ungültige Zeilen werden von Qt defensiv behandelt.

        Wichtige interne Logik:
        - Name-Tooltip, Public-Checkbox und Statusmarkierungen werden getrennt von den
          Standardtextzellen gepflegt, damit partielle Zeilenupdates einfach bleiben.
        """

        self._local_table.set_item(row_index, 1, self._build_local_name_item(repository))
        self._local_table.clear_row_background(row_index)
        if not repository.exists_local:
            self._local_table.set_row_background(row_index, "#3a3a3a")
        elif repository.sync_state == "REMOTE_MISSING":
            self._local_table.set_row_background(row_index, "#5c1f24")
        elif repository.sync_state == "DIVERGED":
            self._local_table.set_row_background(row_index, "#5b3d12")
        elif repository.sync_state == "LOCAL_AHEAD":
            self._local_table.set_row_background(row_index, "#1f3b4d")

    def _find_local_insert_index(self, repository: LocalRepo) -> int:
        """
        Ermittelt die sortierte Einfuegeposition eines lokalen Repositories.

        Eingabeparameter:
        - repository: Neu einzufuegendes oder verschobenes Repository.

        Rueckgabewerte:
        - Zielindex innerhalb der lokalen In-Memory-Liste und Tabelle.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Tabelle bleibt alphabetisch stabil, ohne dafuer bei Einzelupdates komplett
          neu aufgebaut werden zu muessen.
        """

        repository_key = repository.name.lower()
        for index, current_repository in enumerate(self._local_repositories):
            if repository_key < current_repository.name.lower():
                return index
        return len(self._local_repositories)

    def _update_local_action_buttons(self) -> None:
        """
        Synchronisiert die lokalen Toolbar-Buttons mit der aktuellen Tabellenbelegung.

        Eingabeparameter:
        - Keine.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Auswertung bleibt an einer Stelle, damit Vollaufbau und Delta-Updates
          dieselbe Button-Logik verwenden.
        """

        self._update_primary_toolbar_actions()

    def _build_local_name_item(self, repository: LocalRepo):
        """
        Erzeugt das Name-Item fuer die lokale Tabelle inklusive Pfad-Tooltip.

        Eingabeparameter:
        - repository: Lokales Repository fuer die aktuelle Tabellenzeile.

        Rueckgabewerte:
        - Vollstaendig vorbereitetes QTableWidgetItem.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Der Pfad verschwindet aus der Hauptspalte, bleibt aber ueber Tooltip und Repo-Kontext sichtbar.
        """

        from PySide6.QtWidgets import QTableWidgetItem

        item = QTableWidgetItem(repository.name)
        item.setToolTip(f"Lokaler Pfad: {repository.full_path}")
        item.setStatusTip(repository.full_path)
        return item

    def _build_remote_name_item(self, repository: RemoteRepo):
        """
        Erzeugt das Name-Item fuer die Remote-Tabelle inklusive kompakter Metadaten im Tooltip.

        Eingabeparameter:
        - repository: Remote-Repository fuer die aktuelle Zeile.

        Rueckgabewerte:
        - Vollstaendig vorbereitetes QTableWidgetItem.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Zusatzeigenschaften werden in den Tooltip verlagert, damit die Haupttabelle kompakt bleibt.
        """

        from PySide6.QtWidgets import QTableWidgetItem

        topics_text = ", ".join(repository.topics) if repository.topics else "-"
        item = QTableWidgetItem(repository.name)
        item.setToolTip(
            "\n".join(
                [
                    f"Full Name: {repository.full_name or '-'}",
                    f"Created: {repository.created_at or '-'}",
                    f"Updated: {repository.updated_at or '-'}",
                    f"Pushed: {repository.pushed_at or '-'}",
                    f"Size: {repository.size} KB",
                    f"Topics: {topics_text}",
                    f"Contributors: {repository.contributors_summary or '-'}",
                    f"Beschreibung: {repository.description or '-'}",
                ]
            )
        )
        return item

    def _build_public_checkbox(self, repository: LocalRepo) -> QWidget:
        """
        Baut die Public-Anzeige fuer eine lokale Tabellenzeile auf.

        Eingabeparameter:
        - repository: Lokales Repository fuer die aktuelle Tabellenzeile.

        Rueckgabewerte:
        - QWidget mit Checkbox-Anzeige fuer die Public-Spalte.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Bereits veroeffentlichte Remotes werden nur angezeigt.
        - Unveroeffentlichte Repositories koennen eine lokale Push-Vorgabe setzen.
        """

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox = QCheckBox()
        checkbox.setChecked(repository.remote_visibility == "public" or repository.publish_as_public)
        checkbox.setToolTip(
            "Remote-Sichtbarkeit: "
            f"{repository.remote_visibility}"
            if repository.has_remote
            else "Lokale Vorgabe fuer spaeteren Push: public an/aus"
        )
        checkbox.setEnabled(not repository.has_remote)
        if not repository.has_remote:
            checkbox.toggled.connect(lambda checked, repo=repository: setattr(repo, "publish_as_public", checked))
        layout.addWidget(checkbox)
        return container

    def _show_local_context_menu(self, row_index: int) -> None:
        """
        Baut das Kontextmenue fuer eine lokale Tabellenzeile und emittiert nur Aktionssignale.

        Eingabeparameter:
        - row_index: Aktivierte Tabellenzeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Zeilen werden ignoriert.

        Wichtige interne Logik:
        - Das Hauptfenster erstellt nur das Menue; die eigentliche Fachwirkung liegt im Controller.
        """

        if not (0 <= row_index < len(self._local_repositories)):
            return

        self._select_local_row(row_index)
        repository = self._local_repositories[row_index]
        menu = QMenu(self)
        menu_actions: dict[str, object] = {}
        supported_actions = {
            "pull",
            "commit",
            "push",
            "review_changes",
            "stash_changes",
            "create_remote",
            "repair_remote",
            "remove_remote",
            "reinitialize_repository",
            "resolve_divergence",
            "refresh_repository",
            "open_repository",
            "show_in_explorer",
            "open_repo_explorer",
            "show_history",
            "show_diagnostics",
        }
        for action_name in ("open_repository", "show_in_explorer", "open_repo_explorer", "show_history", "show_diagnostics"):
            menu_actions[action_name] = menu.addAction(self._action_label(action_name))
        menu.addSeparator()
        destructive_actions = {"remove_remote", "reinitialize_repository", "delete_local_repository"}
        normal_actions = [
            action_name
            for action_name in repository.available_actions
            if action_name not in destructive_actions and action_name in supported_actions
        ]
        for action_name in normal_actions:
            menu_actions[action_name] = menu.addAction(self._action_label(action_name))
        if destructive_actions.intersection(repository.available_actions):
            menu.addSeparator()
            for action_name in repository.available_actions:
                if action_name not in destructive_actions:
                    continue
                menu_actions[action_name] = menu.addAction(self._action_label(action_name))
        selected_action = menu.exec(self.cursor().pos())
        for action_name, action in menu_actions.items():
            if selected_action == action:
                self._trigger_repository_action(action_name)
                return

    def _show_remote_context_menu(self, row_index: int) -> None:
        """
        Baut das Kontextmenue fuer eine Remote-Zeile und emittiert Sichtbarkeitsaktionen.

        Eingabeparameter:
        - row_index: Aktivierte Tabellenzeile.

        Rueckgabewerte:
        - Keine.

        Moegliche Fehlerfaelle:
        - Ungueltige Zeilen werden ignoriert.

        Wichtige interne Logik:
        - Die UI zeigt nur die fachlich sinnvolle Umschaltaktion fuer den aktuellen
          Sichtbarkeitszustand an und ueberlaesst die eigentliche Aenderung dem Controller.
        """

        if not (0 <= row_index < len(self._remote_repositories)):
            return

        self._select_remote_row(row_index)
        repository = self._remote_repositories[row_index]
        menu = QMenu(self)
        menu_actions: dict[str, object] = {}
        current_visibility_action = menu.addAction(f"Aktuell: {repository.visibility}")
        current_visibility_action.setEnabled(False)
        menu.addSeparator()
        for action_name in ("open_repository", "open_repo_explorer", "show_history", "show_diagnostics"):
            menu_actions[action_name] = menu.addAction(self._action_label(action_name))
        menu.addSeparator()
        supported_actions = {"clone", "set_private", "set_public"}
        for action_name in repository.available_actions:
            if action_name not in supported_actions:
                continue
            menu_actions[action_name] = menu.addAction(self._action_label(action_name))
        selected_action = menu.exec(self.cursor().pos())
        for action_name, action in menu_actions.items():
            if selected_action == action:
                self._trigger_repository_action(action_name)
                return
