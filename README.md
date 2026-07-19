# SV Studio

SV Studio is a lightweight, local desktop IDE for learning SystemVerilog and
UVM. It combines a project explorer, SystemVerilog editor, UVM-aware logs,
source-linked problems, phase navigation, and a built-in VCD waveform viewer.

The default toolchain is fully open source:

- [Verilator](https://github.com/verilator/verilator) for SystemVerilog
  compilation and simulation.
- [CHIPS Alliance UVM for Verilator](https://github.com/chipsalliance/uvm-verilator),
  based on the Apache-2.0 Accellera reference implementation.
- WSL on Windows, so no commercial simulator or license server is needed.
- Z3 for SystemVerilog constrained randomization.

Verilator's UVM support is actively developing. The included lab intentionally
uses the broadly working UVM subset: factory registration, phases, config DB,
sequences, driver, monitor, analysis ports, scoreboard, objections, and reports.
Advanced constraint randomization and some coverage features can still expose
tool limitations.

## Start

On Windows, double-click `run.bat`, or run:

```powershell
.\run.ps1
```

The first start creates a local Python environment and installs the Qt desktop
runtime. No files are uploaded and no browser is used.

The IDE opens the included **UVM Counter Lab**. Press **F5** immediately to try
the learning Demo Engine, then open **Project → Toolchains** to install the free
Verilator + UVM toolchain for real compilation.

## Randomization and debugging

Select `counter_random_test` to run a weighted `dist` constraint through
Verilator's Z3 solver. Every run records its test, engine, verbosity, and seed.

- **F5** runs normally.
- **F6** stops on the first UVM error and saves the solver exchange to
  `.svstudio/solver.log`.
- **Ctrl+F5** re-runs the exact same seed.
- The **Debug** tab copies reproduction details and opens the solver log.
- Compiler and UVM diagnostics appear in **Problems**; double-click one to jump
  to the source line.

The red dots in the editor gutter are source bookmarks. Verilator runs as a
compiled batch simulator, so they are intentionally not presented as live HDL
breakpoints.

## Open-source toolchain

The setup needs Windows Subsystem for Linux with Ubuntu. In SV Studio:

1. Open **Project → Toolchains**.
2. Click **Set Up Free Toolchain**.
3. Wait for the terminal to report `Complete`.
4. Click **Refresh Status**, save, and press **F5**.

The setup builds Verilator under `~/.local/sv-studio` inside WSL and clones the
UVM library into the current project under `tools/uvm-verilator`.

## Project file

Each workspace uses a `.svstudio.json` file:

```json
{
  "name": "My UVM Project",
  "top": "tb_top",
  "test": "smoke_test",
  "simulator": "auto",
  "sources": ["rtl/**/*.sv", "tb/tb_top.sv"],
  "include_dirs": ["tb"],
  "uvm_home": "",
  "waveform": ".svstudio/waves.vcd"
}
```

For predictable compilation order, use an explicit top-level testbench that
`include`s its UVM class files, as shown in `examples/uvm_counter/tb/tb_top.sv`.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `F5` | Run the selected UVM test |
| `F6` | Debug and stop on the first UVM error |
| `Ctrl+F5` | Re-run the previous seed |
| `Shift+F5` | Stop the active build or simulation |
| `Ctrl+S` | Save the active file |
| `Ctrl+Alt+S` | Save all files |
| `Ctrl+F` | Find in the active file |
| `F8` | Refresh the project explorer |

## Build a Windows package

```powershell
.\tools\build_windows.ps1
```

The portable zip is written to `dist/SVStudio-Windows-x64-v0.2.0.zip`. GitHub
Actions runs the tests and builds the same package on every push; tags matching
`v*` also create a GitHub Release and attach the zip automatically.
