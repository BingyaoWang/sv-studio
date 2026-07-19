import json
from pathlib import Path

from svstudio.project import ProjectConfig


def test_project_round_trip(tmp_path: Path):
    config = ProjectConfig(name="Lab", top="tb", sources=["rtl/*.sv"])
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "dut.sv").write_text("module dut; endmodule", encoding="utf-8")
    config.save(tmp_path)

    loaded = ProjectConfig.load(tmp_path)
    assert loaded.name == "Lab"
    assert loaded.top == "tb"
    assert [path.name for path in loaded.source_files(tmp_path)] == ["dut.sv"]
    saved = json.loads((tmp_path / ".svstudio.json").read_text(encoding="utf-8"))
    assert saved["name"] == "Lab"
    assert "simulator" not in saved
    assert "uvm_home" not in saved
    assert "plusargs" not in saved


def test_example_project_sources_are_explicit():
    root = Path(__file__).resolve().parents[1] / "examples" / "uvm_counter"
    config = ProjectConfig.load(root)
    assert [path.name for path in config.source_files(root)] == ["counter.sv", "tb_top.sv"]
