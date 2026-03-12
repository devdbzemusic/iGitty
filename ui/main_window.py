"""Hauptfenster der iGitty-Anwendung."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from models.repo_models import LocalRepo, RemoteRepo
from models.view_models import StatusSnapshot
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
    remote_repo_open_requested = Signal(str, str)
    local_repo_open_requested = Signal(str, str)

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

        self._remote_table = RepoTableWidget(
            title="Remote GitHub Repositories",
            columns=["Auswahl", "Name", "Owner", "Sichtbarkeit", "Branch", "Language", "Archiv", "Fork", "Updated"],
        )
        self._local_table = RepoTableWidget(
            title="Lokale Repositories",
            columns=["Auswahl", "Name", "Pfad", "Branch", "Remote", "Aenderungen", "Letzter Commit"],
        )
        self._path_selector = PathSelectorWidget()
        self._log_panel = LogPanelWidget()
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
        ):
            toolbar_layout.addWidget(widget)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(QLabel("Zielordner"))
        toolbar_layout.addWidget(self._path_selector, stretch=1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._remote_table)
        splitter.addWidget(self._local_table)
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
        self._local_table.row_activated.connect(self._open_local_row)
        self._path_selector.browse_requested.connect(self._choose_target_directory)

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
                repo.full_path,
                repo.current_branch,
                "Ja" if repo.has_remote else "Nein",
                f"Ja ({repo.modified_count}+{repo.untracked_count})" if repo.has_changes else "Nein",
                f"{repo.last_commit_hash} {repo.last_commit_date}",
            ]
            for repo in repositories
        ]
        self._local_table.populate_rows(rows)
        has_local = bool(repositories)
        self._commit_button.setEnabled(has_local)
        self._push_button.setEnabled(has_local)
        self._struct_scan_button.setEnabled(has_local)

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
            self.remote_repo_open_requested.emit(self._remote_repositories[row_index].name, "remote")

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
            self.local_repo_open_requested.emit(self._local_repositories[row_index].name, "local")
