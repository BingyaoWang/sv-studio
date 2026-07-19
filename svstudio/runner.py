from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .project import ProjectConfig
from .vcd import write_demo_vcd


class RunnerError(RuntimeError):
    pass


@dataclass
class Toolchain:
    key: str
    label: str
    executable: str = ""
    ready: bool = False
    note: str = ""
    solver_ready: bool = False


@dataclass
class CommandStep:
    label: str
    program: str
    args: list[str]
    cwd: Path


@dataclass
class SimulationPlan:
    engine: Toolchain
    steps: list[CommandStep]
    waveform_path: Path


def _run_probe(command: list[str], timeout: float = 3.0) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0, result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False, ""


def detect_toolchains() -> list[Toolchain]:
    chains: list[Toolchain] = []
    native_verilator = os.environ.get("SVSTUDIO_VERILATOR") or shutil.which("verilator")
    chains.append(
        Toolchain(
            "verilator",
            "Verilator (native)",
            native_verilator or "",
            bool(native_verilator),
            "Open-source SystemVerilog compiler" + (" · Z3 ready" if shutil.which("z3") else " · Z3 missing"),
            bool(shutil.which("z3")),
        )
    )

    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
    wsl_ready = False
    version = ""
    if wsl:
        probe = (
            'export PATH="$HOME/.local/sv-studio/verilator/bin:$PATH"; '
            "command -v verilator >/dev/null && verilator --version; "
            "command -v z3 >/dev/null && z3 --version || echo 'Z3 missing'"
        )
        wsl_ready, version = _run_probe([wsl, "-d", "Ubuntu", "--", "bash", "-lc", probe], 6)
    wsl_solver_ready = "Z3 version" in version
    chains.append(
        Toolchain(
            "wsl-verilator",
            "Verilator + UVM (WSL)",
            wsl or "",
            wsl_ready,
            " · ".join(version.splitlines()[-2:]) if version else ("WSL detected; setup required" if wsl else "WSL not found"),
            wsl_solver_ready,
        )
    )

    iverilog = shutil.which("iverilog")
    chains.append(
        Toolchain(
            "iverilog",
            "Icarus Verilog (basic SV)",
            iverilog or "",
            bool(iverilog and shutil.which("vvp")),
            "Useful for basic RTL; full UVM is not supported",
            False,
        )
    )
    chains.append(
        Toolchain(
            "demo",
            "Learning Demo Engine",
            ready=True,
            note="No compiler required; demonstrates the IDE workflow",
            solver_ready=False,
        )
    )
    return chains


def choose_toolchain(preference: str = "auto") -> Toolchain:
    chains = detect_toolchains()
    by_key = {chain.key: chain for chain in chains}
    if preference != "auto":
        return by_key.get(preference, by_key["demo"])
    for key in ("wsl-verilator", "verilator", "iverilog"):
        if by_key[key].ready:
            return by_key[key]
    return by_key["demo"]


def windows_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if drive:
        tail = resolved.as_posix().split(":", 1)[1]
        return f"/mnt/{drive}{tail}"
    return resolved.as_posix()


def _uvm_source(config: ProjectConfig, root: Path) -> Path:
    configured = config.resolved_uvm_home(root)
    candidates = [
        configured,
        root / "tools" / "uvm-verilator",
        root / "tools" / "uvm",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if (candidate / "src" / "uvm.sv").exists():
            return candidate / "src"
        if (candidate / "uvm.sv").exists():
            return candidate
    raise RunnerError(
        "The open-source UVM library is not installed yet. Open Toolchains and run "
        "the free Verilator + UVM setup first."
    )


def _verilator_arguments(config: ProjectConfig, root: Path, wsl: bool) -> tuple[list[str], Path, str]:
    sources = config.source_files(root)
    if not sources:
        raise RunnerError("No SystemVerilog source files match this project's source patterns.")
    uvm_src = _uvm_source(config, root)
    build_dir = root / ".svstudio" / "obj_dir"
    build_dir.mkdir(parents=True, exist_ok=True)

    convert = windows_to_wsl if wsl else lambda path: str(path.resolve())
    args = [
        "--cc",
        "--exe",
        "--main",
        "--timing",
        "--trace",
        "--trace-structs",
        "--coverage",
        "-Mdir",
        convert(build_dir),
        "--prefix",
        "svsim",
        "-o",
        "svsim",
        "--top-module",
        config.top,
        "--timescale",
        "1ns/1ps",
        "--error-limit",
        "100",
        "-DUVM_NO_DPI",
        "-Wno-fatal",
        "-Wno-lint",
        "-Wno-style",
        "-Wno-SYMRSVDWORD",
        "-Wno-IGNOREDRETURN",
        "-Wno-ZERODLY",
    ]
    for define in config.defines:
        args.append(f"-D{define}")
    include_dirs = [uvm_src, *(root / item for item in config.include_dirs)]
    for include_dir in include_dirs:
        args.append(f"+incdir+{convert(include_dir)}")
    args.append(convert(uvm_src / "uvm.sv"))
    args.extend(convert(source) for source in sources)
    return args, build_dir, convert(build_dir)


def build_plan(config: ProjectConfig, root: Path, preference: str | None = None) -> SimulationPlan:
    engine = choose_toolchain(preference or config.simulator)
    waveform = root / config.waveform
    waveform.parent.mkdir(parents=True, exist_ok=True)
    plusargs = [
        f"+UVM_TESTNAME={config.test}",
        *config.plusargs,
    ]

    if engine.key == "demo":
        return SimulationPlan(engine, [], waveform)

    if not engine.ready:
        raise RunnerError(f"{engine.label} is not ready. Open Toolchains to finish setup.")

    if engine.key == "wsl-verilator":
        args, build_dir, wsl_build = _verilator_arguments(config, root, True)
        wsl_root = windows_to_wsl(root)
        prefix = (
            'export PATH="$HOME/.local/sv-studio/verilator/bin:$PATH"; '
            f"cd {shlex.quote(wsl_root)}; "
        )
        compile_line = prefix + "verilator " + " ".join(shlex.quote(arg) for arg in args)
        make_line = prefix + f"make -j$(nproc) -C {shlex.quote(wsl_build)} -f svsim.mk"
        run_line = prefix + shlex.quote(f"{wsl_build}/svsim") + " " + " ".join(
            shlex.quote(arg) for arg in plusargs
        )
        program = engine.executable
        common = ["-d", "Ubuntu", "--", "bash", "-lc"]
        steps = [
            CommandStep("Compile SystemVerilog + UVM", program, [*common, compile_line], root),
            CommandStep("Build simulation", program, [*common, make_line], root),
            CommandStep("Run UVM test", program, [*common, run_line], root),
        ]
        return SimulationPlan(engine, steps, waveform)

    if engine.key == "verilator":
        args, build_dir, _ = _verilator_arguments(config, root, False)
        make = shutil.which("make") or shutil.which("mingw32-make")
        if not make:
            raise RunnerError("Verilator was found, but Make is missing. The WSL setup is recommended on Windows.")
        steps = [
            CommandStep("Compile SystemVerilog + UVM", engine.executable, args, root),
            CommandStep("Build simulation", make, ["-j", "-C", str(build_dir), "-f", "svsim.mk"], root),
            CommandStep("Run UVM test", str(build_dir / "svsim"), plusargs, root),
        ]
        return SimulationPlan(engine, steps, waveform)

    if engine.key == "iverilog":
        if any("uvm" in source.name.lower() for source in config.source_files(root)):
            raise RunnerError("Icarus supports basic SystemVerilog but cannot run this UVM class library.")
        output = root / ".svstudio" / "simv"
        args = ["-g2012", "-s", config.top, "-o", str(output)]
        args.extend(f"-I{root / item}" for item in config.include_dirs)
        args.extend(str(path) for path in config.source_files(root))
        steps = [
            CommandStep("Compile SystemVerilog", engine.executable, args, root),
            CommandStep("Run simulation", shutil.which("vvp") or "vvp", [str(output), *plusargs], root),
        ]
        return SimulationPlan(engine, steps, waveform)

    raise RunnerError(f"Unsupported simulator: {engine.label}")


class ProcessWorker(QThread):
    output = Signal(str)
    step_started = Signal(str)
    completed = Signal(bool, str)

    def __init__(self, plan: SimulationPlan):
        super().__init__()
        self.plan = plan
        self._process: subprocess.Popen[str] | None = None
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run(self) -> None:
        if self.plan.engine.key == "demo":
            self._run_demo()
            return
        for step in self.plan.steps:
            if self._stop_requested:
                self.completed.emit(False, "Simulation stopped")
                return
            self.step_started.emit(step.label)
            self.output.emit(f"\n› {step.label}\n")
            self.output.emit("$ " + subprocess.list2cmdline([step.program, *step.args]) + "\n")
            try:
                self._process = subprocess.Popen(
                    [step.program, *step.args],
                    cwd=step.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                assert self._process.stdout is not None
                for line in self._process.stdout:
                    self.output.emit(line)
                return_code = self._process.wait()
            except OSError as error:
                self.completed.emit(False, str(error))
                return
            if return_code != 0:
                self.completed.emit(False, f"{step.label} failed with exit code {return_code}")
                return
        self.completed.emit(True, "UVM test completed")

    def _run_demo(self) -> None:
        self.step_started.emit("Learning Demo Engine")
        demo_lines = [
            "SV Studio Demo Engine — install the free Verilator toolchain for real compilation.\n",
            "UVM_INFO @ 0: reporter [RNTST] Running test counter_smoke_test...\n",
            "UVM_INFO tb/counter_test.sv(24) @ 0: uvm_test_top [TEST] Build phase\n",
            "UVM_INFO tb/counter_driver.sv(31) @ 15: uvm_test_top.env.agent.driver [DRV] Reset complete\n",
            "UVM_INFO tb/counter_sequence.sv(22) @ 25: uvm_test_top.env.agent.sequencer@@seq [SEQ] Starting 8 transactions\n",
            "UVM_INFO tb/counter_scoreboard.sv(43) @ 40: uvm_test_top.env.scoreboard [MATCH] expected=1 actual=1\n",
            "UVM_INFO tb/counter_scoreboard.sv(43) @ 50: uvm_test_top.env.scoreboard [MATCH] expected=2 actual=2\n",
            "UVM_INFO tb/counter_scoreboard.sv(43) @ 60: uvm_test_top.env.scoreboard [MATCH] expected=3 actual=3\n",
            "UVM_INFO tb/counter_scoreboard.sv(43) @ 70: uvm_test_top.env.scoreboard [MATCH] expected=4 actual=4\n",
            "UVM_INFO tb/counter_test.sv(36) @ 125: uvm_test_top [TEST] Counter smoke test passed\n",
            "\n--- UVM Report Summary ---\n",
            "UVM_INFO : 10\nUVM_WARNING : 0\nUVM_ERROR : 0\nUVM_FATAL : 0\n",
        ]
        for line in demo_lines:
            if self._stop_requested:
                self.completed.emit(False, "Simulation stopped")
                return
            self.output.emit(line)
            time.sleep(0.08)
        write_demo_vcd(self.plan.waveform_path)
        self.completed.emit(True, "Demo UVM test completed")
