from pathlib import Path

from svstudio.project import ProjectConfig
from svstudio.runner import build_plan, windows_to_wsl


def test_demo_build_plan_needs_no_toolchain(tmp_path: Path):
    config = ProjectConfig(simulator="demo", waveform=".svstudio/test.vcd")
    plan = build_plan(config, tmp_path)
    assert plan.engine.key == "demo"
    assert plan.steps == []
    assert plan.waveform_path == tmp_path / ".svstudio" / "test.vcd"


def test_windows_path_conversion():
    converted = windows_to_wsl(Path("C:/work/lab"))
    assert converted.lower().endswith("/work/lab")
