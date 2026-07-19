import hashlib
import os
import re
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
    uses_uvm: bool = False


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
            "Open-source SystemVerilog compiler" + (" - Z3 ready" if shutil.which("z3") else " - Z3 missing"),
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
        # A cold WSL boot can exceed six seconds on Windows even when the
        # installed engine is healthy. Wait long enough to avoid a false
        # "setup required" result on the first click of Run.
        wsl_ready, version = _run_probe([wsl, "-d", "Ubuntu", "--", "bash", "-lc", probe], 20)
    wsl_solver_ready = "Z3 version" in version
    chains.append(
        Toolchain(
            "wsl-verilator",
            "Verilator + UVM (WSL)",
            wsl or "",
            wsl_ready,
            " - ".join(version.splitlines()[-2:]) if version else ("WSL detected; setup required" if wsl else "WSL not found"),
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
    for key in ("wsl-verilator", "verilator"):
        if by_key[key].ready:
            return by_key[key]
    return Toolchain(
        "unavailable",
        "Free Verilator engine",
        ready=False,
        note="The one-time free engine setup has not completed yet.",
    )


def windows_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if drive:
        tail = resolved.as_posix().split(":", 1)[1]
        return f"/mnt/{drive}{tail}"
    return resolved.as_posix()


def _uvm_source(config: ProjectConfig, root: Path) -> Path:
    candidates = [
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
        "The free UVM library is not installed in this project yet. Run the one-time "
        "SV Studio engine setup, then press Run again."
    )


def project_uses_uvm(config: ProjectConfig, root: Path) -> bool:
    """Detect UVM from project source without exposing a mode switch to users."""
    marker = re.compile(r"\b(?:uvm_pkg|uvm_component|uvm_test|run_test)\b|`uvm_")
    candidates = set(config.source_files(root))
    for include_dir in config.include_dirs:
        directory = root / include_dir
        if directory.is_dir():
            candidates.update(directory.rglob("*.sv"))
            candidates.update(directory.rglob("*.svh"))
    for source in candidates:
        try:
            if marker.search(source.read_text(encoding="utf-8", errors="ignore")):
                return True
        except OSError:
            continue
    return False


def _verilator_arguments(
    config: ProjectConfig,
    root: Path,
    wsl: bool,
    uses_uvm: bool,
) -> tuple[list[str], Path, str]:
    sources = config.source_files(root)
    if not sources:
        raise RunnerError("No SystemVerilog source files match this project's source patterns.")
    uvm_src = _uvm_source(config, root) if uses_uvm else None
    build_dir = root / ".svstudio" / "obj_dir"
    build_dir.mkdir(parents=True, exist_ok=True)

    convert = windows_to_wsl if wsl else lambda path: str(path.resolve())
    if wsl:
        # Building the generated UVM C++ directly under /mnt/c is extremely
        # slow because large precompiled headers cross the Windows/WSL file
        # boundary. Keep only reproducible intermediates in WSL-local storage;
        # the simulation still runs from the project root, so VCD output stays
        # alongside the Windows project.
        build_key = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
        # /var/tmp is Linux-native and survives WSL instance shutdowns. Plain
        # /tmp may be cleared between two clicks of Run in the desktop app.
        engine_build_dir = f"/var/tmp/svstudio-{build_key}/obj_dir"
    else:
        engine_build_dir = convert(build_dir)
    args = [
        "--cc",
        "--exe",
        "--main",
        "--timing",
        "--trace",
        "--trace-structs",
        "--coverage",
        "-Mdir",
        engine_build_dir,
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
        "-Wno-fatal",
        "-Wno-lint",
        "-Wno-style",
        "-Wno-SYMRSVDWORD",
        "-Wno-IGNOREDRETURN",
        "-Wno-ZERODLY",
    ]
    if uses_uvm:
        args.append("-DUVM_NO_DPI")
    for define in config.defines:
        args.append(f"-D{define}")
    include_dirs = [*(root / item for item in config.include_dirs)]
    if uvm_src:
        include_dirs.insert(0, uvm_src)
    for include_dir in include_dirs:
        args.append(f"+incdir+{convert(include_dir)}")
    if uvm_src:
        args.append(convert(uvm_src / "uvm.sv"))
    args.extend(convert(source) for source in sources)
    return args, build_dir, engine_build_dir


def build_plan(config: ProjectConfig, root: Path, preference: str | None = None) -> SimulationPlan:
    # There is intentionally no user-facing backend choice. Always use the
    # strongest free local engine available on this machine.
    engine = choose_toolchain("auto")
    uses_uvm = project_uses_uvm(config, root)
    waveform = root / config.waveform
    waveform.parent.mkdir(parents=True, exist_ok=True)
    plusargs = [f"+UVM_TESTNAME={config.test}", *config.plusargs] if uses_uvm else []

    if not engine.ready:
        raise RunnerError("The free local engine is not ready yet.")

    if engine.key == "wsl-verilator":
        args, build_dir, wsl_build = _verilator_arguments(config, root, True, uses_uvm)
        wsl_root = windows_to_wsl(root)
        prefix = (
            'export PATH="$HOME/.local/sv-studio/verilator/bin:$PATH"; '
            f"cd {shlex.quote(wsl_root)}; "
        )
        compile_line = (
            prefix
            + f"mkdir -p {shlex.quote(wsl_build)}; "
            + "verilator "
            + " ".join(shlex.quote(arg) for arg in args)
        )
        make_line = prefix + f"make -j$(nproc) -C {shlex.quote(wsl_build)} -f svsim.mk"
        run_line = prefix + shlex.quote(f"{wsl_build}/svsim") + " " + " ".join(
            shlex.quote(arg) for arg in plusargs
        )
        program = engine.executable
        common = ["-d", "Ubuntu", "--", "bash", "-lc"]
        compile_label = "Check UVM project" if uses_uvm else "Check SystemVerilog"
        run_label = "Run UVM test" if uses_uvm else "Run simulation"
        steps = [
            CommandStep(compile_label, program, [*common, compile_line], root),
            CommandStep("Build simulator", program, [*common, make_line], root),
            CommandStep(run_label, program, [*common, run_line], root),
        ]
        return SimulationPlan(engine, steps, waveform, uses_uvm)

    if engine.key == "verilator":
        args, build_dir, _ = _verilator_arguments(config, root, False, uses_uvm)
        make = shutil.which("make") or shutil.which("mingw32-make")
        if not make:
            raise RunnerError("Verilator was found, but Make is missing. The WSL setup is recommended on Windows.")
        steps = [
            CommandStep("Check UVM project" if uses_uvm else "Check SystemVerilog", engine.executable, args, root),
            CommandStep("Build simulator", make, ["-j", "-C", str(build_dir), "-f", "svsim.mk"], root),
            CommandStep("Run UVM test" if uses_uvm else "Run simulation", str(build_dir / "svsim"), plusargs, root),
        ]
        return SimulationPlan(engine, steps, waveform, uses_uvm)

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
        step_count = len(self.plan.steps)
        for step_number, step in enumerate(self.plan.steps, start=1):
            if self._stop_requested:
                self.completed.emit(False, "Simulation stopped")
                return
            self.step_started.emit(step.label)
            self.output.emit(f"\n[{step_number}/{step_count}] {step.label}...\n")
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
                    cleaned = self._clean_output_line(line)
                    cleaned = self._shorten_project_path(cleaned)
                    if cleaned and self._should_show_line(step, cleaned):
                        self.output.emit(cleaned)
                return_code = self._process.wait()
            except OSError as error:
                self.completed.emit(False, str(error))
                return
            if return_code != 0:
                self.completed.emit(False, f"{step.label} failed with exit code {return_code}")
                return
            self.output.emit("Done.\n")
        self.completed.emit(True, "Test passed" if self.plan.uses_uvm else "Simulation completed")

    @staticmethod
    def _clean_output_line(line: str) -> str:
        line = line.replace("\x00", "")
        if line.lstrip().lower().startswith("wsl:"):
            return ""
        if "\ufffd" in line or any(ord(character) < 32 and character not in "\t\r\n" for character in line):
            return ""
        return line

    def _shorten_project_path(self, line: str) -> str:
        root = self.plan.waveform_path.parent.parent
        prefixes = (root.resolve().as_posix(), windows_to_wsl(root))
        for prefix in prefixes:
            line = line.replace(prefix.rstrip("/") + "/", "")
        return line

    def _should_show_line(self, step: CommandStep, line: str) -> bool:
        if step.label.startswith("Run"):
            if self.plan.uses_uvm:
                stripped = line.strip()
                if not stripped:
                    return False
                if stripped.startswith(("UVM_ERROR", "UVM_FATAL")):
                    return True
                if "tools/uvm-verilator/" in line:
                    return False
                boilerplate = (
                    "IMPORTANT RELEASE NOTES",
                    "This implementation of the UVM Library",
                    "standard.  See the DEVIATIONS",
                    "for more details.",
                    "Accellera:1800.2",
                    "All copyright owners",
                    "All Rights Reserved",
                    "Specify +UVM_NO_RELNOTES",
                    "** Report counts by id",
                )
                if any(marker in stripped for marker in boilerplate):
                    return False
                if stripped.startswith(("-----", "[")):
                    return False
            return True
        lowered = line.lower()
        useful = (
            "%error",
            "%warning",
            " error:",
            " fatal:",
            "undefined reference",
            "no such file",
            "exiting due to",
        )
        return any(marker in lowered for marker in useful)

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
