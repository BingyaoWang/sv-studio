import os
import shutil
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from svstudio.app import MainWindow


def test_main_window_runs_demo_and_loads_waveform(tmp_path: Path):
    source = Path(__file__).resolve().parents[1] / "examples" / "uvm_counter"
    project = tmp_path / "uvm_counter"
    shutil.copytree(source, project)
    app = QApplication.instance() or QApplication([])
    window = MainWindow(project)
    assert window.test_combo.findText("counter_random_test") >= 0
    demo_index = window.engine_combo.findData("demo")
    window.engine_combo.setCurrentIndex(demo_index)
    window.run_test()

    deadline = time.monotonic() + 8
    while window.worker is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)

    assert window.worker is None
    assert "UVM_ERROR : 0" in window.console.toPlainText()
    assert len(window.waveform.data.signals) == 4
    assert window.problems.rowCount() == 0
    assert window.action_rerun.isEnabled()
    first_seed = window._last_seed
    window.rerun_last_seed()
    deadline = time.monotonic() + 8
    while window.worker is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert window._last_seed == first_seed
    assert f"seed={first_seed}" in window.debug_panel.reproduction
    window.close()
