"""Hauptfenster der iGitty-Anwendung."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
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


class MainWindow(QMainWindow):
    """Stellt das zweispaltige Arbeitsfenster des MVP bereit."""

    refresh_remote_requested = Signal()
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

        self._remote_table = RepoTableWidget(
            title="Remote GitHub Repositories",
            columns=["Auswahl", "Name", "Owner", "Sichtbarkeit", "Branch", "Language", "Archiv", "Fork", "Updated"],
        )
        self._local_table = RepoTableWidget(
            title="Lokale Repositories",
            columns=[
                "Auswahl",
                "Name",
                "Public",
                "Branch",
                "Remote",
                "Remote Status",
                "Online",
                "Recommended Action",
                "Aenderungen",
                "Letzter Commit",
            ],
        )
        self._path_selector = PathSelectorWidget()
        self._log_panel = LogPanelWidget()
        self._diagnostics_window = DiagnosticsWindow(self)
        self._status_bar_widget = StatusBarWidget()
        self._remote_repositories: list[RemoteRepo] = []
        self._local_repositories: list[LocalRepo] = []

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

        toolbar_box = QGroupBox("Aktionen")
        toolbar_layout = QHBoxLayout(toolbar_box)
        self._refresh_remote_button = QPushButton("Remote laden")
        self._scan_local_button = QPushButton("Lokale Repos scannen")
        self._clone_button = QPushButton("Klonen")
        self._commit_button = QPushButton("Commit")
        self._push_button = QPushButton("Push")
        self._delete_button = QPushButton("Remote loeschen")
        self._struct_scan_button = QPushButton("Struktur scannen")
        self._diagnostics_button = QPushButton("Diagnosefenster")
        self._refresh_remote_button.setObjectName("refresh_remote_button")
        self._scan_local_button.setObjectName("scan_local_button")
        self._clone_button.setObjectName("clone_button")
        self._commit_button.setObjectName("commit_button")
        self._push_button.setObjectName("push_button")
        self._delete_button.setObjectName("delete_button")
        self._struct_scan_button.setObjectName("struct_scan_button")
        self._diagnostics_button.setObjectName("diagnostics_button")
        self._clone_button.setEnabled(False)
        self._commit_button.setEnabled(False)
        self._push_button.setEnabled(False)
        self._delete_button.setEnabled(False)
        self._struct_scan_button.setEnabled(False)

        for widget in (
            self._refresh_remote_button,
            self._scan_local_button,
            self._clone_button,
            self._commit_button,
            self._push_button,
            self._delete_button,
            self._struct_scan_button,
            self._diagnostics_button,
        ):
            toolbar_layout.addWidget(widget)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(QLabel("Zielordner"))
        toolbar_layout.addWidget(self._path_selector, stretch=1)

        local_box = QGroupBox("Lokale Ansicht")
        local_layout = QVBoxLayout(local_box)
        local_layout.addWidget(self._local_table, stretch=1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._remote_table)
        splitter.addWidget(local_box)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        log_box = QGroupBox("Aktionslog")
        log_layout = QVBoxLayout(log_box)
        log_layout.addWidget(self._log_panel)

        root_layout.addWidget(toolbar_box)
        root_layout.addWidget(splitter, stretch=1)
        root_layout.addWidget(log_box, stretch=0)

        self.setCentralWidget(central_widget)
        self.setStatusBar(self._status_bar_widget)

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

        self._refresh_remote_button.clicked.connect(self.refresh_remote_requested.emit)
        self._scan_local_button.clicked.connect(self.scan_local_requested.emit)
        self._clone_button.clicked.connect(self.clone_requested.emit)
        self._commit_button.clicked.connect(self.commit_requested.emit)
        self._push_button.clicked.connect(self.push_requested.emit)
        self._delete_button.clicked.connect(self.delete_remote_requested.emit)
        self._struct_scan_button.clicked.connect(self.struct_scan_requested.emit)
        self._remote_table.filter_text_changed.connect(self.remote_filter_changed.emit)
        self._local_table.filter_text_changed.connect(self.local_filter_changed.emit)
        self._remote_table.row_activated.connect(self._open_remote_row)
        self._remote_table.row_context_requested.connect(self._show_remote_context_menu)
        self._local_table.row_activated.connect(self._open_local_row)
        self._local_table.row_context_requested.connect(self._show_local_context_menu)
        self._local_table.row_selected.connect(self._select_local_row)
        self._path_selector.browse_requested.connect(self._choose_target_directory)
        self._diagnostics_button.clicked.connect(self.show_diagnostics_window)

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

        self._remote_repositories = repositories
        rows = [
            [
                "",
                repo.name,
                repo.owner,
                repo.visibility,
                repo.default_branch,
                repo.language,
                "Ja" if repo.archived else "Nein",
                "Ja" if repo.fork else "Nein",
                repo.updated_at,
            ]
            for repo in repositories
        ]
        self._remote_table.populate_rows(rows)
        for row_index, repo in enumerate(repositories):
            self._remote_table.set_item(row_index, 1, self._build_remote_name_item(repo))
        self._clone_button.setEnabled(bool(repositories))
        self._delete_button.setEnabled(bool(repositories))

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

        self._local_repositories = repositories
        rows = [
            [
                "",
                repo.name,
                "",
                repo.current_branch,
                "Ja" if repo.has_remote else "Nein",
                repo.remote_status,
                self._format_online_state(repo.remote_exists_online),
                repo.recommended_action,
                f"Ja ({repo.modified_count}+{repo.untracked_count})" if repo.has_changes else "Nein",
                f"{repo.last_commit_hash} {repo.last_commit_date}",
            ]
            for repo in repositories
        ]
        self._local_table.populate_rows(rows)
        for row_index, repo in enumerate(repositories):
            name_item = self._build_local_name_item(repo)
            self._local_table.set_item(row_index, 1, name_item)
            self._local_table.set_cell_widget(row_index, 2, self._build_public_checkbox(repo))
            if repo.remote_status == "REMOTE_MISSING":
                self._local_table.set_row_background(row_index, "#5c1f24")
        has_local = bool(repositories)
        self._commit_button.setEnabled(has_local)
        self._push_button.setEnabled(has_local)
        self._struct_scan_button.setEnabled(has_local)
        if not repositories:
            self._diagnostics_window.set_local_repo_diagnostics([])
            self._diagnostics_window.set_local_repo_history([])

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

        self._refresh_remote_button.setEnabled(not is_loading)
        self._refresh_remote_button.setText("Lade..." if is_loading else "Remote laden")

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

        self._clone_button.setEnabled(not is_loading and bool(self._remote_repositories))
        self._clone_button.setText("Klonen..." if is_loading else "Klonen")

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

        self._commit_button.setEnabled(not is_loading and bool(self._local_repositories))
        self._commit_button.setText("Commit..." if is_loading else "Commit")

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

        self._push_button.setEnabled(not is_loading and bool(self._local_repositories))
        self._push_button.setText("Push..." if is_loading else "Push")

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

        self._delete_button.setEnabled(not is_loading and bool(self._remote_repositories))
        self._delete_button.setText("Loesche..." if is_loading else "Remote loeschen")

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

        self._struct_scan_button.setEnabled(not is_loading and bool(self._local_repositories))
        self._struct_scan_button.setText("Scanne Struktur..." if is_loading else "Struktur scannen")

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

        self._scan_local_button.setEnabled(not is_loading)
        self._scan_local_button.setText("Scanne..." if is_loading else "Lokale Repos scannen")

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

        repositories = list(self._local_repositories)
        for index, current_repository in enumerate(repositories):
            if current_repository.full_path == repository.full_path:
                repositories[index] = repository
                break
        else:
            repositories.append(repository)
        repositories.sort(key=lambda item: item.name.lower())
        self.populate_local_repositories(repositories)

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

        repositories = list(self._remote_repositories)
        for index, current_repository in enumerate(repositories):
            if current_repository.repo_id == repository.repo_id:
                repositories[index] = repository
                break
        else:
            repositories.append(repository)
        self.populate_remote_repositories(repositories)

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
        for row_index in self._remote_table.checked_row_indices():
            if 0 <= row_index < len(self._remote_repositories):
                selected_repositories.append(self._remote_repositories[row_index])
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
        for row_index in self._local_table.checked_row_indices():
            if 0 <= row_index < len(self._local_repositories):
                selected_repositories.append(self._local_repositories[row_index])
        return selected_repositories

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
            repository = self._local_repositories[row_index]
            self.local_repo_selected.emit(
                {
                    "repo_name": repository.name,
                    "local_path": repository.full_path,
                    "remote_repo_id": repository.remote_repo_id,
                    "remote_url": repository.remote_url,
                }
            )

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

    def _format_online_state(self, remote_exists_online: int | None) -> str:
        """
        Uebersetzt den Online-Zustand eines Remotes in eine kurze Tabellenanzeige.

        Eingabeparameter:
        - remote_exists_online: `1`, `0` oder `None` aus dem State-Layer.

        Rueckgabewerte:
        - Kurzer UI-String fuer die lokale Tabelle.

        Moegliche Fehlerfaelle:
        - Keine.

        Wichtige interne Logik:
        - Die Anzeige bleibt knapp, damit die eigentliche Fachlogik im Controller liegt.
        """

        if remote_exists_online == 1:
            return "Ja"
        if remote_exists_online == 0:
            return "Nein"
        return "Unbekannt"

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

        repository = self._local_repositories[row_index]
        repo_ref = {
            "repo_name": repository.name,
            "local_path": repository.full_path,
            "remote_url": repository.remote_url,
            "remote_status": repository.remote_status,
        }

        menu = QMenu(self)
        repair_action = menu.addAction("Repair remote")
        remove_action = menu.addAction("Remove remote")
        create_action = menu.addAction("Create GitHub repository")
        reinitialize_action = menu.addAction("Reinitialize repository")

        selected_action = menu.exec(self.cursor().pos())
        if selected_action == repair_action:
            self.local_repo_action_requested.emit(repo_ref, "repair_remote")
        elif selected_action == remove_action:
            self.local_repo_action_requested.emit(repo_ref, "remove_remote")
        elif selected_action == create_action:
            self.local_repo_action_requested.emit(repo_ref, "create_remote")
        elif selected_action == reinitialize_action:
            self.local_repo_action_requested.emit(repo_ref, "reinitialize_repository")

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

        repository = self._remote_repositories[row_index]
        repo_ref = {
            "repo_id": repository.repo_id,
            "repo_name": repository.name,
            "repo_owner": repository.owner,
            "remote_url": repository.html_url,
            "visibility": repository.visibility,
        }

        menu = QMenu(self)
        current_visibility_action = menu.addAction(f"Aktuell: {repository.visibility}")
        current_visibility_action.setEnabled(False)
        menu.addSeparator()

        toggle_action = None
        if repository.visibility == "public":
            toggle_action = menu.addAction("Auf private setzen")
        elif repository.visibility == "private":
            toggle_action = menu.addAction("Auf public setzen")

        selected_action = menu.exec(self.cursor().pos())
        if selected_action == toggle_action and repository.visibility == "public":
            self.remote_repo_action_requested.emit(repo_ref, "set_private")
        elif selected_action == toggle_action and repository.visibility == "private":
            self.remote_repo_action_requested.emit(repo_ref, "set_public")
