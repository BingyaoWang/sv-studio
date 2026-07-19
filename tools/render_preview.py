"""Render an offscreen SV Studio preview for visual regression checks."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from svstudio.app import MainWindow


def main() -> int:
    root = ROOT
    app = QApplication.instance() or QApplication([])
    temporary = tempfile.TemporaryDirectory()
    project = Path(temporary.name) / "uvm_counter"
    shutil.copytree(root / "examples" / "uvm_counter", project)
    window = MainWindow(project)
    window.show()
    for _ in range(12):
        app.processEvents()
        time.sleep(0.03)
    output = root / ".svstudio" / "ui-preview.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output)):
        return 1
    print(output)

    demo_index = window.engine_combo.findData("demo")
    window.engine_combo.setCurrentIndex(demo_index)
    window.run_test()
    deadline = time.monotonic() + 8
    while window.worker is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    wave_output = root / ".svstudio" / "wave-preview.png"
    if not window.grab().save(str(wave_output)):
        return 1
    print(wave_output)
    window.bottom_tabs.setCurrentIndex(3)
    app.processEvents()
    debug_output = root / ".svstudio" / "debug-preview.png"
    if not window.grab().save(str(debug_output)):
        return 1
    print(debug_output)
    window.close()
    temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
