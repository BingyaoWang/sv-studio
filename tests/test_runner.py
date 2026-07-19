from pathlib import Path

from svstudio.project import ProjectConfig
from svstudio.runner import CommandStep, ProcessWorker, SimulationPlan, Toolchain, _uvm_source, project_uses_uvm, windows_to_wsl


def test_project_mode_is_detected_from_source(tmp_path: Path):
    rtl = tmp_path / "rtl"
    tb = tmp_path / "tb"
    rtl.mkdir()
    tb.mkdir()
    (rtl / "design.sv").write_text("module design; endmodule\n", encoding="utf-8")
    config = ProjectConfig(sources=["rtl/*.sv", "tb/*.sv"])

    assert not project_uses_uvm(config, tmp_path)

    (tb / "tb_top.sv").write_text(
        "import uvm_pkg::*; initial run_test();\n",
        encoding="utf-8",
    )
    assert project_uses_uvm(config, tmp_path)


def test_project_free_uvm_wins_over_configured_commercial_path(tmp_path: Path):
    project_uvm = tmp_path / "tools" / "uvm-verilator" / "src"
    project_uvm.mkdir(parents=True)
    (project_uvm / "uvm.sv").write_text("package uvm_pkg; endpackage\n", encoding="utf-8")
    commercial_uvm = tmp_path / "commercial" / "src"
    commercial_uvm.mkdir(parents=True)
    (commercial_uvm / "uvm.sv").write_text("package uvm_pkg; endpackage\n", encoding="utf-8")

    config = ProjectConfig(uvm_home=str(commercial_uvm.parent))

    assert _uvm_source(config, tmp_path) == project_uvm


def test_windows_path_conversion():
    converted = windows_to_wsl(Path("C:/work/lab"))
    assert converted.lower().endswith("/work/lab")


def test_wsl_encoding_noise_is_removed_from_console():
    assert ProcessWorker._clean_output_line("w\x00s\x00l\x00:\x00 warning\n") == ""
    assert ProcessWorker._clean_output_line("N/e\x01c localhost \ufffd\n") == ""
    assert ProcessWorker._clean_output_line("UVM_ERROR useful message\n") == "UVM_ERROR useful message\n"


def test_uvm_library_boilerplate_is_hidden(tmp_path: Path):
    plan = SimulationPlan(Toolchain("test", "test", ready=True), [], tmp_path / ".svstudio" / "waves.vcd", True)
    worker = ProcessWorker(plan)
    step = CommandStep("Run UVM test", "", [], tmp_path)

    assert not worker._should_show_line(step, "UVM_WARNING tools/uvm-verilator/src/base/uvm_root.svh internal warning\n")
    assert not worker._should_show_line(step, "  ******** IMPORTANT RELEASE NOTES ********\n")
    assert worker._should_show_line(step, "UVM_INFO tb/test.sv [ALU_SUMMARY] passed=10\n")
    assert worker._should_show_line(step, "UVM_ERROR tools/uvm-verilator/internal.svh failure\n")
