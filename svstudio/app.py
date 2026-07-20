from __future__ import annotations

import html
import os
import random
import re
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .editor import CodeEditor
from .project import PROJECT_FILE, SOURCE_SUFFIXES, ProjectConfig
from .runner import ProcessWorker, RunnerError, build_plan, choose_toolchain, detect_toolchains
from .theme import APP_STYLESHEET, COLORS
from .waveform import WaveformPanel


UVM_LINE_RE = re.compile(r"\bUVM_(INFO|WARNING|ERROR|FATAL)\b")
SOURCE_RE = re.compile(r"(?P<file>[A-Za-z0-9_./\\-]+\.(?:sv|svh|v|vh))\((?P<line>\d+)\)")
VERILATOR_ERROR_RE = re.compile(
    r"%(?P<severity>Error|Warning)(?:-[A-Z0-9_]+)?:\s*(?P<file>[^:\r\n]+):(?P<line>\d+)(?::\d+)?:\s*(?P<message>.*)"
)


class UvmLogPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.lines: list[str] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(10, 5, 10, 5)
        title = QLabel("UVM REPORT STREAM")
        title.setObjectName("sectionTitle")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self.filters: dict[str, QCheckBox] = {}
        for severity in ("INFO", "WARNING", "ERROR", "FATAL"):
            checkbox = QCheckBox(severity.title())
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._render)
            self.filters[severity] = checkbox
            toolbar.addWidget(checkbox)
        clear = QPushButton("Clear")
        clear.setMaximumHeight(26)
        clear.clicked.connect(self.clear)
        toolbar.addWidget(clear)
        layout.addLayout(toolbar)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setFont(QFont("Cascadia Code", 9))
        self.view.setStyleSheet("padding: 7px;")
        layout.addWidget(self.view)

    def append(self, chunk: str) -> None:
        self.lines.extend(line for line in chunk.splitlines() if UVM_LINE_RE.search(line))
        self._render()

    def clear(self) -> None:
        self.lines.clear()
        self.view.clear()

    def _render(self) -> None:
        colors = {
            "INFO": COLORS["blue"],
            "WARNING": COLORS["orange"],
            "ERROR": COLORS["red"],
            "FATAL": "#ff3f55",
        }
        rendered = []
        for line in self.lines:
            match = UVM_LINE_RE.search(line)
            if not match or not self.filters[match.group(1)].isChecked():
                continue
            color = colors[match.group(1)]
            rendered.append(
                f'<div style="white-space:pre; color:{color}; margin:2px 0">{html.escape(line)}</div>'
            )
        self.view.setHtml("".join(rendered))
        self.view.moveCursor(QTextCursor.MoveOperation.End)


class DebugPanel(QWidget):
    rerun_requested = Signal()
    open_solver_requested = Signal()

    def __init__(self):
        super().__init__()
        self.reproduction = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        header = QHBoxLayout()
        title = QLabel("REPRODUCIBLE DEBUG SESSION")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        rerun = QPushButton("↻  Re-run Same Seed")
        rerun.clicked.connect(self.rerun_requested)
        header.addWidget(rerun)
        solver = QPushButton("Open Solver Log")
        solver.clicked.connect(self.open_solver_requested)
        header.addWidget(solver)
        copy = QPushButton("Copy Reproduction")
        copy.clicked.connect(self._copy_reproduction)
        header.addWidget(copy)
        root.addLayout(header)

        cards = QHBoxLayout()
        self.test_value = self._metric(cards, "TEST")
        self.seed_value = self._metric(cards, "SEED")
        self.engine_value = self._metric(cards, "ENGINE")
        self.status_value = self._metric(cards, "STATUS")
        root.addLayout(cards)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(78)
        self.details.setFont(QFont("Cascadia Code", 9))
        self.details.setPlaceholderText("Run or debug a test to capture its reproduction details")
        root.addWidget(self.details)

    @staticmethod
    def _metric(layout: QHBoxLayout, label: str) -> QLabel:
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 6, 10, 7)
        name = QLabel(label)
        name.setObjectName("sectionTitle")
        value = QLabel("—")
        value.setStyleSheet("font-weight: 700;")
        card_layout.addWidget(name)
        card_layout.addWidget(value)
        layout.addWidget(card, 1)
        return value

    def start_run(self, test: str, seed: int, engine: str, debug: bool, verbosity: str) -> None:
        self.test_value.setText(test)
        self.seed_value.setText(str(seed))
        self.engine_value.setText(engine)
        self.status_value.setText("Debugging" if debug else "Running")
        self.status_value.setStyleSheet(f"font-weight: 700; color: {COLORS['blue']};")
        self.reproduction = (
            f"test={test} seed={seed} engine={engine} verbosity={verbosity} "
            f"mode={'debug' if debug else 'run'}"
        )
        self.details.setPlainText(
            self.reproduction
            + ("\nStops on first UVM error · solver trace: .svstudio/solver.log" if debug else "")
        )

    def finish_run(self, success: bool, elapsed: float, problem_count: int) -> None:
        self.status_value.setText("Passed" if success else "Failed")
        color = COLORS["green"] if success else COLORS["red"]
        self.status_value.setStyleSheet(f"font-weight: 700; color: {color};")
        self.details.appendPlainText(f"elapsed={elapsed:.2f}s problems={problem_count}")

    def _copy_reproduction(self) -> None:
        if self.reproduction:
            QApplication.clipboard().setText(self.reproduction)


class ToolchainDialog(QDialog):
    def __init__(self, root: Path, config: ProjectConfig, parent=None):
        super().__init__(parent)
        self.root = root
        self.config = config
        self.setWindowTitle("Open-source Toolchains")
        self.resize(720, 470)
        layout = QVBoxLayout(self)

        heading = QLabel("Free, local SystemVerilog + UVM")
        heading.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(heading)
        description = QLabel(
            "SV Studio uses Verilator and the CHIPS Alliance UVM library. Both are open source and "
            "require no license server. WSL is recommended on Windows."
        )
        description.setWordWrap(True)
        description.setObjectName("muted")
        layout.addWidget(description)

        self.table = QTreeWidget()
        self.table.setHeaderLabels(["Status", "Toolchain", "Details"])
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 210)
        layout.addWidget(self.table)

        form = QFormLayout()
        self.engine = QComboBox()
        for chain in detect_toolchains():
            self.engine.addItem(chain.label, chain.key)
        preferred = self.engine.findData(config.simulator if config.simulator != "auto" else "wsl-verilator")
        if preferred >= 0:
            self.engine.setCurrentIndex(preferred)
        form.addRow("Project engine", self.engine)

        uvm_row = QHBoxLayout()
        self.uvm_home = QLineEdit(config.uvm_home)
        self.uvm_home.setPlaceholderText("Auto: tools/uvm-verilator")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_uvm)
        uvm_row.addWidget(self.uvm_home)
        uvm_row.addWidget(browse)
        form.addRow("UVM library", uvm_row)
        layout.addLayout(form)

        note = QLabel(
            "The setup builds current Verilator inside WSL and downloads the Apache-2.0 UVM library. "
            "It does not install or request any commercial EDA software."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)

        buttons = QHBoxLayout()
        self.setup_button = QPushButton("Set Up Free Toolchain")
        self.setup_button.setObjectName("primaryButton")
        self.setup_button.clicked.connect(self._start_setup)
        refresh = QPushButton("Refresh Status")
        refresh.clicked.connect(self._refresh)
        buttons.addWidget(self.setup_button)
        buttons.addWidget(refresh)
        buttons.addStretch()
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        dialog_buttons.accepted.connect(self._save)
        dialog_buttons.rejected.connect(self.reject)
        buttons.addWidget(dialog_buttons)
        layout.addLayout(buttons)
        self._refresh()

    def _refresh(self) -> None:
        self.table.clear()
        for chain in detect_toolchains():
            item = QTreeWidgetItem(["●  Ready" if chain.ready else "○  Missing", chain.label, chain.note])
            item.setForeground(0, QColor(COLORS["green"] if chain.ready else COLORS["muted"]))
            self.table.addTopLevelItem(item)

    def _browse_uvm(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select UVM Library", str(self.root))
        if selected:
            self.uvm_home.setText(selected)

    def _start_setup(self) -> None:
        script = self.root.parents[1] / "tools" / "setup_open_source_uvm.ps1" if self.root.name == "uvm_counter" else self.root / "tools" / "setup_open_source_uvm.ps1"
        if not script.exists():
            package_root = Path(__file__).resolve().parent.parent
            script = package_root / "tools" / "setup_open_source_uvm.ps1"
        if not script.exists():
            QMessageBox.warning(self, "Setup unavailable", "The open-source setup script could not be found.")
            return
        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoExit",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-ProjectRoot",
                    str(self.root),
                ],
                cwd=self.root,
            )
        except OSError as error:
            QMessageBox.critical(self, "Could not start setup", str(error))
            return
        QMessageBox.information(
            self,
            "Setup started",
            "The free toolchain setup is running in a terminal. When it says Complete, return here and click Refresh Status.",
        )

    def _save(self) -> None:
        self.config.simulator = self.engine.currentData()
        self.config.uvm_home = self.uvm_home.text().strip()
        self.config.save(self.root)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, project_root: Path):
        super().__init__()
        self.settings = QSettings("SVStudio", "SVStudio")
        self.project_root = project_root.resolve()
        self.config = ProjectConfig.load(self.project_root)
        self.editors: dict[Path, CodeEditor] = {}
        self.worker: ProcessWorker | None = None
        self._problem_keys: set[tuple[str, int, str]] = set()
        self._last_seed: int | None = None
        self._debug_mode = False
        self._run_started = 0.0
        self.setWindowTitle(f"SV Studio - {self.config.name}")
        self.setMinimumSize(960, 640)
        self.resize(1320, 820)
        self.setStyleSheet(APP_STYLESHEET)
        self._build_actions()
        self._build_menu()
        self._build_toolbar()
        self._build_workspace()
        self._build_statusbar()
        self.refresh_project_tree()
        self._discover_tests()
        self._update_engine_status()
        self._restore_window()
        self._open_start_file()

    def _build_actions(self) -> None:
        self.action_open_folder = QAction("Open Folder...", self, shortcut=QKeySequence.StandardKey.Open)
        self.action_open_folder.triggered.connect(self.open_folder)
        self.action_new_project = QAction("New Project...", self, shortcut="Ctrl+Shift+N")
        self.action_new_project.triggered.connect(self.new_project)
        self.action_save = QAction("Save", self, shortcut=QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(self.save_current)
        self.action_save_all = QAction("Save All", self, shortcut="Ctrl+Alt+S")
        self.action_save_all.triggered.connect(self.save_all)
        self.action_find = QAction("Find...", self, shortcut=QKeySequence.StandardKey.Find)
        self.action_find.triggered.connect(self.find_text)
        self.action_run = QAction("Run", self, shortcut="F5")
        self.action_run.triggered.connect(self.run_test)
        self.action_stop = QAction("Stop", self, shortcut="Shift+F5")
        self.action_stop.setEnabled(False)
        self.action_stop.triggered.connect(self.stop_test)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.action_new_project)
        file_menu.addAction(self.action_open_folder)
        file_menu.addSeparator()
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_all)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close, QKeySequence.StandardKey.Quit)
        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addAction("Undo", lambda: self.current_editor() and self.current_editor().undo(), QKeySequence.StandardKey.Undo)
        edit_menu.addAction("Redo", lambda: self.current_editor() and self.current_editor().redo(), QKeySequence.StandardKey.Redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_find)
        run_menu = self.menuBar().addMenu("Run")
        run_menu.addAction(self.action_run)
        run_menu.addAction(self.action_stop)
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction("About SV Studio", self.show_about)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        brand = QLabel("  SV STUDIO  ")
        brand.setObjectName("brand")
        toolbar.addWidget(brand)
        toolbar.addSeparator()
        toolbar.addAction(self.action_open_folder)
        toolbar.addAction(self.action_save)
        toolbar.addAction(self.action_run)
        toolbar.addAction(self.action_stop)
        toolbar.addSeparator()
        automatic = QLabel("SystemVerilog / UVM - automatic")
        automatic.setObjectName("muted")
        toolbar.addWidget(automatic)

    def _build_workspace(self) -> None:
        vertical = QSplitter(Qt.Orientation.Vertical)
        top = QSplitter(Qt.Orientation.Horizontal)
        top.addWidget(self._build_explorer())
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.setMovable(True)
        self.editor_tabs.tabCloseRequested.connect(self.close_editor)
        self.editor_tabs.currentChanged.connect(self._editor_changed)
        top.addWidget(self.editor_tabs)
        top.setSizes([240, 1080])
        top.setStretchFactor(1, 1)
        vertical.addWidget(top)

        self.bottom_tabs = QTabWidget()
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Cascadia Code", 9))
        self.console.setPlaceholderText("Build and simulation output will appear here")
        self.bottom_tabs.addTab(self.console, "Console")
        self.waveform = WaveformPanel()
        self.bottom_tabs.addTab(self.waveform, "Waveform")
        vertical.addWidget(self.bottom_tabs)
        vertical.setSizes([650, 245])
        vertical.setStretchFactor(0, 1)
        self.setCentralWidget(vertical)

    def _build_explorer(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 10, 5, 5)
        header = QHBoxLayout()
        title = QLabel("EXPLORER")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        refresh = QPushButton("Refresh")
        refresh.setFixedSize(62, 27)
        refresh.setToolTip("Refresh files")
        refresh.clicked.connect(self.refresh_project_tree)
        header.addWidget(refresh)
        layout.addLayout(header)
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderHidden(True)
        self.project_tree.itemDoubleClicked.connect(self._tree_open)
        self.project_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.project_tree.customContextMenuRequested.connect(self._tree_menu)
        layout.addWidget(self.project_tree)
        return panel

    def _build_inspector(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 6)
        title = QLabel("UVM RUN")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.engine_badge = QLabel()
        layout.addWidget(self.engine_badge, alignment=Qt.AlignmentFlag.AlignLeft)

        form = QFormLayout()
        form.setContentsMargins(0, 8, 0, 5)
        self.test_combo = QComboBox()
        self.test_combo.setEditable(True)
        form.addRow("Test", self.test_combo)
        self.verbosity = QComboBox()
        self.verbosity.addItems(["UVM_LOW", "UVM_MEDIUM", "UVM_HIGH", "UVM_FULL", "UVM_DEBUG"])
        self.verbosity.setCurrentText("UVM_MEDIUM")
        form.addRow("Verbosity", self.verbosity)
        seed_row = QHBoxLayout()
        self.seed = QSpinBox()
        self.seed.setRange(1, 2_147_483_647)
        self.seed.setValue(random.randint(1, 999_999))
        new_seed = QPushButton("↻")
        new_seed.setFixedSize(29, 29)
        new_seed.setToolTip("Generate a new random seed")
        new_seed.clicked.connect(lambda: self.seed.setValue(random.randint(1, 2_147_483_647)))
        seed_row.addWidget(self.seed)
        seed_row.addWidget(new_seed)
        form.addRow("Seed", seed_row)
        self.extra_args = QLineEdit()
        self.extra_args.setPlaceholderText("+MY_ARG=value")
        form.addRow("Plusargs", self.extra_args)
        layout.addLayout(form)
        run = QPushButton("▶  Run UVM Test")
        run.setObjectName("primaryButton")
        run.clicked.connect(self.run_test)
        layout.addWidget(run)
        debug_row = QHBoxLayout()
        debug = QPushButton("◆  Debug")
        debug.setToolTip("Stop on the first UVM error and capture the random solver trace")
        debug.clicked.connect(self.debug_test)
        rerun = QPushButton("↻  Same Seed")
        rerun.setToolTip("Re-run the previous test with the identical random seed")
        rerun.clicked.connect(self.rerun_last_seed)
        debug_row.addWidget(debug)
        debug_row.addWidget(rerun)
        layout.addLayout(debug_row)

        layout.addSpacing(14)
        phase_title = QLabel("PHASE NAVIGATOR")
        phase_title.setObjectName("sectionTitle")
        layout.addWidget(phase_title)
        self.phase_tree = QTreeWidget()
        self.phase_tree.setHeaderHidden(True)
        self.phase_tree.setMaximumHeight(205)
        self.phase_names = [
            "build_phase",
            "connect_phase",
            "end_of_elaboration_phase",
            "start_of_simulation_phase",
            "run_phase",
            "extract_phase",
            "check_phase",
            "report_phase",
        ]
        for phase in self.phase_names:
            self.phase_tree.addTopLevelItem(QTreeWidgetItem([f"○  {phase}"]))
        layout.addWidget(self.phase_tree)

        layout.addSpacing(12)
        learn_title = QLabel("LEARNING PATH")
        learn_title.setObjectName("sectionTitle")
        layout.addWidget(learn_title)
        self.learn_tree = QTreeWidget()
        self.learn_tree.setHeaderHidden(True)
        for label, target in (
            ("01  Sequence items", "tb/counter_item.sv"),
            ("02  Sequences", "tb/counter_sequence.sv"),
            ("03  Driver + interface", "tb/counter_driver.sv"),
            ("04  Monitor + analysis", "tb/counter_monitor.sv"),
            ("05  Scoreboard", "tb/counter_scoreboard.sv"),
            ("06  Test + objections", "tb/counter_test.sv"),
        ):
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.ItemDataRole.UserRole, target)
            self.learn_tree.addTopLevelItem(item)
        self.learn_tree.itemDoubleClicked.connect(self._learn_open)
        layout.addWidget(self.learn_tree)
        layout.addStretch()

        setup = QPushButton("Configure Free Toolchain")
        setup.clicked.connect(self.open_toolchains)
        layout.addWidget(setup)
        return panel

    def _build_statusbar(self) -> None:
        self.status_message = QLabel("Ready")
        self.statusBar().addWidget(self.status_message, 1)
        self.cursor_status = QLabel("Ln 1, Col 1 - SystemVerilog")
        self.statusBar().addPermanentWidget(self.cursor_status)

    def _restore_window(self) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        if not self._confirm_unsaved_all():
            event.ignore()
            return
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(1500)
        self.settings.setValue("window/geometry", self.saveGeometry())
        event.accept()

    def _open_start_file(self) -> None:
        for candidate in (self.project_root / "tb" / "tb_top.sv", self.project_root / "rtl" / "counter.sv"):
            if candidate.exists():
                self.open_file(candidate)
                return

    def refresh_project_tree(self) -> None:
        self.project_tree.clear()
        root_item = QTreeWidgetItem([self.config.name.upper()])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(self.project_root))
        root_item.setExpanded(True)
        self.project_tree.addTopLevelItem(root_item)
        hidden = {".git", ".venv", ".svstudio", "__pycache__", "obj_dir", "tools"}

        def add_children(parent_item: QTreeWidgetItem, directory: Path, depth: int = 0) -> None:
            if depth > 8:
                return
            try:
                entries = sorted(directory.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower()))
            except OSError:
                return
            for path in entries:
                if path.name in hidden or (path.name.startswith(".") and path.name != PROJECT_FILE):
                    continue
                if path.is_file() and path.suffix.lower() not in SOURCE_SUFFIXES | {".json", ".md", ".vcd", ".txt"}:
                    continue
                item = QTreeWidgetItem([path.name])
                item.setData(0, Qt.ItemDataRole.UserRole, str(path))
                parent_item.addChild(item)
                if path.is_dir():
                    add_children(item, path, depth + 1)
                    if path.name in {"rtl", "tb"}:
                        item.setExpanded(True)

        add_children(root_item, self.project_root)
        root_item.setExpanded(True)

    def _tree_open(self, item: QTreeWidgetItem) -> None:
        path = Path(item.data(0, Qt.ItemDataRole.UserRole))
        if path.is_file():
            self.open_file(path)

    def _tree_menu(self, position) -> None:
        item = self.project_tree.itemAt(position)
        selected = Path(item.data(0, Qt.ItemDataRole.UserRole)) if item else self.project_root
        base = selected if selected.is_dir() else selected.parent
        menu = QMenu(self)
        menu.addAction("New SystemVerilog File...", lambda: self._new_path(base, False, ".sv"))
        menu.addAction("New Folder...", lambda: self._new_path(base, True))
        if selected != self.project_root:
            menu.addSeparator()
            menu.addAction("Rename...", lambda: self._rename_path(selected))
            menu.addAction("Delete...", lambda: self._delete_path(selected))
        menu.exec(self.project_tree.viewport().mapToGlobal(position))

    def _new_path(self, base: Path, folder: bool, suffix: str = "") -> None:
        name, accepted = QInputDialog.getText(self, "New Folder" if folder else "New File", "Name")
        if not accepted or not name.strip():
            return
        name = name.strip()
        if not folder and suffix and not Path(name).suffix:
            name += suffix
        target = base / name
        try:
            if folder:
                target.mkdir(parents=False, exist_ok=False)
            else:
                target.write_text("`timescale 1ns/1ps\n\n", encoding="utf-8")
        except OSError as error:
            QMessageBox.warning(self, "Could not create item", str(error))
            return
        self.refresh_project_tree()
        if not folder:
            self.open_file(target)

    def _rename_path(self, path: Path) -> None:
        name, accepted = QInputDialog.getText(self, "Rename", "New name", text=path.name)
        if not accepted or not name.strip() or name == path.name:
            return
        try:
            path.rename(path.with_name(name.strip()))
        except OSError as error:
            QMessageBox.warning(self, "Could not rename item", str(error))
        self.refresh_project_tree()

    def _delete_path(self, path: Path) -> None:
        answer = QMessageBox.question(
            self,
            "Delete item",
            f"Delete {path.name}? This cannot be undone.",
            QMessageBox.StandardButton.Delete | QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Delete:
            return
        try:
            path.rmdir() if path.is_dir() else path.unlink()
        except OSError as error:
            QMessageBox.warning(self, "Could not delete item", f"Only empty folders can be deleted.\n\n{error}")
        self.refresh_project_tree()

    def open_file(self, path: Path, line: int | None = None) -> None:
        path = path.resolve()
        if path.suffix.lower() in {".vcd"}:
            self._load_vcd(path)
            return
        if path in self.editors:
            editor = self.editors[path]
            self.editor_tabs.setCurrentWidget(editor)
            if line:
                editor.go_to_line(line)
            return
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            QMessageBox.warning(self, "Could not open file", str(error))
            return
        editor = CodeEditor(path)
        editor.setPlainText(content)
        editor.moveCursor(QTextCursor.MoveOperation.Start)
        editor.ensureCursorVisible()
        editor.document().setModified(False)
        editor.document().modificationChanged.connect(lambda modified, value=editor: self._modified(value, modified))
        editor.cursorPositionChanged.connect(self._update_cursor_status)
        self.editors[path] = editor
        self.editor_tabs.addTab(editor, path.name)
        self.editor_tabs.setCurrentWidget(editor)
        if line:
            editor.go_to_line(line)

    def current_editor(self) -> CodeEditor | None:
        widget = self.editor_tabs.currentWidget()
        return widget if isinstance(widget, CodeEditor) else None

    def save_current(self) -> None:
        editor = self.current_editor()
        if editor:
            self._save_editor(editor)

    def save_all(self) -> None:
        for editor in self.editors.values():
            if editor.document().isModified():
                self._save_editor(editor)

    def _save_editor(self, editor: CodeEditor) -> bool:
        try:
            editor.path.write_text(editor.toPlainText(), encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Save failed", str(error))
            return False
        editor.document().setModified(False)
        self.status_message.setText(f"Saved {editor.path.name}")
        return True

    def close_editor(self, index: int) -> None:
        editor = self.editor_tabs.widget(index)
        if isinstance(editor, CodeEditor) and editor.document().isModified():
            answer = QMessageBox.question(
                self,
                "Unsaved changes",
                f"Save changes to {editor.path.name}?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save and not self._save_editor(editor):
                return
        self.editor_tabs.removeTab(index)
        if isinstance(editor, CodeEditor):
            self.editors.pop(editor.path, None)
            editor.deleteLater()

    def _confirm_unsaved_all(self) -> bool:
        dirty = [editor for editor in self.editors.values() if editor.document().isModified()]
        if not dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            f"Save changes in {len(dirty)} open file(s)?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return all(self._save_editor(editor) for editor in dirty)
        return True

    def _modified(self, editor: CodeEditor, modified: bool) -> None:
        index = self.editor_tabs.indexOf(editor)
        if index >= 0:
            self.editor_tabs.setTabText(index, editor.path.name + (" *" if modified else ""))

    def _editor_changed(self) -> None:
        self._update_cursor_status()

    def _update_cursor_status(self) -> None:
        editor = self.current_editor()
        if editor:
            cursor = editor.textCursor()
            relative = editor.path.relative_to(self.project_root) if editor.path.is_relative_to(self.project_root) else editor.path
            self.cursor_status.setText(
                f"{relative} - Ln {cursor.blockNumber() + 1}, Col {cursor.columnNumber() + 1} - SystemVerilog"
            )

    def find_text(self) -> None:
        editor = self.current_editor()
        if not editor:
            return
        text, accepted = QInputDialog.getText(self, "Find", "Search in current file")
        if accepted and text and not editor.find(text):
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            editor.setTextCursor(cursor)
            if not editor.find(text):
                self.status_message.setText(f'No match for "{text}"')

    def _discover_tests(self) -> None:
        tests = set()
        pattern = re.compile(r"\bclass\s+(\w+_test)\s+extends\s+\w+\b")
        candidates = set(self.config.source_files(self.project_root))
        for include_dir in self.config.include_dirs:
            directory = self.project_root / include_dir
            if directory.is_dir():
                candidates.update(directory.rglob("*.sv"))
                candidates.update(directory.rglob("*.svh"))
        for source in sorted(candidates):
            try:
                tests.update(pattern.findall(source.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                pass
        if not tests:
            tests.add(self.config.test)
        if self.config.test not in tests:
            learning_tests = sorted(name for name in tests if name.endswith("learning_test"))
            self.config.test = learning_tests[0] if learning_tests else sorted(tests)[0]

    def _engine_changed(self) -> None:
        self.config.simulator = "auto"
        self.config.save(self.project_root)
        self._update_engine_status()

    def _update_engine_status(self) -> None:
        engine = choose_toolchain("auto")
        self.status_message.setText("Ready" if engine.ready else "Free engine setup required")

    def run_test(self) -> None:
        self._start_test()

    def debug_test(self) -> None:
        self._start_test()

    def rerun_last_seed(self) -> None:
        self._start_test(reuse_seed=True)

    def _start_test(self, reuse_seed: bool = False) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.save_all()
        self._discover_tests()
        self.config.simulator = "auto"
        run_seed = self._last_seed if reuse_seed and self._last_seed is not None else random.randint(1, 2_147_483_647)
        self._last_seed = run_seed
        self.config.plusargs = [
            "+UVM_VERBOSITY=UVM_MEDIUM",
            "+UVM_NO_RELNOTES",
            f"+verilator+seed+{run_seed}",
        ]
        self.config.save(self.project_root)
        try:
            plan = build_plan(self.config, self.project_root)
        except RunnerError as error:
            if "not installed" in str(error) or "not ready" in str(error):
                answer = QMessageBox.question(
                    self,
                    "Free engine setup",
                    "SV Studio needs its free local Verilator/UVM engine. Install it now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self._start_free_engine_setup()
            else:
                QMessageBox.warning(self, "Run unavailable", str(error))
            return
        self.console.clear()
        self.bottom_tabs.setCurrentIndex(0)
        self.action_run.setEnabled(False)
        self.action_stop.setEnabled(True)
        self._run_started = time.monotonic()
        self.worker = ProcessWorker(plan)
        self.worker.output.connect(self._simulation_output)
        self.worker.step_started.connect(self._simulation_step)
        self.worker.completed.connect(lambda success, message, value=plan: self._simulation_done(success, message, value.waveform_path))
        self.worker.start()

    def _start_free_engine_setup(self) -> None:
        script = Path(__file__).resolve().parent.parent / "tools" / "setup_open_source_uvm.ps1"
        if not script.exists():
            QMessageBox.warning(self, "Setup unavailable", "The free engine installer was not found.")
            return
        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoExit",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-ProjectRoot",
                    str(self.project_root),
                ],
                cwd=self.project_root,
            )
        except OSError as error:
            QMessageBox.warning(self, "Setup unavailable", str(error))
            return
        QMessageBox.information(
            self,
            "Setup started",
            "The free engine is installing. When the terminal says Complete, press Run again.",
        )

    def stop_test(self) -> None:
        if self.worker:
            self.worker.stop()
            self.status_message.setText("Stopping...")

    def _simulation_output(self, text: str) -> None:
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(text)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def _simulation_step(self, step: str) -> None:
        self.status_message.setText(step)

    def _simulation_done(self, success: bool, message: str, waveform_path: Path) -> None:
        self.action_run.setEnabled(True)
        self.action_stop.setEnabled(False)
        self.status_message.setText(("Passed - " if success else "Failed - ") + message)
        if waveform_path.exists():
            try:
                self._load_vcd(waveform_path)
            except (OSError, ValueError) as error:
                self._append_console(f"\nWaveform could not be loaded: {error}\n")
        if not success:
            self.bottom_tabs.setCurrentIndex(0)
        self.worker = None

    def _append_console(self, text: str) -> None:
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(text)

    def _parse_problem(self, text: str) -> None:
        severity_match = UVM_LINE_RE.search(text)
        source_match = SOURCE_RE.search(text)
        if severity_match and severity_match.group(1) in {"WARNING", "ERROR", "FATAL"}:
            severity = severity_match.group(1)
            file = source_match.group("file") if source_match else ""
            line = int(source_match.group("line")) if source_match else 0
            self._add_problem(severity, file, line, text.strip())
        for match in VERILATOR_ERROR_RE.finditer(text):
            self._add_problem(match.group("severity").upper(), match.group("file"), int(match.group("line")), match.group("message"))

    def _add_problem(self, severity: str, file: str, line: int, message: str) -> None:
        key = (file, line, message)
        if key in self._problem_keys:
            return
        self._problem_keys.add(key)
        row = self.problems.rowCount()
        self.problems.insertRow(row)
        severity_item = QTableWidgetItem(severity)
        severity_item.setForeground(QColor(COLORS["red"] if severity in {"ERROR", "FATAL"} else COLORS["orange"]))
        self.problems.setItem(row, 0, severity_item)
        location = QTableWidgetItem(f"{file}:{line}" if file else "Simulation")
        location.setData(Qt.ItemDataRole.UserRole, (file, line))
        self.problems.setItem(row, 1, location)
        self.problems.setItem(row, 2, QTableWidgetItem(message))
        self.bottom_tabs.setTabText(2, f"Problems ({self.problems.rowCount()})")

    def _open_problem(self, row: int, _column: int = 0) -> None:
        item = self.problems.item(row, 1)
        if not item:
            return
        file, line = item.data(Qt.ItemDataRole.UserRole) or ("", 0)
        if not file:
            return
        path = Path(file)
        if not path.is_absolute():
            direct = self.project_root / path
            if direct.exists():
                path = direct
            else:
                matches = list(self.project_root.rglob(path.name))
                if matches:
                    path = matches[0]
        if path.exists():
            self.open_file(path, line)

    def _reset_phases(self) -> None:
        for index, phase in enumerate(self.phase_names):
            item = self.phase_tree.topLevelItem(index)
            item.setText(0, f"○  {phase}")
            item.setForeground(0, QColor(COLORS["muted"]))

    def _set_phase(self, active: int) -> None:
        for index, phase in enumerate(self.phase_names):
            item = self.phase_tree.topLevelItem(index)
            if index < active:
                item.setText(0, f"✓  {phase}")
                item.setForeground(0, QColor(COLORS["green"]))
            elif index == active:
                item.setText(0, f"●  {phase}")
                item.setForeground(0, QColor(COLORS["blue"]))

    def _finish_phases(self) -> None:
        for index, phase in enumerate(self.phase_names):
            item = self.phase_tree.topLevelItem(index)
            item.setText(0, f"✓  {phase}")
            item.setForeground(0, QColor(COLORS["green"]))

    def _load_vcd(self, path: Path) -> None:
        self.waveform.load_file(path)
        self.bottom_tabs.setCurrentIndex(1)
        self.bottom_tabs.setTabText(1, f"Waveform - {path.name}")

    def open_solver_log(self) -> None:
        path = self.project_root / ".svstudio" / "solver.log"
        if path.exists():
            self.open_file(path)
        else:
            QMessageBox.information(
                self,
                "No solver log yet",
                "Run a constrained-random test with Debug (F6). The Z3 exchange will be written here.",
            )

    def open_vcd(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Open VCD Waveform", str(self.project_root), "VCD waveform (*.vcd)")
        if selected:
            self._load_vcd(Path(selected))

    def _learn_open(self, item: QTreeWidgetItem) -> None:
        target = item.data(0, Qt.ItemDataRole.UserRole)
        if target:
            path = self.project_root / target
            if path.exists():
                self.open_file(path)

    def open_toolchains(self) -> None:
        dialog = ToolchainDialog(self.project_root, self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            index = self.engine_combo.findData(self.config.simulator)
            if index >= 0:
                self.engine_combo.setCurrentIndex(index)
            self._update_engine_status()

    def open_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Open SystemVerilog Project", str(self.project_root.parent))
        if not selected:
            return
        if not self._confirm_unsaved_all():
            return
        self._switch_project(Path(selected))

    def new_project(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Choose an Empty Project Folder", str(self.project_root.parent))
        if not selected:
            return
        root = Path(selected)
        try:
            (root / "rtl").mkdir(exist_ok=True)
            (root / "tb").mkdir(exist_ok=True)
            ProjectConfig(name=root.name).save(root)
            starter = root / "rtl" / "design.sv"
            if not starter.exists():
                starter.write_text(
                    """`timescale 1ns/1ps

module simple_adder (
    input  logic [7:0] a,
    input  logic [7:0] b,
    output logic [7:0] result
);
    assign result = a + b;
endmodule
""",
                    encoding="utf-8",
                )
            top = root / "tb" / "tb_top.sv"
            if not top.exists():
                top.write_text(
                    """`timescale 1ns/1ps

module tb_top;
    logic [7:0] a;
    logic [7:0] b;
    logic [7:0] result;

    simple_adder dut (.*);

    initial begin
        $dumpfile(".svstudio/waves.vcd");
        $dumpvars(0, tb_top);
        a = 8'd1;  b = 8'd2;  #10;
        a = 8'd10; b = 8'd20; #10;
        a = 8'hff; b = 8'd1;  #10;
        $finish;
    end
endmodule
""",
                    encoding="utf-8",
                )
        except OSError as error:
            QMessageBox.warning(self, "Could not create project", str(error))
            return
        self._switch_project(root)

    def _switch_project(self, root: Path) -> None:
        while self.editor_tabs.count():
            self.editor_tabs.removeTab(0)
        self.editors.clear()
        self.project_root = root.resolve()
        self.config = ProjectConfig.load(self.project_root)
        self.setWindowTitle(f"SV Studio - {self.config.name}")
        self.refresh_project_tree()
        self._discover_tests()
        self._update_engine_status()
        self._open_start_file()

    def show_uvm_guide(self) -> None:
        QMessageBox.information(
            self,
            "Open-source UVM workflow",
            "1. Open Project → Toolchains.\n"
            "2. Run Set Up Free Toolchain (Verilator + CHIPS Alliance UVM).\n"
            "3. Choose a uvm_test, seed, and verbosity.\n"
            "4. Press F5 to run, or F6 to stop on the first UVM error.\n"
            "5. Use Ctrl+F5 to reproduce the exact seed.\n"
            "6. Double-click errors to jump to source, then inspect Debug and Waveform.\n\n"
            "Constrained randomization uses the bundled setup's Z3 solver. Verilator UVM support is actively improving; some advanced constraints may still be unsupported.",
        )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About SV Studio",
            "SV Studio 0.4.0\n\nA minimal, local SystemVerilog and UVM IDE.\n"
            "Designed for the free Verilator + CHIPS Alliance UVM toolchain.",
        )
