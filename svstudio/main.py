from __future__ import annotations

import sys
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .app import MainWindow
from .project import PROJECT_FILE


def default_project() -> Path:
    package_root = Path(__file__).resolve().parent.parent
    example = package_root / "examples" / "uvm_counter"
    if getattr(sys, "frozen", False) and (example / PROJECT_FILE).exists():
        documents = Path.home() / "Documents"
        project_home = documents if documents.exists() else Path.home()
        target = project_home / "SVStudioProjects" / "UVM Counter Lab"
        if not (target / PROJECT_FILE).exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(example, target, dirs_exist_ok=True)
        return target
    if (example / PROJECT_FILE).exists():
        return example
    return Path.cwd()


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("SV Studio")
    app.setOrganizationName("SVStudio")
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#111418"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8edf2"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#13171c"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e8edf2"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#1d222a"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e8edf2"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#264d43"))
    app.setPalette(palette)
    project = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else default_project()
    window = MainWindow(project)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
