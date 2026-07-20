import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from svstudio.app import MainWindow
from svstudio.resources import application_icon_path
from svstudio.vcd import write_demo_vcd


def test_main_window_is_minimal_and_loads_waveform(tmp_path: Path):
    source = Path(__file__).resolve().parents[1] / "examples" / "uvm_counter"
    project = tmp_path / "uvm_counter"
    shutil.copytree(source, project)
    app = QApplication.instance() or QApplication([])
    window = MainWindow(project)
    assert window.action_run.text() == "Run"
    assert window.bottom_tabs.count() == 2
    assert window.bottom_tabs.tabText(0) == "Console"
    assert window.bottom_tabs.tabText(1) == "Waveform"
    assert not hasattr(window, "engine_combo")
    assert not hasattr(window, "test_combo")
    assert application_icon_path().is_file()
    assert not QIcon(str(application_icon_path())).isNull()

    waveform = project / ".svstudio" / "test.vcd"
    write_demo_vcd(waveform)
    window._load_vcd(waveform)
    assert len(window.waveform.data.signals) == 4
    assert window.bottom_tabs.currentIndex() == 1
    window.close()
